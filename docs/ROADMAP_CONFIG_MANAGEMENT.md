# SpotiPi Configuration Management - Roadmap

*Web-basierte Spotify-Konfiguration und erweiterte Einstellungen*

## 🎯 **Vision: Self-Service Setup**

Benutzer sollen SpotiPi komplett über das Web-Interface einrichten können, ohne SSH oder Dateisystem-Zugriff. One-Click Setup vom ersten Start bis zur funktionsfähigen Installation.

## 🚀 **Phase 1: Spotify Connection Setup (4-6 Wochen)**

### Core Features
- [ ] **Setup Wizard**: Geführte Ersteinrichtung beim ersten Start
- [ ] **Spotify App Registration**: Schritt-für-Schritt Anleitung + Links
- [ ] **Token Generation**: Integrierter OAuth-Flow ohne externe Tools
- [ ] **Connection Testing**: Automatische Validierung der Spotify-Verbindung

### Technical Implementation
```
/config-wizard/
├── step-1-welcome.html        # Willkommen + Übersicht
├── step-2-spotify-app.html    # Spotify App erstellen
├── step-3-oauth.html          # OAuth Flow
├── step-4-test.html           # Verbindung testen
└── step-5-complete.html       # Setup abgeschlossen
```

### Backend Components
```python
# src/blueprints/config.py
@app.route("/setup/spotify/oauth")
def spotify_oauth_start():
    # OAuth Flow initiieren
    
@app.route("/setup/spotify/callback") 
def spotify_oauth_callback():
    # Token empfangen und speichern
    
@app.route("/setup/test-connection")
def test_spotify_connection():
    # Verbindung validieren
```

## 🔧 **Phase 2: Advanced Configuration UI (2-3 Wochen)**

### Settings Categories
- [ ] **Spotify Settings**: Token-Management, API-Limits, Retry-Verhalten
- [ ] **Network Settings**: CORS, Rate Limiting, mDNS-Name
- [ ] **System Settings**: Logging-Level, Cache-Größen, Auto-Updates
- [ ] **Alarm Settings**: Standard-Volumes, Fade-Zeiten, Device-Präferenzen

### UI Components
```typescript
interface ConfigSection {
  id: string;
  title: string;
  description: string;
  settings: ConfigSetting[];
}

interface ConfigSetting {
  key: string;
  type: 'text' | 'number' | 'boolean' | 'select' | 'password';
  value: any;
  validation?: ValidationRule[];
  helpText?: string;
}
```

### Advanced Features
- [ ] **Config Import/Export**: JSON-basierte Konfigurationssicherung
- [ ] **Environment Detection**: Automatische Pi vs. Development Settings
- [ ] **Backup System**: Automatische Config-Backups vor Änderungen
- [ ] **Reset Options**: Factory Reset + Selective Reset

## 🌐 **Phase 3: OAuth Integration & Security (3-4 Wochen)**

### Spotify OAuth Flow
```mermaid
graph LR
    A[User öffnet Setup] --> B[Spotify App Anleitung]
    B --> C[Client ID/Secret eingeben]
    C --> D[OAuth Flow starten]
    D --> E[Spotify Autorisierung]
    E --> F[Token empfangen]
    F --> G[Automatische Validierung]
    G --> H[Setup komplett]
```

### Security Implementation
- [ ] **Secure Token Storage**: Verschlüsselte `.env` Files
- [ ] **PKCE OAuth Flow**: Sicherheitsbest-Practice für öffentliche Clients
- [ ] **Token Rotation**: Automatische Refresh-Token Erneuerung
- [ ] **Config Encryption**: Sensible Daten verschlüsselt speichern

### User Experience
- [ ] **Guided Tutorial**: Screenshots + Video-Links für Spotify App Setup
- [ ] **Error Recovery**: Detaillierte Fehlerdiagnose bei OAuth-Problemen
- [ ] **Status Dashboard**: Live-Status der Spotify-Verbindung
- [ ] **Re-Authorization**: Einfache Token-Erneuerung ohne komplettes Setup

## 📱 **Phase 4: Mobile-Optimized Config (2 Wochen)**

### Mobile Configuration Experience
- [ ] **Touch-Optimized Forms**: Große Input-Felder, Touch-Targets
- [ ] **Progressive Disclosure**: Erweiterte Settings nur auf Anfrage
- [ ] **Gesture Navigation**: Swipe zwischen Setup-Schritten
- [ ] **QR Code Integration**: Einfache Übertragung von Spotify-URLs

### Mobile-Specific Features
- [ ] **Camera Integration**: QR-Code Scanner für Client-Secret
- [ ] **Clipboard Integration**: Automatisches Einfügen von Spotify-Daten
- [ ] **Haptic Feedback**: Bestätigungen bei erfolgreichen Steps
- [ ] **Offline Indicators**: Klare Meldung wenn Internet fehlt

## 🔄 **Phase 5: Advanced Management Features (4-5 Wochen)**

### Multi-Device Management
- [ ] **Device Groups**: Logische Gruppierung von Spotify-Geräten
- [ ] **Priority Settings**: Bevorzugte Devices für Alarm/Sleep
- [ ] **Device Health**: Status-Monitoring aller registrierten Geräte
- [ ] **Auto-Discovery**: Automatische Erkennung neuer Spotify-Geräte

### Configuration Profiles
- [ ] **User Profiles**: Verschiedene Nutzer-Konfigurationen
- [ ] **Scene Management**: Vordefinierte Alarm/Sleep-Szenarien
- [ ] **Schedule Profiles**: Wochentag-spezifische Konfigurationen
- [ ] **Backup Strategies**: Automatisierte Config-Sicherung

