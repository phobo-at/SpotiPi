#!/usr/bin/env python3
"""
🔐 Token Encryption Module for SpotiPi
Provides secure token storage with encryption at rest.
Uses Fernet symmetric encryption with machine-derived keys.
Designed for single-user LAN deployment on Pi Zero W.
"""

import base64
import hashlib
import json
import logging
import os
import platform
import secrets
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _get_machine_id() -> str:
    """Get a stable machine identifier for key derivation.
    
    Uses multiple sources to create a stable machine-specific ID:
    - Machine ID from /etc/machine-id (Linux)
    - Platform node (hostname hash)
    - User-specific salt
    
    Returns:
        str: Stable machine identifier string
    """
    components = []
    
    # Try Linux machine-id
    machine_id_path = Path("/etc/machine-id")
    if machine_id_path.exists():
        try:
            components.append(machine_id_path.read_text().strip())
        except (OSError, PermissionError):
            pass
    
    # Add platform node (hostname-based identifier)
    components.append(str(platform.node()))
    
    # Add user identifier
    components.append(os.getenv("USER", os.getenv("USERNAME", "default")))
    
    # Combine and hash
    combined = ":".join(components)
    return hashlib.sha256(combined.encode()).hexdigest()


def _get_encryption_key_path() -> Path:
    """Get path to the encryption key file."""
    app_name = os.getenv("SPOTIPI_APP_NAME", "spotipi")
    config_dir = Path.home() / f".{app_name}"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / ".token_key"


def _derive_key(machine_id: str, salt: bytes) -> bytes:
    """Derive a 32-byte encryption key from machine ID and salt.
    
    Args:
        machine_id: Machine-specific identifier
        salt: Random salt bytes
        
    Returns:
        bytes: 32-byte key suitable for Fernet
    """
    # Use PBKDF2-like derivation (manual since we avoid extra dependencies)
    key_material = f"{machine_id}:{salt.hex()}".encode()
    
    # Multiple rounds of SHA-256 for key stretching
    derived = key_material
    for _ in range(10000):  # 10k iterations
        derived = hashlib.sha256(derived).digest()
    
    # Fernet requires URL-safe base64 encoded 32-byte key
    return base64.urlsafe_b64encode(derived)


def _get_or_create_key() -> bytes:
    """Get existing encryption key or create a new one.
    
    Returns:
        bytes: Fernet-compatible encryption key
    """
    key_path = _get_encryption_key_path()
    machine_id = _get_machine_id()
    
    if key_path.exists():
        try:
            key_data = json.loads(key_path.read_text())
            salt = bytes.fromhex(key_data["salt"])
            stored_machine_hash = key_data.get("machine_hash", "")
            
            # Verify machine hasn't changed (key would be invalid)
            current_hash = hashlib.sha256(machine_id.encode()).hexdigest()[:16]
            if stored_machine_hash != current_hash:
                logger.warning("Machine ID changed - regenerating encryption key")
                raise ValueError("Machine changed")
            
            return _derive_key(machine_id, salt)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Invalid key file, regenerating: {e}")
    
    # Generate new key
    salt = secrets.token_bytes(32)
    machine_hash = hashlib.sha256(machine_id.encode()).hexdigest()[:16]
    
    key_data = {
        "salt": salt.hex(),
        "machine_hash": machine_hash,
        "version": 1
    }
    
    # Write atomically
    tmp_path = key_path.with_suffix(".tmp")
    try:
        tmp_path.write_text(json.dumps(key_data))
        os.replace(tmp_path, key_path)
        # Restrict permissions
        os.chmod(key_path, 0o600)
    except OSError as e:
        logger.error(f"Failed to write key file: {e}")
        # Clean up temp file if it exists
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
    
    return _derive_key(machine_id, salt)


