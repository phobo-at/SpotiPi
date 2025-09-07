#!/usr/bin/env python3
"""
Spotify Token Generator für SpotiPi
Generiert einen neuen Refresh Token für die Spotify API
"""

import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Spotify App Credentials (from environment variables)
CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
REDIRECT_URI = "http://127.0.0.1:8080"  # Standard Spotipy Port

if not CLIENT_ID or not CLIENT_SECRET:
    print("❌ Error: SPOTIFY_CLIENT_ID und SPOTIFY_CLIENT_SECRET müssen in der .env Datei gesetzt sein!")
    print("📝 Erstelle eine .env Datei mit deinen Spotify App Credentials.")
    exit(1)

# Benötigte Scopes
SCOPES = [
    "user-read-playback-state",
    "user-modify-playback-state", 
    "user-read-currently-playing",
    "playlist-read-private",
    "playlist-read-collaborative",
    "user-library-read",
    "user-top-read",
    "user-read-recently-played"
]

def get_spotify_token():
    """Generiert einen neuen Spotify Refresh Token"""
    
    print("🎵 Spotify Token Generator für SpotiPi")
    print("="*50)
    
    # Spotify OAuth Setup
    sp_oauth = SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=" ".join(SCOPES),
        cache_path=".spotify_cache"
    )
    
    # Token abrufen (öffnet Browser für Autorisierung)
    print("🌐 Öffne Browser für Spotify Autorisierung...")
    token_info = sp_oauth.get_access_token()
    
    if token_info:
        print("\n✅ Token erfolgreich generiert!")
        print("="*50)
        print(f"ACCESS_TOKEN: {token_info['access_token'][:50]}...")
        print(f"REFRESH_TOKEN: {token_info['refresh_token']}")
        print(f"EXPIRES_IN: {token_info['expires_in']} Sekunden")
        print("="*50)
        
        # .env Datei updaten (nur Refresh Token, Client-Daten bleiben bestehen)
        env_file_path = '.env'
        env_content = []
        
        # Bestehende .env lesen falls vorhanden
        if os.path.exists(env_file_path):
            with open(env_file_path, 'r') as f:
                env_content = f.readlines()
        
        # Refresh Token updaten oder hinzufügen
        refresh_token_line = f"SPOTIFY_REFRESH_TOKEN={token_info['refresh_token']}\n"
        updated = False
        
        for i, line in enumerate(env_content):
            if line.startswith('SPOTIFY_REFRESH_TOKEN='):
                env_content[i] = refresh_token_line
                updated = True
                break
        
        if not updated:
            env_content.append(refresh_token_line)
        
        # .env Datei schreiben
        with open(env_file_path, 'w') as f:
            f.writelines(env_content)
        
        print("💾 .env Datei wurde aktualisiert!")
        print("🎉 SpotiPi ist jetzt bereit!")
        
    else:
        print("❌ Token-Generierung fehlgeschlagen")

if __name__ == "__main__":
    get_spotify_token()
