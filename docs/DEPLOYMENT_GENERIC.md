# 🚀 SpotiPi Deployment Guide (Generic)

Comprehensive guide for setting up and managing SpotiPi deployment on Raspberry Pi or Linux servers.

## 📋 Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Complete Setup from Scratch](#complete-setup-from-scratch)
4. [Git Hook Deployment](#git-hook-deployment)
5. [Service Management](#service-management)
6. [Troubleshooting](#troubleshooting)
7. [Maintenance](#maintenance)

---

## 🏗️ Overview

### Architecture
```
Development Machine         Raspberry Pi / Linux Server
├── /path/to/spotipi/       ├── /home/pi/spotipi-repo.git (bare repo)
│   └── spotify_wakeup      ├── /home/pi/spotipi-app (app)
│                           └── systemd service (spotipi.service)
```

### Deployment Flow
1. **Develop** on local machine
2. **Push** via `git push production master`
3. **Auto-deploy** via Git post-receive hook
4. **Auto-restart** systemd service
5. **Ready** at `http://your-pi-ip:5000`

---

## 📋 Prerequisites

### Raspberry Pi / Linux Server
- **Operating System**: Raspberry Pi OS or Ubuntu/Debian
- **SSH Access**: Enabled and accessible
- **User**: With sudo privileges (default `pi` on Raspberry Pi)
- **Network**: Stable internet connection

### Development Machine
- **Git**: Installed and configured
- **SSH**: Access to the server
- **Text Editor**: For configuration files

### Spotify Credentials
- **Spotify Developer App**: Created at https://developer.spotify.com
- **Client ID**: From the Spotify App
- **Client Secret**: From the Spotify App
- **Refresh Token**: Obtained via OAuth2 flow

---

## 🛠️ Complete Setup from Scratch

### 1. Server Preparation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y git python3 python3-pip python3-venv nginx

# Create user (if not exists)
# sudo useradd -m -s /bin/bash pi
# sudo usermod -aG sudo pi
```

### 2. Application Directory Setup

```bash
# Create application directory
sudo mkdir -p /home/pi/spotipi-app
sudo chown pi:pi /home/pi/spotipi-app

# Create virtual environment
cd /home/pi/spotipi-app
python3 -m venv venv
source venv/bin/activate

# Install base dependencies
pip install flask requests python-dotenv psutil
```

### 3. Git Repository Setup

```bash
# Create bare Git repository for deployment
cd /home/pi
git init --bare spotipi-repo.git

# Set ownership
sudo chown -R pi:pi /home/pi/spotipi-repo.git
```

### 4. Git Hook Configuration

Create the post-receive hook:

```bash
cat > /home/pi/spotipi-repo.git/hooks/post-receive << 'EOF'
#!/bin/bash

DEPLOY_DIR="/home/pi/spotipi-app"
REPO_DIR="/home/pi/spotipi-repo.git"
LOGFILE="/home/pi/deploy.log"

echo "[$(date)] 🚀 Deployment started via post-receive" >> "$LOGFILE"

# Checkout code
cd "$DEPLOY_DIR" || {
    echo "[$(date)] ❌ ERROR: Cannot cd to $DEPLOY_DIR" >> "$LOGFILE"
    exit 1
}

echo "[$(date)] 📥 Checking out latest code..." >> "$LOGFILE"
GIT_DIR="$REPO_DIR" GIT_WORK_TREE="$DEPLOY_DIR" git checkout -f master >> "$LOGFILE" 2>&1

# Check if requirements.txt changed
if git diff --name-only HEAD@{1} HEAD 2>/dev/null | grep -q "requirements.txt"; then
    echo "[$(date)] 📦 requirements.txt changed, updating dependencies..." >> "$LOGFILE"
    /home/pi/spotipi-app/venv/bin/pip install -r requirements.txt >> "$LOGFILE" 2>&1
else
    echo "[$(date)] ⏭️  No dependency changes detected" >> "$LOGFILE"
fi

# Restart app
echo "[$(date)] 🔄 Restarting spotipi.service..." >> "$LOGFILE"
sudo systemctl restart spotipi.service >> "$LOGFILE" 2>&1

if [ $? -eq 0 ]; then
    echo "[$(date)] ✅ Deployment complete! Service restarted successfully." >> "$LOGFILE"
else
    echo "[$(date)] ❌ ERROR: Service restart failed!" >> "$LOGFILE"
fi

echo "[$(date)] 📱 App should be available at http://$(hostname -I | awk '{print $1}'):5000" >> "$LOGFILE"
EOF

# Make hook executable
chmod +x /home/pi/spotipi-repo.git/hooks/post-receive
```

### 5. Systemd Service Setup

Create the service file:

```bash
sudo tee /etc/systemd/system/spotipi.service << 'EOF'
[Unit]
Description=SpotiPi Web Application
After=network.target

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/home/pi/spotipi-app
Environment=PATH=/home/pi/spotipi-app/venv/bin
ExecStart=/home/pi/spotipi-app/venv/bin/python run.py
Restart=always
RestartSec=10

# Logging
StandardOutput=append:/home/pi/spotipi.log
StandardError=append:/home/pi/spotipi.log

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable spotipi.service
sudo systemctl start spotipi.service
```

### 6. Configure Sudoers for Service Management

Allow user to restart the service without password:

```bash
sudo tee /etc/sudoers.d/spotipi << 'EOF'
pi ALL=(ALL) NOPASSWD: /bin/systemctl restart spotipi.service
pi ALL=(ALL) NOPASSWD: /bin/systemctl start spotipi.service
pi ALL=(ALL) NOPASSWD: /bin/systemctl stop spotipi.service
pi ALL=(ALL) NOPASSWD: /bin/systemctl status spotipi.service
EOF
```

### 7. Environment Configuration

```bash
# Create environment file
touch /home/pi/spotipi-app/.env

# Add Spotify credentials
nano /home/pi/spotipi-app/.env
```

Content of `.env` (replace with your values):
```
SPOTIFY_CLIENT_ID=your_client_id_here
SPOTIFY_CLIENT_SECRET=your_client_secret_here
SPOTIFY_REFRESH_TOKEN=your_refresh_token_here
SPOTIFY_USERNAME=your_spotify_username_here
```

### 8. Local Development Setup

Add convenient aliases to `.bashrc`:

```bash
echo "alias restart-spotipi='sudo systemctl restart spotipi.service'" >> ~/.bashrc
echo "alias status-spotipi='sudo systemctl status spotipi.service'" >> ~/.bashrc
echo "alias logs-spotipi='sudo journalctl -u spotipi.service -f'" >> ~/.bashrc
echo "alias deploy-log='tail -f /home/pi/deploy.log'" >> ~/.bashrc
source ~/.bashrc
```

### 9. Setup Git Remote on Development Machine

On your development machine (in the SpotiPi project directory):

```bash
# Add Git remote (adjust IP address)
git remote add production pi@192.168.1.100:/home/pi/spotipi-repo.git

# Or with hostname (if mDNS works)
git remote add production pi@raspberrypi.local:/home/pi/spotipi-repo.git

# First deployment
git push production master
```

---

## 🔄 Git Hook Deployment

### How It Works

1. **Developer pushes** code to bare repository
2. **post-receive hook** triggers automatically
3. **Code is checked out** to working directory
4. **Dependencies** are updated if needed
5. **Service restarts** automatically
6. **App is live** within seconds

### Hook Features

- ✅ **Automatic code deployment**
- ✅ **Smart dependency management** (only when requirements.txt changes)
- ✅ **Service restart** with error handling
- ✅ **Comprehensive logging** with timestamps and emojis
- ✅ **Error detection** and reporting

### Deployment Commands (from development machine)

```bash
# Deploy to production
git push production master

# Check deployment status
ssh pi@your-server-ip "tail -20 /home/pi/deploy.log"

# Remote service status
ssh pi@your-server-ip "sudo systemctl status spotipi.service"
```

---

## 🔧 Service Management

### Service Commands

```bash
# Start service
sudo systemctl start spotipi.service

# Stop service
sudo systemctl stop spotipi.service

# Restart service (main command)
sudo systemctl restart spotipi.service
# or use alias:
restart-spotipi

# Check status
sudo systemctl status spotipi.service
# or use alias:
status-spotipi

# View logs
sudo journalctl -u spotipi.service -f
# or use alias:
logs-spotipi

# Enable auto-start on boot
sudo systemctl enable spotipi.service
```

### Log Files

| File | Purpose | Location |
|------|---------|----------|
| `deploy.log` | Git deployment logs | `/home/pi/deploy.log` |
| `spotipi.log` | Application stdout/stderr | `/home/pi/spotipi.log` |
| `systemd logs` | Service management | `journalctl -u spotipi.service` |

---

## 🐛 Troubleshooting

### Common Issues

#### Service Won't Start
```bash
# Check service status
sudo systemctl status spotipi.service

# Check detailed logs
sudo journalctl -u spotipi.service -f

# Verify Python environment
ls -la /home/pi/spotipi-app/venv/bin/python
```

#### Deployment Fails
```bash
# Check deployment log
tail -50 /home/pi/deploy.log

# Verify Git hook permissions
ls -la /home/pi/spotipi-repo.git/hooks/post-receive

# Test manual deployment
cd /home/pi/spotipi-app
git pull
```

#### Environment Issues
```bash
# Verify .env file
cat /home/pi/spotipi-app/.env

# Check file permissions
ls -la /home/pi/spotipi-app/.env

# Test Python imports
cd /home/pi/spotipi-app
venv/bin/python -c "import src.app"
```

#### SSH Connection Problems
```bash
# Test SSH connection
ssh pi@your-server-ip "echo 'Connection OK'"

# Use SSH keys (recommended)
ssh-copy-id pi@your-server-ip

# Test Git over SSH
git ls-remote production
```

### Debug Commands

```bash
# Service status overview
systemctl --user status spotipi.service

# Disk space check
df -h

# Memory usage
free -h

# Process check
ps aux | grep python

# Network connectivity
curl -I http://localhost:5000

# Port availability check
sudo netstat -tlnp | grep :5000
```

---

## 🔄 Maintenance

### Regular Tasks

#### Weekly
```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Check log file sizes
du -sh /home/pi/*.log

# Verify service health
sudo systemctl status spotipi.service
```

#### Monthly
```bash
# Rotate large log files
sudo logrotate -f /etc/logrotate.conf

# Check available disk space
df -h

# Backup configuration
cp /home/pi/spotipi-app/.env /home/pi/.env.backup
```

### Backup Strategy

#### Configuration Backup
```bash
#!/bin/bash
# backup.sh
BACKUP_DIR="/home/pi/backups/$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"

# Backup critical files
cp /home/pi/spotipi-app/.env "$BACKUP_DIR/"
cp /etc/systemd/system/spotipi.service "$BACKUP_DIR/"
cp /home/pi/spotipi-repo.git/hooks/post-receive "$BACKUP_DIR/"

echo "Backup completed: $BACKUP_DIR"
```

#### Configuration Export
```bash
# Export current configuration
python3 -c "
import json
from src.api.spotify import load_config
config = load_config()
print(json.dumps(config, indent=2))
" > config_backup.json
```

### Updates and Upgrades

#### Update Application
```bash
# From development machine - normal deployment
git push production master

# Manual update on server
cd /home/pi/spotipi-app
git pull origin master
venv/bin/pip install -r requirements.txt
sudo systemctl restart spotipi.service
```

#### Update Python Dependencies
```bash
cd /home/pi/spotipi-app
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt --upgrade
```

---

## 📚 Additional Resources

### Useful Commands Reference

```bash
# Quick deployment status
ssh pi@your-server-ip "systemctl is-active spotipi.service && tail -5 /home/pi/deploy.log"

# Remote restart
ssh pi@your-server-ip "sudo systemctl restart spotipi.service"

# Check app accessibility
curl -s -o /dev/null -w "%{http_code}" http://your-server-ip:5000

# Git repository size
du -sh /home/pi/spotipi-repo.git /home/pi/spotipi-app

# Find server IP address
hostname -I
```

### Network Configuration

#### Access Points
- **Local IP**: `http://192.168.x.x:5000`
- **Hostname**: `http://raspberrypi.local:5000` (with mDNS)
- **SSH Access**: `ssh pi@raspberrypi.local` or `ssh pi@192.168.x.x`

#### Firewall (if enabled)
```bash
sudo ufw allow 5000/tcp
sudo ufw allow 22/tcp
sudo ufw enable
```

#### Port Forwarding (Router)
For external access:
- **Internal Port**: 5000
- **External Port**: Your choice (e.g. 8080)
- **Protocol**: TCP

---

## 🎯 Quick Start Summary

For experienced users who need quick setup:

```bash
# 1. Server setup
sudo apt install -y git python3 python3-pip python3-venv
git init --bare /home/pi/spotipi-repo.git

# 2. Create working directory
mkdir -p /home/pi/spotipi-app
cd /home/pi/spotipi-app
python3 -m venv venv

# 3. Install post-receive hook (see section 4)
# 4. Create systemd service (see section 5)  
# 5. Configure sudoers (see section 6)
# 6. Create .env file with Spotify credentials (see section 7)
# 7. Add Git remote on development machine and push (see section 9)

# Ready to go! 🚀
```

### Customizations for Your Setup

**Adjust paths:**
- `/home/pi/` → Your user path
- `pi` → Your username
- `192.168.x.x` → Your server IP

**Adjust service names:**
- `spotipi.service` → Your desired service name
- Adjust repository names accordingly

**Adjust network:**
- Set up SSH keys for secure connection
- Configure firewall rules as needed
- Use port 5000 or another port

---

**Last Updated**: August 15, 2025  
**Version**: 1.0.0  
**License**: MIT License
