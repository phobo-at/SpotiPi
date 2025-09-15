#!/bin/bash
#
# 🚀 Deploy SpotiPi to Raspberry Pi - Path-Agnostic Version
# Synchronizes local code changes to the Pi with detailed logging
# 
# Features:
# - Auto-detects local and remote paths
# - Configurable via environment variables
# - Maintains backward compatibility

# 🔧 Configuration with smart defaults
PI_HOST="${SPOTIPI_PI_HOST:-pi@spotipi.local}"
APP_NAME="${SPOTIPI_APP_NAME:-spotipi}"

# Auto-detect local path (where this script is located)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_LOCAL_PATH="$(dirname "$SCRIPT_DIR")"

# Allow override via environment
LOCAL_PATH="${SPOTIPI_LOCAL_PATH:-$DEFAULT_LOCAL_PATH}"

# Auto-detect remote path  
PI_PATH="${SPOTIPI_PI_PATH:-/home/pi/$APP_NAME}"

echo "🚀 Deploying SpotiPi to Raspberry Pi..."
echo "📁 Local path: $LOCAL_PATH"
echo "🌐 Remote: $PI_HOST:$PI_PATH"

# Verify local path exists
if [ ! -d "$LOCAL_PATH" ]; then
    echo "❌ Local path does not exist: $LOCAL_PATH"
    echo "💡 Set SPOTIPI_LOCAL_PATH environment variable or run from correct location"
    exit 1
fi

# Verify we have the expected SpotiPi structure
if [ ! -f "$LOCAL_PATH/run.py" ] || [ ! -d "$LOCAL_PATH/src" ]; then
    echo "❌ This doesn't look like a SpotiPi project directory: $LOCAL_PATH"
    echo "💡 Expected run.py and src/ directory"
    exit 1
fi

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
    
    # Restart service on Pi (path-agnostic)
    SERVICE_NAME="${SPOTIPI_SERVICE_NAME:-spotify-web.service}"
    echo "🔄 Restarting service: $SERVICE_NAME"
    ssh "$PI_HOST" "sudo systemctl restart $SERVICE_NAME"
    
    if [ $? -eq 0 ]; then
        echo "✅ Service restarted successfully"
        echo "🎵 SpotiPi deployment complete!"
        echo "🌐 Access: http://spotipi.local:5000"
        
        # Optional: Show service status
        if [ "${SPOTIPI_SHOW_STATUS:-}" = "1" ]; then
            echo ""
            echo "📊 Service Status:"
            ssh "$PI_HOST" "sudo systemctl status $SERVICE_NAME --no-pager -l"
        fi
    else
        echo "❌ Failed to restart service"
        echo "💡 Check service status: ssh $PI_HOST 'sudo systemctl status $SERVICE_NAME'"
    fi
else
    echo "❌ Failed to sync code"
    rm -f /tmp/rsync_output.log /tmp/rsync_deletions.log
    exit 1
fi