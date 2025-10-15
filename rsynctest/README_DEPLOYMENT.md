# 🚀 Raspberry Pi Deployment Script

This directory contains a deployment script template for automatically synchronizing your local SpotiPi code to a Raspberry Pi.

## 📁 Files

- `deploy_to_pi.template.sh` - **Generic template**

## 🛠️ Setup Instructions

### 1. Copy the template
```bash
cp scripts/deploy_to_pi.template.sh scripts/deploy_to_pi.sh
```

### 2. Configure your Pi settings
Edit `scripts/deploy_to_pi.sh` and update these variables:

```bash
# Update these with your specific configuration
PI_HOST="pi@raspberrypi.local"              # Your Pi's hostname or IP
PI_PATH="/home/pi/spotipi"            # Project path on Pi
LOCAL_PATH="/Users/yourname/projects/..."    # Your local project path
```

### 3. Test SSH connection
```bash
ssh pi@raspberrypi.local "echo 'Connection OK'"
```

### 4. Make executable and test
```bash
chmod +x scripts/deploy_to_pi.sh
scripts/deploy_to_pi.sh
```

## ✨ Features

- **📁 Syncs all code changes** to your Pi
- **🗑️ Removes deleted files** from Pi automatically  
- **📊 Detailed logging** shows what was transferred/deleted
- **🔄 Optional service restart** (customize as needed)
- **🚀 Fast incremental transfers** with rsync

## 📋 Example Output

```
🚀 Deploying SpotiPi to Raspberry Pi...
📋 Synchronizing files to Pi...
🔍 Checking for deletions...

📊 Deployment Summary:
======================
📁 Files transferred: 3
🗑️  Files deleted: 1

🗑️  Deleted from Pi:
   ❌ scripts/old_file.py

📁 Transferred to Pi:
   ✅ src/app.py
   ✅ scripts/deploy_to_pi.sh
   ✅ static/css/style.css

✅ Code synchronized successfully
🎵 Deployment complete!
```

## 🔧 Customization

You can customize:
- **Excluded files/folders** in the `--exclude` patterns
- **Service restart commands** (uncomment in script)
- **Target directories** and hostnames
- **SSH options** (ports, keys, etc.)

## 📝 Notes

- Uses `rsync` for efficient incremental transfers
- Preserves file permissions and timestamps
- Automatically excludes common files (`.git`, `venv/`, logs, etc.)
- Safe deletion with dry-run checks first