class TokenEncryption:
    """Handles encryption/decryption of Spotify tokens.
    
    Uses Fernet symmetric encryption when cryptography is available,
    falls back to obfuscation for environments without it.
    """
    
    def __init__(self):
        self._key: Optional[bytes] = None
        self._fernet = None
        self._use_encryption = False
        
        try:
            from cryptography.fernet import Fernet
            self._key = _get_or_create_key()
            self._fernet = Fernet(self._key)
            self._use_encryption = True
            logger.debug("Token encryption initialized with Fernet")
        except ImportError:
            logger.info("cryptography not installed - using obfuscation fallback")
            self._key = _get_or_create_key()
        except Exception as e:
            logger.warning(f"Encryption init failed, using obfuscation: {e}")
            self._key = _get_or_create_key()
    
    def encrypt(self, data: Dict[str, Any]) -> str:
        """Encrypt token data to a string.
        
        Args:
            data: Token dictionary to encrypt
            
        Returns:
            str: Encrypted string (or obfuscated if no encryption)
        """
        json_bytes = json.dumps(data, sort_keys=True).encode("utf-8")
        
        if self._use_encryption and self._fernet:
            encrypted = self._fernet.encrypt(json_bytes)
            return f"ENC:1:{encrypted.decode('utf-8')}"
        
        # Fallback: XOR obfuscation with key
        return self._obfuscate(json_bytes)
    
    def decrypt(self, encrypted_data: str) -> Optional[Dict[str, Any]]:
        """Decrypt token data from string.
        
        Args:
            encrypted_data: Encrypted string
            
        Returns:
            Dict or None if decryption fails
        """
        try:
            # Check for encryption prefix
            if encrypted_data.startswith("ENC:1:"):
                if not self._use_encryption or not self._fernet:
                    logger.error("Encrypted data but no encryption available")
                    return None
                
                token_data = encrypted_data[6:]  # Remove prefix
                decrypted = self._fernet.decrypt(token_data.encode("utf-8"))
                return json.loads(decrypted.decode("utf-8"))
            
            # Check for obfuscation prefix
            if encrypted_data.startswith("OBF:1:"):
                return self._deobfuscate(encrypted_data)
            
            # Plain JSON (legacy, will be re-encrypted on next save)
            return json.loads(encrypted_data)
            
        except Exception as e:
            logger.warning(f"Token decryption failed: {e}")
            return None
    
    def _obfuscate(self, data: bytes) -> str:
        """XOR-based obfuscation fallback.
        
        Args:
            data: Raw bytes to obfuscate
            
        Returns:
            str: Obfuscated string with prefix
        """
        if not self._key:
            return f"OBF:0:{base64.b64encode(data).decode()}"
        
        key_bytes = base64.urlsafe_b64decode(self._key)
        obfuscated = bytes(
            b ^ key_bytes[i % len(key_bytes)]
            for i, b in enumerate(data)
        )
        return f"OBF:1:{base64.urlsafe_b64encode(obfuscated).decode()}"
    
    def _deobfuscate(self, obfuscated: str) -> Optional[Dict[str, Any]]:
        """Reverse XOR obfuscation.
        
        Args:
            obfuscated: Obfuscated string with prefix
            
        Returns:
            Dict or None if deobfuscation fails
        """
        try:
            parts = obfuscated.split(":", 2)
            if len(parts) != 3 or parts[0] != "OBF":
                return None
            
            version, encoded = parts[1], parts[2]
            data = base64.urlsafe_b64decode(encoded)
            
            if version == "0":
                return json.loads(data.decode("utf-8"))
            
            if version == "1" and self._key:
                key_bytes = base64.urlsafe_b64decode(self._key)
                deobfuscated = bytes(
                    b ^ key_bytes[i % len(key_bytes)]
                    for i, b in enumerate(data)
                )
                return json.loads(deobfuscated.decode("utf-8"))
            
            return None
        except Exception as e:
            logger.warning(f"Deobfuscation failed: {e}")
            return None
    
    @property
    def is_encrypted(self) -> bool:
        """Check if real encryption is being used."""
        return self._use_encryption


# Module-level singleton
_encryption: Optional[TokenEncryption] = None


def get_token_encryption() -> TokenEncryption:
    """Get or create the token encryption singleton.
    
    Returns:
        TokenEncryption: Encryption handler instance
    """
    global _encryption
    if _encryption is None:
        _encryption = TokenEncryption()
    return _encryption


def encrypt_token_payload(payload: Dict[str, Any]) -> str:
    """Encrypt a token payload for storage.
    
    Args:
        payload: Token data dictionary
        
    Returns:
        str: Encrypted/obfuscated string
    """
    return get_token_encryption().encrypt(payload)


def decrypt_token_payload(encrypted: str) -> Optional[Dict[str, Any]]:
    """Decrypt a stored token payload.
    
    Args:
        encrypted: Encrypted/obfuscated string
        
    Returns:
        Dict or None if decryption fails
    """
    return get_token_encryption().decrypt(encrypted)


def is_encryption_available() -> bool:
    """Check if real encryption (not just obfuscation) is available.
    
    Returns:
        bool: True if cryptography library is available
    """
    return get_token_encryption().is_encrypted
