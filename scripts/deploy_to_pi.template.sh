#!/bin/bash
#
# 🚀 Deploy SpotiPi to Raspberry Pi  
# Synchronizes local code changes to the Pi with detailed logging
#
# 📝 SETUP INSTRUCTIONS:
# 1. Copy this file to deploy_to_pi.sh
# 2. Update the variables below with your specific configuration
# 3. Make sure you have SSH key access to your Pi
# 4. Test the connection: ssh <YOUR_PI_USER>@<YOUR_PI_HOST> "echo 'Connection OK'"

# 🔧 CONFIGURATION - UPDATE THESE VALUES
PI_HOST="<YOUR_PI_USER>@<YOUR_PI_HOSTNAME_OR_IP>"     # e.g., "pi@raspberrypi.local" or "pi@192.168.1.100"
PI_PATH="/home/<YOUR_PI_USER>/<YOUR_PROJECT_FOLDER>"  # e.g., "/home/pi/spotipi"
LOCAL_PATH="<YOUR_LOCAL_PROJECT_PATH>"                # e.g., "/Users/yourname/projects/spotipi"

echo "🚀 Deploying SpotiPi to Raspberry Pi..."

# Sync code with detailed logging
echo "📋 Synchronizing files to Pi..."

# First, check what would be deleted with a dry run
echo "🔍 Checking for deletions..."
rsync -av \
  --delete \
  --dry-run \
  --itemize-changes \
  --exclude='.git' \
  --exclude='.env' \
  --exclude='venv/' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='.DS_Store' \
  --exclude='node_modules/' \
  --exclude='logs/' \
  --exclude='*.log' \
  --exclude='tests/' \
  --exclude='docs/' \
  --exclude='.pytest_cache/' \
  --exclude='*.egg-info/' \
  "$LOCAL_PATH/" "$PI_HOST:$PI_PATH/" 2>&1 | grep "deleting\|*deleting" > /tmp/rsync_deletions.log

# Now do the actual sync
rsync -av \
  --delete \
  --exclude='.git' \
  --exclude='.env' \
  --exclude='venv/' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='.DS_Store' \
  --exclude='node_modules/' \
  --exclude='logs/' \
  --exclude='*.log' \
  --exclude='tests/' \
  --exclude='docs/' \
  --exclude='.pytest_cache/' \
  --exclude='*.egg-info/' \
  "$LOCAL_PATH/" "$PI_HOST:$PI_PATH/" 2>&1 | tee /tmp/rsync_output.log

if [ $? -eq 0 ]; then
    echo ""
    echo "📊 Deployment Summary:"
    echo "======================"
    
    # Parse the output for changes
    TRANSFERRED=$(grep -A 1000 "Transfer starting" /tmp/rsync_output.log | grep -v "Transfer starting" | grep -v "sent\|received\|total size\|speedup" | grep -E "^[^d].*" | grep -v "/$" | wc -l | tr -d ' ')
    DELETED=$(wc -l < /tmp/rsync_deletions.log | tr -d ' ')
    
    echo "📁 Files transferred: $TRANSFERRED"
    echo "🗑️  Files deleted: $DELETED"
    
    # Show deleted files
    if [ "$DELETED" -gt 0 ]; then
        echo ""
        echo "🗑️  Deleted from Pi:"
        cat /tmp/rsync_deletions.log | sed 's/.*deleting /   ❌ /'
    fi
    
    # Show transferred files (limit to avoid spam)
    if [ "$TRANSFERRED" -gt 0 ]; then
        echo ""
        echo "📁 Transferred to Pi:"
        grep -A 1000 "Transfer starting" /tmp/rsync_output.log | \
            grep -v "Transfer starting" | \
            grep -v "sent\|received\|total size\|speedup" | \
            grep -E "^[^d].*" | \
            grep -v "/$" | \
            head -10 | \
            sed 's/^/   ✅ /'
        
        if [ "$TRANSFERRED" -gt 10 ]; then
            echo "   ... and $(($TRANSFERRED - 10)) more files"
        fi
    fi
    
    # Clean up
    rm -f /tmp/rsync_output.log /tmp/rsync_deletions.log
    
    echo ""
    echo "✅ Code synchronized successfully"
    
    # 🔧 OPTIONAL: Restart service on Pi (uncomment and customize if needed)
    # echo "🔄 Restarting service on Pi..."
    # ssh "$PI_HOST" "sudo systemctl restart <YOUR_SERVICE_NAME>.service"
    # 
    # if [ $? -eq 0 ]; then
    #     echo "✅ Service restarted successfully"
    #     echo "🎵 SpotiPi deployment complete!"
    #     echo "🌐 Access: http://<YOUR_PI_HOSTNAME>:<YOUR_PORT>"
    # else
    #     echo "❌ Failed to restart service"
    # fi
    
    echo "🎵 Deployment complete!"
    echo "🌐 Access your Pi at: http://<YOUR_PI_HOSTNAME>:<YOUR_PORT>"
    
else
    echo "❌ Failed to sync code"
    rm -f /tmp/rsync_output.log /tmp/rsync_deletions.log
fi

# 📋 USAGE EXAMPLES:
# 
# Basic setup:
# PI_HOST="pi@raspberrypi.local"
# PI_PATH="/home/pi/my_project"  
# LOCAL_PATH="/Users/myname/projects/my_project"
#
# With custom SSH port:
# PI_HOST="pi@192.168.1.100 -p 2222"
#
# With different user:
# PI_HOST="myuser@my-pi.local"
# PI_PATH="/home/myuser/my_project"
