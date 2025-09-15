# 🔄 SpotiPi Migration Guide: `spotify_wakeup` → `spotipi`

## 📋 Migration Overview

Diese Anleitung führt Sie durch die sichere Umbenennung des Arbeitsverzeichnisses von `spotify_wakeup` zu `spotipi`, sowohl lokal als auch auf dem Raspberry Pi.

### ✨ **Path-Independence Verbesserungen**
Alle hardcoded Pfade wurden durch umgebungsvariable-gesteuerte, path-agnostische Lösungen ersetzt:
- **Environment Variable**: `SPOTIPI_APP_NAME` (default: "spotipi")
- **Config Directory**: `~/.${SPOTIPI_APP_NAME}/` (default: `~/.spotipi/`)
- **Pi App Directory**: `/home/pi/${SPOTIPI_APP_NAME}/` (default: `/home/pi/spotipi/`)

### 🎯 **Ziele der Migration**
1. **Konsistente Namensgebung**: Projekt, Verzeichnisse und Services heißen alle "spotipi"
2. **Path-Independence**: Keine hardcoded Pfade mehr
3. **Rückwärtskompatibilität**: Datenmigration ohne Verlust
4. **Saubere Struktur**: Alte Verzeichnisse werden bereinigt

## 🚀 **Schritt-für-Schritt Migration**

### **Phase 1: Lokale Migration**

#### 1.1 Backup erstellen
```bash
cd /Users/michi/spotipi-dev/
cp -r spotify_wakeup spotify_wakeup_backup_$(date +%Y%m%d)
```

#### 1.2 Repository lokal umbenennen  
```bash
cd /Users/michi/spotipi-dev/
mv spotify_wakeup spotipi
cd spotipi
```

#### 1.3 Git Remote aktualisieren (falls erforderlich)
```bash
# Falls Repository-URL geändert werden soll
git remote set-url origin git@github.com:phobo-at/spotipi.git
```

#### 1.4 Neue path-agnostic Scripts aktivieren
```bash
# Alte Scripts als Backup beibehalten, neue verwenden
mv scripts/deploy_to_pi.sh scripts/deploy_to_pi_old.sh
mv scripts/deploy_to_pi_new.sh scripts/deploy_to_pi.sh
chmod +x scripts/deploy_to_pi.sh

mv scripts/toggle_logging.sh scripts/toggle_logging_old.sh  
mv scripts/toggle_logging_new.sh scripts/toggle_logging.sh
chmod +x scripts/toggle_logging.sh
```

### **Phase 2: Raspberry Pi Vorbereitung**

#### 2.1 Service stoppen
```bash
ssh pi@spotipi.local "sudo systemctl stop spotify-web.service"
```

#### 2.2 Config/Cache Migration auf Pi
```bash
ssh pi@spotipi.local "
# Backup erstellen
sudo cp -r ~/.spotify_wakeup ~/.spotify_wakeup_backup_$(date +%Y%m%d) 2>/dev/null || true

# Neues Verzeichnis erstellen und Daten migrieren
mkdir -p ~/.spotipi
if [ -d ~/.spotify_wakeup ]; then
  cp -r ~/.spotify_wakeup/* ~/.spotipi/ 2>/dev/null || true
fi
"
```

#### 2.3 Hauptverzeichnis Migration auf Pi
```bash
ssh pi@spotipi.local "
# Backup des Hauptverzeichnisses  
sudo cp -r /home/pi/spotify_wakeup /home/pi/spotify_wakeup_backup_$(date +%Y%m%d) 2>/dev/null || true

# Neues Verzeichnis erstellen
sudo mkdir -p /home/pi/spotipi
sudo chown pi:pi /home/pi/spotipi

# Code migrieren (außer venv - das wird neu erstellt)
if [ -d /home/pi/spotify_wakeup ]; then
  rsync -av --exclude='venv/' --exclude='*.log' --exclude='logs/' /home/pi/spotify_wakeup/ /home/pi/spotipi/
fi
"
```

### **Phase 3: Systemd Service Update**

#### 3.1 Neuen Service erstellen
```bash
ssh pi@spotipi.local "
# Backup alten Service
sudo cp /etc/systemd/system/spotify-web.service /etc/systemd/system/spotify-web.service.backup

# Neuen path-agnostic Service erstellen
sudo tee /etc/systemd/system/spotify-web.service > /dev/null << 'EOF'
[Unit]
Description=SpotiPi Web Interface
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/spotipi
EnvironmentFile=/home/pi/spotipi/.env
Environment=\"SPOTIPI_APP_NAME=spotipi\"
ExecStart=/home/pi/spotipi/venv/bin/python run.py
Restart=always
Environment=\"PYTHONUNBUFFERED=1\"
Environment=\"PORT=5000\"
StandardOutput=append:/home/pi/spotipi/web.log
StandardError=append:/home/pi/spotipi/web.log

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
"
```

