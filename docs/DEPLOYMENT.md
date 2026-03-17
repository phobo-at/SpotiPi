# 🚀 SpotiPi Deployment Anleitung

Umfassende Anleitung für die Einrichtung und Verwaltung des SpotiPi Deployments auf dem Raspberry Pi.

## 📋 Inhaltsverzeichnis

1. [Aktueller Setup Überblick](#aktueller-setup-überblick)
2. [Komplette Einrichtung von Grund auf](#komplette-einrichtung-von-grund-auf)
3. [Git Hook Deployment](#git-hook-deployment)
4. [Service Verwaltung](#service-verwaltung)
5. [Fehlerbehebung](#fehlerbehebung)
6. [Wartung](#wartung)

---

## 🏗️ Aktueller Setup Überblick

### Architektur
```
Mac Entwicklung              Raspberry Pi Produktion
├── /spotipi-dev/            ├── /home/pi/repo.git (bare repo)
│   └── spotipi              ├── /home/pi/spotipi (app)
│                            ├── systemd service (spotipi.service)
│                            └── Waitress WSGI Server via `python run.py`
```

### Deployment Ablauf
1. **Entwickeln** auf dem Mac in `/Users/michi/spotipi-dev/spotipi/`
2. **Push** via `git push prod master`
3. **Auto-Deploy** via Git post-receive hook
4. **Auto-Neustart** systemd service
5. **Bereit** unter `http://spotipi.local:5000`

### Aktuelle Git Remotes
```bash
origin  git@github.com:phobo-at/spotipi.git (GitHub Backup)
prod    ssh://pi@spotipi.local/home/pi/repo.git (Produktion)
```

---

## 🛠️ Komplette Einrichtung von Grund auf

### 1. Raspberry Pi Vorbereitung

```bash
# System aktualisieren
sudo apt update && sudo apt upgrade -y

# Benötigte Pakete installieren
sudo apt install -y git python3 python3-pip python3-venv nginx

# Pi User erstellen (falls nicht vorhanden)
sudo useradd -m -s /bin/bash pi
sudo usermod -aG sudo pi
```

### 2. Anwendungsverzeichnis Einrichtung

```bash
# Anwendungsverzeichnis erstellen
sudo mkdir -p /home/pi/spotipi
sudo chown pi:pi /home/pi/spotipi

# Virtuelle Umgebung erstellen
cd /home/pi/spotipi
python3 -m venv venv
source venv/bin/activate

# Basis-Abhängigkeiten installieren
pip install flask requests python-dotenv psutil
```

### 3. Git Repository Einrichtung

```bash
# Bare Git Repository für Deployment erstellen
cd /home/pi
git init --bare repo.git

# Besitzrechte setzen
sudo chown -R pi:pi /home/pi/repo.git
```

### 4. Git Hook Konfiguration

Post-receive Hook erstellen:

```bash
cat > /home/pi/repo.git/hooks/post-receive << 'EOF'
#!/bin/bash

DEPLOY_DIR="/home/pi/spotipi"
REPO_DIR="/home/pi/repo.git"
LOGFILE="/home/pi/deploy.log"

echo "[$(date)] 🚀 Deployment gestartet via post-receive" >> "$LOGFILE"

# Code auschecken
cd "$DEPLOY_DIR" || {
    echo "[$(date)] ❌ FEHLER: Kann nicht zu $DEPLOY_DIR wechseln" >> "$LOGFILE"
    exit 1
}

echo "[$(date)] 📥 Aktueller Code wird ausgecheckt..." >> "$LOGFILE"
GIT_DIR="$REPO_DIR" GIT_WORK_TREE="$DEPLOY_DIR" git checkout -f master >> "$LOGFILE" 2>&1

# Prüfen ob requirements.txt geändert wurde
if git diff --name-only HEAD@{1} HEAD 2>/dev/null | grep -q "requirements.txt"; then
    echo "[$(date)] 📦 requirements.txt geändert, Abhängigkeiten werden aktualisiert..." >> "$LOGFILE"
    /home/pi/spotipi/venv/bin/pip install -r requirements.txt >> "$LOGFILE" 2>&1
else
    echo "[$(date)] ⏭️  Keine Änderungen an Abhängigkeiten erkannt" >> "$LOGFILE"
fi

# App neustarten
echo "[$(date)] 🔄 spotipi.service wird neugestartet..." >> "$LOGFILE"
sudo systemctl restart spotipi.service >> "$LOGFILE" 2>&1

if [ $? -eq 0 ]; then
    echo "[$(date)] ✅ Deployment abgeschlossen! Service erfolgreich neugestartet." >> "$LOGFILE"
else
    echo "[$(date)] ❌ FEHLER: Service-Neustart fehlgeschlagen!" >> "$LOGFILE"
fi

echo "[$(date)] 📱 App sollte verfügbar sein unter http://spotipi.local:5000" >> "$LOGFILE"
EOF

# Hook ausführbar machen
chmod +x /home/pi/repo.git/hooks/post-receive
```

### 5. Systemd Service Einrichtung

Service-Datei erstellen:

```bash
sudo tee /etc/systemd/system/spotipi.service << 'EOF'
[Unit]
Description=SpotiPi Web Anwendung
After=network.target

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/home/pi/spotipi
Environment=PATH=/home/pi/spotipi/venv/bin
ExecStart=/home/pi/spotipi/venv/bin/python run.py
Restart=always
RestartSec=10

# Logging
StandardOutput=append:/home/pi/web.log
StandardError=append:/home/pi/web.log

[Install]
WantedBy=multi-user.target
EOF

# Service aktivieren und starten
sudo systemctl daemon-reload
sudo systemctl enable spotipi.service
sudo systemctl start spotipi.service
```

### 6. Alarm Timer Einrichtung (Robustheit)

**Seit v1.3.8** wird der Alarm-Timer standardmäßig aktiviert, um Robustheit nach Stromausfall/Reboot zu gewährleisten.

Der systemd-Timer (`spotipi-alarm.timer`) führt täglich um 05:30 Uhr einen Alarm-Readiness-Check aus und stellt sicher, dass verpasste Alarme nach Downtime nachgeholt werden (`Persistent=true`).

```bash
# Timer-Status prüfen
sudo systemctl status spotipi-alarm.timer

# Timer manuell aktivieren (falls nicht automatisch geschehen)
sudo systemctl enable --now spotipi-alarm.timer

# Timer deaktivieren (falls gewünscht)
sudo systemctl disable --now spotipi-alarm.timer
# ODER beim Deployment:
SPOTIPI_ENABLE_ALARM_TIMER=0 ./scripts/deploy_to_pi.sh
```

**Timer-Details:**
- **Zeitplan:** Täglich um 05:30 Uhr
- **Catch-up:** `Persistent=true` – führt verpasste Ausführungen nach Reboot nach
- **Service:** `spotipi-alarm.service` ruft `scripts/run_alarm.sh` auf
- **Zweck:** Backup-Layer zusätzlich zum in-process Scheduler-Thread

### 7. Sudoers für Service-Verwaltung konfigurieren

Pi User erlauben, Service ohne Passwort zu verwalten:

```bash
sudo tee /etc/sudoers.d/spotipi << 'EOF'
pi ALL=(ALL) NOPASSWD: /bin/systemctl restart spotipi.service
pi ALL=(ALL) NOPASSWD: /bin/systemctl start spotipi.service
pi ALL=(ALL) NOPASSWD: /bin/systemctl stop spotipi.service
pi ALL=(ALL) NOPASSWD: /bin/systemctl status spotipi.service
EOF
```

### 7. Umgebungskonfiguration

```bash
# Umgebungsverzeichnis und Datei erstellen
mkdir -p /home/pi/.spotipi
touch /home/pi/.spotipi/.env
chmod 600 /home/pi/.spotipi/.env

# Spotify-Anmeldedaten hinzufügen (manuell bearbeiten)
nano /home/pi/.spotipi/.env
```

Inhalt der `.env`:
```
SPOTIFY_CLIENT_ID=deine_client_id
SPOTIFY_CLIENT_SECRET=dein_client_secret
SPOTIFY_REFRESH_TOKEN=dein_refresh_token
SPOTIFY_USERNAME=dein_username
```

### 8. Lokale Entwicklungseinrichtung

Praktische Aliase zur `.bashrc` hinzufügen:

```bash
echo "alias restart-app='sudo systemctl restart spotipi.service'" >> ~/.bashrc
echo "alias status-app='sudo systemctl status spotipi.service'" >> ~/.bashrc
echo "alias logs-app='sudo journalctl -u spotipi.service -f'" >> ~/.bashrc
echo "alias deploy-log='tail -f /home/pi/deploy.log'" >> ~/.bashrc
source ~/.bashrc
```

---

## 🔄 Git Hook Deployment

### Wie es funktioniert

1. **Entwickler pusht** Code zum Bare Repository
2. **post-receive Hook** wird automatisch ausgelöst
3. **Code wird ausgecheckt** in das Arbeitsverzeichnis
4. **Abhängigkeiten** werden bei Bedarf aktualisiert
5. **Service startet neu** automatisch
6. **App ist live** innerhalb von Sekunden

### Hook Features

- ✅ **Automatisches Code-Deployment**
- ✅ **Intelligente Abhängigkeitsverwaltung** (nur wenn requirements.txt sich ändert)
- ✅ **Service-Neustart** mit Fehlerbehandlung
- ✅ **Umfassendes Logging** mit Zeitstempel und Emojis
- ✅ **Fehlererkennung** und Berichterstattung

### Deployment Befehle (vom Mac)

```bash
# Deployment zur Produktion
git push prod master

# Deployment zur Entwicklung
git push dev master

# Deployment Status prüfen
ssh pi@spotipi.local "tail -20 /home/pi/deploy.log"
```

---

## 🔧 Service Verwaltung

### Service Befehle

```bash
# Service starten
sudo systemctl start spotipi.service

# Service stoppen
sudo systemctl stop spotipi.service

# Service neustarten (Hauptbefehl)
sudo systemctl restart spotipi.service
# oder Alias verwenden:
restart-app

# Status prüfen
sudo systemctl status spotipi.service
# oder Alias verwenden:
status-app

# Logs anzeigen
sudo journalctl -u spotipi.service -f
# oder Alias verwenden:
logs-app

# Auto-Start beim Systemstart aktivieren
sudo systemctl enable spotipi.service
```

### Log Dateien

| Datei | Zweck | Pfad |
|-------|-------|------|
| `deploy.log` | Git Deployment Logs | `/home/pi/deploy.log` |
| `web.log` | Anwendung stdout/stderr | `/home/pi/web.log` |
| `systemd logs` | Service Verwaltung | `journalctl -u spotipi.service` |

---

## 🐛 Fehlerbehebung

### Häufige Probleme

#### Service startet nicht
```bash
# Service Status prüfen
sudo systemctl status spotipi.service

# Detaillierte Logs prüfen
sudo journalctl -u spotipi.service -f

# Python Umgebung überprüfen
ls -la /home/pi/spotipi/venv/bin/python
```

#### Deployment schlägt fehl
```bash
# Deployment Log prüfen
tail -50 /home/pi/deploy.log

# Git Hook Berechtigungen überprüfen
ls -la /home/pi/repo.git/hooks/post-receive

# Manuelles Deployment testen
cd /home/pi/spotipi
git pull
```

#### Umgebungsprobleme
```bash
# .env Datei überprüfen
cat /home/pi/.spotipi/.env

# Dateiberechtigungen prüfen
ls -la /home/pi/.spotipi/.env

# Python Imports testen
cd /home/pi/spotipi
venv/bin/python -c "import src.app"
```

### Debug Befehle

```bash
# Service Status Übersicht
systemctl --user status spotipi.service

# Festplattenspeicher prüfen
df -h

# Speicherverbrauch
free -h

# Prozess prüfen
ps aux | grep python

# Netzwerkverbindung
curl -I http://localhost:5000
```

---

## 🔄 Wartung

### Regelmäßige Aufgaben

#### Wöchentlich
```bash
# Systempakete aktualisieren
sudo apt update && sudo apt upgrade -y

# Log-Dateigrößen prüfen
du -sh /home/pi/*.log

# Service-Gesundheit überprüfen
sudo systemctl status spotipi.service
```

#### Monatlich
```bash
# Große Log-Dateien rotieren
sudo logrotate -f /etc/logrotate.conf

# Verfügbaren Festplattenspeicher prüfen
df -h

# Konfiguration sichern
cp /home/pi/.spotipi/.env /home/pi/.env.backup
```

### Backup Strategie

#### Konfiguration Backup
```bash
#!/bin/bash
# backup.sh
BACKUP_DIR="/home/pi/backups/$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"

# Kritische Dateien sichern
cp /home/pi/.spotipi/.env "$BACKUP_DIR/"
cp /etc/systemd/system/spotipi.service "$BACKUP_DIR/"
cp /home/pi/repo.git/hooks/post-receive "$BACKUP_DIR/"

echo "Backup abgeschlossen: $BACKUP_DIR"
```

#### Datenbank/Konfig Export
```bash
# Aktuelle Konfiguration exportieren
python3 -c "
import json
from src.api.spotify import load_config
config = load_config()
print(json.dumps(config, indent=2))
" > config_backup.json
```

### Updates und Upgrades

#### Anwendung aktualisieren
```bash
# Vom Mac - normales Deployment
git push prod master

# Manuelles Update auf Pi
cd /home/pi/spotipi
git pull origin master
venv/bin/pip install -r requirements.txt
sudo systemctl restart spotipi.service
```

#### Python Abhängigkeiten aktualisieren
```bash
cd /home/pi/spotipi
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt --upgrade
```

---

## 📚 Zusätzliche Ressourcen

### Nützliche Befehle Referenz

```bash
# Schneller Deployment Status
ssh pi@spotipi.local "systemctl is-active spotipi.service && tail -5 /home/pi/deploy.log"

# Remote Neustart
ssh pi@spotipi.local "sudo systemctl restart spotipi.service"

# App Erreichbarkeit prüfen
curl -s -o /dev/null -w "%{http_code}" http://spotipi.local:5000

# Git Repository Größe
du -sh /home/pi/repo.git /home/pi/spotipi
```

### Netzwerk Konfiguration

#### Zugriffspunkte
- **Entwicklung**: `http://spotipi.local:5000`
- **Lokale IP**: `http://192.168.x.x:5000`
- **SSH Zugriff**: `ssh pi@spotipi.local`

#### Firewall (falls aktiviert)
```bash
sudo ufw allow 5000/tcp
sudo ufw allow 22/tcp
sudo ufw enable
```

---

## 🎯 Schnellstart Zusammenfassung

Für erfahrene Benutzer, die das Setup erneut benötigen:

```bash
# 1. Raspberry Pi Setup
sudo apt install -y git python3 python3-pip python3-venv
git init --bare /home/pi/repo.git

# 2. Arbeitsverzeichnis erstellen
mkdir -p /home/pi/spotipi
cd /home/pi/spotipi
python3 -m venv venv

# 3. Post-receive Hook installieren (siehe Abschnitt 4)
# 4. Systemd Service erstellen (siehe Abschnitt 5)  
# 5. Sudoers konfigurieren (siehe Abschnitt 6)
# 6. Git Remote auf Mac hinzufügen und pushen

# Bereit zum Loslegen! 🚀
```

---

**Zuletzt aktualisiert**: 15. August 2025  
**Version**: 1.0.0  
**Betreuer**: SpotiPi Entwicklungsteam
