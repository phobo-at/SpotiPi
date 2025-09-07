#!/usr/bin/env zsh

# SpotiPi Development Server Commands
# Source this file or add these to your .zshrc

SPOTIPI_DIR="/Users/michi/spotipi-dev/spotify_wakeup"

# Function to run SpotiPi commands
spotipi() {
    case "$1" in
        start)
            echo "🚀 Starting SpotiPi development server..."
            cd "$SPOTIPI_DIR" && ./spotipi_dev.py start
            ;;
        stop)
            echo "🛑 Stopping SpotiPi development server..."
            cd "$SPOTIPI_DIR" && ./spotipi_dev.py stop
            ;;
        status)
            cd "$SPOTIPI_DIR" && ./spotipi_dev.py status
            ;;
        logs)
            echo "📄 Showing SpotiPi development server logs..."
            cd "$SPOTIPI_DIR" && ./spotipi_dev.py logs
            ;;
        restart)
            echo "🔄 Restarting SpotiPi development server..."
            cd "$SPOTIPI_DIR" && ./spotipi_dev.py stop
            echo "🧹 Cleaned up remaining processes on port 5001"
            sleep 3
            echo "🎵 Starting SpotiPi Development Server from $SPOTIPI_DIR..."
            cd "$SPOTIPI_DIR" && ./spotipi_dev.py start
            ;;
        *)
            echo "🎵 SpotiPi Development Server"
            echo ""
            echo "Usage: spotipi <command>"
            echo ""
            echo "Commands:"
            echo "  start    - Start server (simple method)"
            echo "  stop     - Stop server"
            echo "  restart  - Stop and start server"
            echo "  status   - Show server status"
            echo "  logs     - Show recent logs"
            ;;
    esac
}

# Individual aliases for convenience
alias spotipi-start='spotipi start'
alias spotipi-stop='spotipi stop'
alias spotipi-status='spotipi status'
alias spotipi-logs='spotipi logs'
alias spotipi-restart='spotipi restart'

echo "✅ SpotiPi zsh commands loaded!"
echo "💡 Use: spotipi start|stop|status|logs|restart"
echo "💡 Or use aliases: spotipi-start, spotipi-stop, etc."