### **Phase 4: Python Environment Setup**

#### 4.1 Virtual Environment auf Pi neu erstellen
```bash
ssh pi@spotipi.local "
cd /home/pi/spotipi
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
"
```

#### 4.2 .env Datei migrieren
```bash
ssh pi@spotipi.local "
# .env aus altem Verzeichnis kopieren falls vorhanden
if [ -f /home/pi/spotify_wakeup/.env ]; then
  cp /home/pi/spotify_wakeup/.env /home/pi/spotipi/.env
fi

# .env aus Config-Verzeichnis kopieren falls vorhanden  
if [ -f ~/.spotipi/.env ]; then
  cp ~/.spotipi/.env /home/pi/spotipi/.env
fi
"
```

### **Phase 5: Deployment Test**

#### 5.1 Erstes Deployment vom neuen lokalen Verzeichnis
```bash
cd /Users/michi/spotipi-dev/spotipi

# Environment Variables setzen für Migration
export SPOTIPI_APP_NAME="spotipi"
export SPOTIPI_PI_PATH="/home/pi/spotipi"

# Deployment ausführen  
./scripts/deploy_to_pi.sh
```

#### 5.2 Service Status prüfen
```bash
ssh pi@spotipi.local "
sudo systemctl status spotify-web.service
sudo journalctl -u spotify-web.service -n 20
"
```

#### 5.3 Web Interface testen
```bash
# Browser öffnen oder curl Test
curl -s -o /dev/null -w "%{http_code}" http://spotipi.local:5000
```

### **Phase 6: Cleanup (nach erfolgreicher Migration)**

#### 6.1 Alte Verzeichnisse auf Pi bereinigen
```bash
ssh pi@spotipi.local "
# Nach erfolgreichem Test - alte Verzeichnisse löschen
sudo rm -rf /home/pi/spotify_wakeup
rm -rf ~/.spotify_wakeup

# Backup-Verzeichnisse können nach einigen Tagen gelöscht werden
# sudo rm -rf /home/pi/spotify_wakeup_backup_*
# rm -rf ~/.spotify_wakeup_backup_*
"
```

#### 6.2 Lokale Bereinigung
```bash
cd /Users/michi/spotipi-dev/
# Nach erfolgreichem Test
rm -rf spotify_wakeup_backup_*
```

## 🔧 **Environment Variables für Anpassungen**

### **Deployment Configuration**
```bash
export SPOTIPI_APP_NAME="spotipi"           # App name (default: spotipi)
export SPOTIPI_PI_HOST="pi@spotipi.local"   # Pi SSH host
export SPOTIPI_PI_PATH="/home/pi/spotipi"   # Pi app directory
export SPOTIPI_LOCAL_PATH="/path/to/local"  # Local project path (auto-detected)
export SPOTIPI_SERVICE_NAME="spotify-web.service"  # Systemd service name
export SPOTIPI_SHOW_STATUS="1"             # Show service status after deployment
```

### **Application Runtime Configuration**  
```bash
export SPOTIPI_APP_NAME="spotipi"           # Affects ~/.spotipi/ config directory
export SPOTIPI_LOG_DIR="/custom/log/path"   # Custom log directory
export SPOTIPI_ENV="production"            # Environment mode
```

## 🛡️ **Rollback Plan**

Falls Probleme auftreten:

### **Service Rollback**
```bash
ssh pi@spotipi.local "
sudo systemctl stop spotify-web.service
sudo cp /etc/systemd/system/spotify-web.service.backup /etc/systemd/system/spotify-web.service
sudo systemctl daemon-reload
sudo systemctl start spotify-web.service
"
```

### **Directory Rollback**
```bash
ssh pi@spotipi.local "
sudo rm -rf /home/pi/spotipi
sudo mv /home/pi/spotify_wakeup_backup_* /home/pi/spotify_wakeup
rm -rf ~/.spotipi  
mv ~/.spotify_wakeup_backup_* ~/.spotify_wakeup
"
```

## ✅ **Migration Checklist**

