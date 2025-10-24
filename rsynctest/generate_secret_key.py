#!/usr/bin/env python3
"""
🔐 Generate Secure Secret Key for SpotiPi
This script generates a cryptographically secure secret key for Flask sessions.
"""

import os
import secrets
from pathlib import Path


def generate_secret_key():
    """Generate a secure 32-byte hex secret key."""
    return secrets.token_hex(32)

def update_env_file():
    """Update or create .env file with secure secret key."""
    # Path-agnostic configuration directory
    app_name = os.getenv("SPOTIPI_APP_NAME", "spotipi")
    env_path = Path.home() / f".{app_name}" / ".env"
    
    # Ensure directory exists
    env_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Generate new secret key
    new_secret_key = generate_secret_key()
    
    print(f"🔐 Generated secure secret key: {new_secret_key}")
    print(f"📁 Environment file: {env_path}")
    
    # Read existing .env or create new one
    env_lines = []
    flask_secret_found = False
    
    if env_path.exists():
        with open(env_path, 'r') as f:
            env_lines = f.readlines()
        
        # Update existing FLASK_SECRET_KEY or add it
        for i, line in enumerate(env_lines):
            if line.startswith('FLASK_SECRET_KEY='):
                env_lines[i] = f'FLASK_SECRET_KEY={new_secret_key}\n'
                flask_secret_found = True
                break
    
    # Add FLASK_SECRET_KEY if not found
    if not flask_secret_found:
        env_lines.append(f'FLASK_SECRET_KEY={new_secret_key}\n')
    
    # Write back to file
    with open(env_path, 'w') as f:
        f.writelines(env_lines)
    
    print(f"✅ Secret key updated in {env_path}")
    print("🚀 Restart SpotiPi application to apply the new secret key")

if __name__ == "__main__":
    print("🔐 SpotiPi Secret Key Generator")
    print("=" * 40)
    
    choice = input("Generate new secret key? (y/N): ").lower().strip()
    
    if choice in ['y', 'yes']:
        update_env_file()
    else:
        # Just generate and display
        secret_key = generate_secret_key()
        print(f"🔐 Generated secret key: {secret_key}")
        print("\n📝 Add this to your .env file:")
        print(f"FLASK_SECRET_KEY={secret_key}")