### System Integration
- [ ] **Home Assistant Integration**: Config-Sync mit HA
- [ ] **Network Scanning**: Automatische Erkennung anderer SpotiPi-Instanzen
- [ ] **Update Management**: Automatische Updates mit Config-Preservation
- [ ] **Migration Tools**: Update von Legacy-Konfigurationen

## 🛠️ **Technical Architecture**

### Config Storage Strategy
```yaml
# config/runtime.json (Encrypted)
spotify:
  client_id: "encrypted_value"
  client_secret: "encrypted_value"
  access_token: "encrypted_value"
  refresh_token: "encrypted_value"
  
system:
  device_name: "SpotiPi-Living"
  network:
    cors_origins: ["192.168.1.*"]
    rate_limits:
      api: 100/minute
      config: 10/minute
      
user_preferences:
  default_volume: 50
  fade_duration: 30
  preferred_devices: ["Sonos Living", "Echo Dot"]
```

### API Endpoints
```python
# Configuration Management API
POST /api/config/spotify/setup     # OAuth Flow initiieren
GET  /api/config/spotify/status    # Verbindungsstatus prüfen
POST /api/config/spotify/refresh   # Token erneuern

GET  /api/config/sections          # Alle Config-Bereiche
PUT  /api/config/{section}         # Section-spezifische Updates
POST /api/config/backup            # Backup erstellen
POST /api/config/restore           # Backup wiederherstellen

GET  /api/config/schema            # Frontend Config-Schema
POST /api/config/validate          # Config-Validierung
POST /api/config/reset             # Factory Reset
```

### Frontend State Management
```javascript
// Configuration Store (Vue/React)
const configStore = {
  state: {
    sections: [],
    currentSection: null,
    isSetupComplete: false,
    spotifyStatus: 'disconnected'
  },
  
  mutations: {
    SET_CONFIG_SECTION(state, section) { ... },
    UPDATE_SPOTIFY_STATUS(state, status) { ... }
  },
  
  actions: {
    async loadConfiguration() { ... },
    async saveConfiguration(section, data) { ... },
    async testSpotifyConnection() { ... }
  }
}
```

## 📋 **Implementation Roadmap**

### Sprint 1 (2 Wochen) - Foundation
- Config-Blueprint erstellen
- Basic Setup-Wizard UI
- Spotify OAuth Flow (Backend)
- Token Storage System

### Sprint 2 (2 Wochen) - Core Setup
- Setup-Wizard Frontend
- Spotify App Registration Guide
- Connection Testing
- Error Handling & Recovery

### Sprint 3 (2 Wochen) - Advanced Config
- Settings Categories UI
- Config Validation System
- Import/Export Functionality
- Mobile Optimizations

### Sprint 4 (2 Wochen) - Security & Polish
- Config Encryption
- PKCE OAuth Implementation  
- User Testing & Bug Fixes
- Documentation & Help System

### Sprint 5 (2 Wochen) - Advanced Features
- Device Management
- Profile System
- System Integration Prep
- Performance Optimization

## 🎨 **User Experience Flow**

### First-Time Setup
1. **Welcome Screen**: "Willkommen bei SpotiPi! Lass uns deine Spotify-Verbindung einrichten."
2. **Spotify App Guide**: Step-by-Step mit Screenshots für Spotify Developer Dashboard
3. **OAuth Flow**: "Autorisiere SpotiPi bei Spotify" → Redirect → Callback
4. **Connection Test**: Automatischer Test mit Device-Discovery
5. **Completion**: "🎉 Setup erfolgreich! Dein erster Alarm ist bereit."

### Daily Configuration
- **Quick Settings**: Häufige Einstellungen direkt auf Hauptseite
- **Advanced Config**: Detaillierte Einstellungen in separater Config-Seite
- **Status Indicators**: Spotify-Verbindung, System-Health immer sichtbar
- **One-Click Actions**: Token erneuern, Devices neu scannen, Config-Backup

### Error Recovery
- **Connection Lost**: "Spotify-Verbindung verloren - [Token erneuern] [Setup wiederholen]"
- **Invalid Config**: "Konfigurationsfehler erkannt - [Automatisch reparieren] [Backup laden]"
- **API Limits**: "Spotify-API-Limit erreicht - Versuche es in X Minuten erneut"

## ⚡ **Quick Wins (Erste 2 Wochen)**

### MVP Features
- [ ] **Basic Config Page**: `/config` Route mit einfachen Einstellungen
- [ ] **Spotify Token Input**: Manuelle Token-Eingabe mit Validierung
- [ ] **Connection Status**: Live-Anzeige der Spotify-Verbindung
- [ ] **Config Persistence**: Sichere Speicherung in JSON-Config

### Implementation
```python
# Minimal MVP für sofortigen Nutzen
@app.route("/config")
def config_page():
    return render_template('config.html', 
                         current_config=load_config(),
                         spotify_status=get_spotify_status())

@app.route("/config/spotify", methods=["POST"])
def update_spotify_config():
    # Token validieren und speichern
    # Verbindung testen
    # Feedback an User
```

---

**Geschätzter Gesamtaufwand:** 12-16 Wochen
**Empfohlenes Vorgehen:** MVP zuerst (2 Wochen), dann iterative Erweiterung
**ROI:** Massiv erhöhte Benutzerfreundlichkeit, reduzierter Support-Aufwand