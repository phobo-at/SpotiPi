#!/usr/bin/env python3
"""
🔧 SpotiPi Development Management Script
Simple commands to start, stop, and monitor the development server
"""

import subprocess
import sys
import os
import signal
import time
from pathlib import Path

def get_pid_file():
    """Get the PID file path"""
    return Path.home() / ".spotify_wakeup" / "dev_server.pid"

def is_server_running():
    """Check if the development server is running"""
    pid_file = get_pid_file()
    if not pid_file.exists():
        return False
    
    try:
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
        
        # Check if process exists
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        # Process doesn't exist, clean up stale PID file
        pid_file.unlink(missing_ok=True)
        return False

def stop_server():
    """Stop the development server"""
    print("🛑 Stopping SpotiPi Development Server...")
    pid_file = get_pid_file()
    stopped = False
    
    # Stop main server
    if pid_file.exists():
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            os.kill(pid, signal.SIGTERM)
            print(f"🛑 Stopped development server (PID: {pid})")
            pid_file.unlink(missing_ok=True)
            stopped = True
        except (OSError, ValueError):
            pid_file.unlink(missing_ok=True)
    
    # Cleanup: kill any processes using port 5001
    try:
        result = subprocess.run(['lsof', '-ti', ':5001'], 
                              capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                try:
                    os.kill(int(pid), signal.SIGTERM)
                    print(f"🧹 Cleaned up remaining processes on port 5001")
                    stopped = True
                except (OSError, ValueError):
                    pass
    except Exception:
        pass
    
    if stopped:
        print("✅ Server stopped successfully")
    else:
        print("ℹ️  No development server was running")
    
    return True

def start_server():
    """Start the development server using the new simple method"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    if is_server_running():
        print("🚨 Development server is already running")
        print("💡 Use 'spotipi stop' to stop it first")
        return False
    
    print("🔄 Restarting SpotiPi development server...")
    print("🛑 Stopping SpotiPi Development Server...")
    print("🧹 Cleaned up remaining processes on port 5001")
    print("🎵 Starting SpotiPi Development Server...")
    print("🚀 Starting development server...")
    print("📍 URL: http://localhost:5001")
    print("🔄 Auto-reload: ENABLED")
    print("🐛 Debug mode: ENABLED")
    print("⚠️  Server will run in background")
    print("=" * 40)
    
    try:
        # Start Flask app with new arguments
        process = subprocess.Popen(
            [sys.executable, 'app.py', '--dev', '--port', '5001'],
            cwd=script_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True  # Detach from parent
        )
        
        # Save PID for management
        pid_file = get_pid_file()
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        with open(pid_file, 'w') as f:
            f.write(str(process.pid))
        
        # Wait a moment and check if it started successfully
        time.sleep(3)
        if is_server_running():
            print("✅ Development server started successfully!")
            print(f"📋 Process ID: {process.pid}")
            print("📍 Server URL: http://localhost:5001")
            print(f"📄 PID file: {pid_file}")
            print()
            print("🔧 Management commands:")
            print("   Stop server: spotipi stop")
            print("   Check status: spotipi status")
            print("   View logs: spotipi logs")
            print()
            print("🎉 Server is running in background!")
            return True
        else:
            print("❌ Server failed to start")
            return False
            
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        return False

def status():
    """Show status of the development server"""
    print("🔍 Checking SpotiPi development server status...")
    
    if is_server_running():
        pid_file = get_pid_file()
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
        print("✅ Development server is running")
        print(f"📋 Process ID: {pid}")
        print("📍 URL: http://localhost:5001")
    else:
        print("❌ Development server is not running")
    
    # Show log locations
    log_dir = Path.home() / ".spotify_wakeup" / "logs"
    if log_dir.exists() and any(log_dir.glob("*.log")):
        print()
        print("📄 Available logs:")
        for log_file in sorted(log_dir.glob("*.log")):
            size = log_file.stat().st_size
            print(f"   {log_file.name} ({size} bytes)")
    
    return is_server_running()

def logs():
    """Show recent log entries"""
    log_file = Path.home() / ".spotify_wakeup" / "logs" / "spotipi.log"
    
    if not log_file.exists():
        print("❌ Log file not found")
        return
    
    print("📄 Recent log entries (last 20 lines):")
    print("=" * 50)
    
    try:
        result = subprocess.run(['tail', '-20', str(log_file)], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print(result.stdout)
        else:
            print("❌ Could not read log file")
    except Exception as e:
        print(f"❌ Error reading logs: {e}")

def main():
    """Main CLI interface"""
    if len(sys.argv) < 2:
        print("🎵 SpotiPi Development Server Manager")
        print()
        print("Usage:")
        print("  ./spotipi_dev.py start         # Start server (simple method)")
        print("  ./spotipi_dev.py stop          # Stop server")
        print("  ./spotipi_dev.py status        # Show status")
        print("  ./spotipi_dev.py logs          # Show recent logs")
        print()
        print("Zsh function 'spotipi' provides convenient commands:")
        print("  spotipi start, spotipi stop, spotipi restart, spotipi status")
        print()
        print("To set up zsh function, run:")
        print("  source spotipi.zsh")
    
    command = sys.argv[1].lower()
    
    if command == "start":
        return 0 if start_server() else 1
    elif command == "stop":
        return 0 if stop_server() else 1
    elif command == "status":
        status()
        return 0
    elif command == "logs":
        logs()
        return 0
    else:
        print(f"❌ Unknown command: {command}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
