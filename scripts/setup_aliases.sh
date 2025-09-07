#!/usr/bin/env zsh
#
# 🔧 SpotiPi Development Setup Script
# Adds convenient zsh aliases for managing the development server
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ZSHRC_FILE="$HOME/.zshrc"

echo "🎵 SpotiPi Development Setup"
echo "========================================"

# Create backup of .zshrc
if [[ -f "$ZSHRC_FILE" ]]; then
    cp "$ZSHRC_FILE" "$ZSHRC_FILE.backup.$(date +%Y%m%d_%H%M%S)"
    echo "✅ Created backup of .zshrc"
fi

# Check if aliases already exist
if grep -q "spotipi-start" "$ZSHRC_FILE" 2>/dev/null; then
    echo "⚠️  SpotiPi aliases already exist in .zshrc"
    echo "💡 Remove existing aliases first or edit manually"
    exit 1
fi

# Add aliases to .zshrc
echo "" >> "$ZSHRC_FILE"
echo "# SpotiPi Development Server Aliases" >> "$ZSHRC_FILE"
echo "alias spotipi-start='cd $SCRIPT_DIR && ./spotipi_dev.py start'" >> "$ZSHRC_FILE"
echo "alias spotipi-stop='cd $SCRIPT_DIR && ./spotipi_dev.py stop'" >> "$ZSHRC_FILE"
echo "alias spotipi-status='cd $SCRIPT_DIR && ./spotipi_dev.py status'" >> "$ZSHRC_FILE"
echo "alias spotipi-logs='cd $SCRIPT_DIR && ./spotipi_dev.py logs'" >> "$ZSHRC_FILE"
echo "alias spotipi-restart='cd $SCRIPT_DIR && ./spotipi_dev.py stop && sleep 2 && ./spotipi_dev.py start'" >> "$ZSHRC_FILE"

echo "✅ Added SpotiPi aliases to .zshrc"
echo ""
echo "🚀 Available commands after restarting your terminal:"
echo "   spotipi-start   # Start development server"
echo "   spotipi-stop    # Stop development server"
echo "   spotipi-status  # Show server status"
echo "   spotipi-logs    # Show recent logs"
echo "   spotipi-restart # Stop and restart server"
echo ""
echo "🔄 To use immediately, run: source ~/.zshrc"
echo "💡 Or restart your terminal"
echo ""
echo "📝 Alternative: You can also source scripts/spotipi.zsh for advanced functions"