- [ ] **Phase 1**: Lokales Backup erstellt
- [ ] **Phase 1**: Repository lokal umbenannt zu `spotipi`
- [ ] **Phase 1**: Neue path-agnostic Scripts aktiviert  
- [ ] **Phase 2**: Service auf Pi gestoppt
- [ ] **Phase 2**: Config-Verzeichnis migriert (`~/.spotify_wakeup` → `~/.spotipi`)
- [ ] **Phase 2**: Hauptverzeichnis migriert (`/home/pi/spotify_wakeup` → `/home/pi/spotipi`)
- [ ] **Phase 3**: Systemd Service aktualisiert
- [ ] **Phase 4**: Python venv neu erstellt
- [ ] **Phase 4**: .env Datei migriert
- [ ] **Phase 5**: Deployment getestet
- [ ] **Phase 5**: Web Interface funktioniert
- [ ] **Phase 6**: Alte Verzeichnisse bereinigt

## 🔍 **Migration Verification**

Nach der Migration sollten Sie die erfolgreiche Durchführung verifizieren:

### **Automatische Verifikation**

#### **Schnelle lokale Überprüfung:**
```bash
./scripts/verify_local.sh
```

#### **Vollständige Migration-Verifikation:**
```bash
./scripts/verify_migration.sh
```

### **Manuelle Verifikation Checklist**

#### **Lokale Environment:**
- [ ] Arbeitsverzeichnis heißt `spotipi`
- [ ] Alte Scripts sind als `_old.sh` gesichert
- [ ] Neue Scripts sind ausführbar
- [ ] Git Remote zeigt auf korrekte URL (falls geändert)

#### **Raspberry Pi Environment:**
- [ ] SSH Verbindung funktioniert: `ssh pi@spotipi.local`
- [ ] Neues Hauptverzeichnis existiert: `/home/pi/spotipi/`
- [ ] Neues Config-Verzeichnis existiert: `~/.spotipi/`
- [ ] Alte Verzeichnisse sind bereinigt oder als Backup markiert

#### **System Service:**
```bash
ssh pi@spotipi.local "sudo systemctl status spotify-web.service"
```
- [ ] Service ist `active (running)`
- [ ] Service ist `enabled` für Autostart
- [ ] Keine Fehler in den Logs

#### **Web Interface:**
- [ ] Web Interface erreichbar: `http://spotipi.local:5000`
- [ ] Hauptseite lädt (HTTP 200)
- [ ] API Endpoints antworten: `/api/alarm_status`, `/api/spotify/library_status`

#### **Python Environment:**
```bash
ssh pi@spotipi.local "cd /home/pi/spotipi && ./venv/bin/python --version"
```
- [ ] Virtual Environment funktioniert
- [ ] Alle Requirements installiert
- [ ] App kann importiert werden

#### **Configuration:**
```bash
ssh pi@spotipi.local "cd /home/pi/spotipi && ./venv/bin/python -c 'from src.config import load_config; print(load_config())'"
```
- [ ] Config lädt erfolgreich
- [ ] .env Datei ist vorhanden (falls benötigt)
- [ ] Spotify Credentials funktionieren

### **Verifikation Output Codes**

Die `verify_migration.sh` Script liefert diese Exit Codes:
- **0**: Vollständig erfolgreich (grün)
- **1**: Erfolgreich mit Warnungen (gelb) 
- **2**: Fehlgeschlagen (rot)

### **Troubleshooting Migration Issues**

#### **Service startet nicht:**
```bash
ssh pi@spotipi.local "sudo journalctl -u spotify-web.service -n 50"
```

#### **Web Interface nicht erreichbar:**
```bash
ssh pi@spotipi.local "netstat -tlnp | grep :5000"
```

#### **Python Import Fehler:**
```bash
ssh pi@spotipi.local "cd /home/pi/spotipi && ./venv/bin/python -c 'import sys; print(sys.path)'"
```

#### **Config Problems:**
```bash
ssh pi@spotipi.local "ls -la ~/.spotipi/ /home/pi/spotipi/config/"
```

## 🎯 **Post-Migration Benefits**

Nach der erfolgreichen Migration haben Sie:
- ✅ **Path-Independence**: Keine hardcoded Pfade mehr
- ✅ **Konsistente Namensgebung**: Alles heißt "spotipi"  
- ✅ **Flexible Konfiguration**: Über Environment Variables anpassbar
- ✅ **Saubere Struktur**: Alte Verzeichnisse bereinigt
- ✅ **Future-Proof**: Einfache Migration für zukünftige Änderungen
- ✅ **Automatische Verifikation**: Scripts für Validierung der Migration