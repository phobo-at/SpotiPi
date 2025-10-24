#!/usr/bin/env python3
"""
🚀 SpotiPi Background Server Manager
Manages the Flask server as a background daemon with proper lifecycle management.
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import psutil


class SpotiPiServerManager:
    """Manages SpotiPi server as a background process."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent  # Go up one level from scripts/
        self.pid_file = self.project_root / "scripts" / "server.pid"
        self.log_file = self.project_root / "logs" / "server.log"
        self.error_log = self.project_root / "logs" / "server_error.log"
        
        # Ensure logs directory exists
        self.log_file.parent.mkdir(exist_ok=True)
    
    def is_running(self) -> bool:
        """Check if server is currently running."""
        if not self.pid_file.exists():
            return False
        
        try:
            with open(self.pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            # Check if process with this PID exists and is our server
            if psutil.pid_exists(pid):
                proc = psutil.Process(pid)
                cmdline = ' '.join(proc.cmdline())
                if 'run.py' in cmdline or 'src.app' in cmdline:
                    return True
            
            # PID file exists but process is dead - clean up
            self.pid_file.unlink()
            return False
            
        except (ValueError, psutil.NoSuchProcess, PermissionError):
            if self.pid_file.exists():
                self.pid_file.unlink()
            return False
    
    def get_status(self) -> dict:
        """Get detailed server status."""
        if not self.is_running():
            return {
                "status": "stopped",
                "pid": None,
                "uptime": None,
                "memory_mb": None,
                "cpu_percent": None
            }
        
        try:
            with open(self.pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            proc = psutil.Process(pid)
            uptime = time.time() - proc.create_time()
            
            return {
                "status": "running",
                "pid": pid,
                "uptime": f"{int(uptime // 60)}m {int(uptime % 60)}s",
                "memory_mb": round(proc.memory_info().rss / 1024 / 1024, 1),
                "cpu_percent": round(proc.cpu_percent(), 1)
            }
            
        except (psutil.NoSuchProcess, ValueError):
            return {"status": "error", "message": "Process not found"}
    
    def start(self) -> bool:
        """Start the server in the background."""
        if self.is_running():
            print("🟢 Server is already running")
            status = self.get_status()
            print(f"   PID: {status['pid']}, Uptime: {status['uptime']}")
            return True
        
        print("🚀 Starting SpotiPi server in background...")
        
        # Start server as background process
        try:
            env = os.environ.copy()
            env['PYTHONUNBUFFERED'] = '1'  # Ensure logs are flushed immediately
            
            with open(self.log_file, 'w') as log_out, open(self.error_log, 'w') as log_err:
                process = subprocess.Popen(
                    [sys.executable, 'run.py'],
                    cwd=self.project_root,
                    stdout=log_out,
                    stderr=log_err,
                    env=env,
                    start_new_session=True  # Detach from current session
                )
            
            # Write PID file
            with open(self.pid_file, 'w') as f:
                f.write(str(process.pid))
            
            # Wait a moment to check if it started successfully
            time.sleep(2)
            
            if self.is_running():
                status = self.get_status()
                print("✅ Server started successfully!")
                print(f"   PID: {status['pid']}")
                print(f"   Logs: {self.log_file}")
                print("   URL: http://localhost:5001")
                return True
            else:
                print("❌ Server failed to start")
                if self.error_log.exists():
                    print(f"   Check error log: {self.error_log}")
                return False
                
        except Exception as e:
            print(f"❌ Error starting server: {e}")
            return False
    
    def stop(self) -> bool:
        """Stop the background server."""
        if not self.is_running():
            print("🔴 Server is not running")
            return True
        
        try:
            with open(self.pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            print(f"🛑 Stopping server (PID: {pid})...")
            
            # Try graceful shutdown first
            os.kill(pid, signal.SIGTERM)
            
            # Wait for graceful shutdown
            for _ in range(10):  # Wait up to 10 seconds
                if not psutil.pid_exists(pid):
                    break
                time.sleep(1)
            
            # Force kill if still running
            if psutil.pid_exists(pid):
                print("   Force killing...")
                os.kill(pid, signal.SIGKILL)
                time.sleep(1)
            
            # Clean up PID file
            if self.pid_file.exists():
                self.pid_file.unlink()
            
            print("✅ Server stopped successfully")
            return True
            
        except (ProcessLookupError, psutil.NoSuchProcess):
            # Process already dead
            if self.pid_file.exists():
                self.pid_file.unlink()
            print("✅ Server was already stopped")
            return True
        except Exception as e:
            print(f"❌ Error stopping server: {e}")
            return False
    
    def restart(self) -> bool:
        """Restart the server."""
        print("🔄 Restarting server...")
        self.stop()
        time.sleep(1)
        return self.start()
    
    def logs(self, lines: int = 50, follow: bool = False):
        """Show server logs."""
        if not self.log_file.exists():
            print("❌ No log file found")
            return
        
        if follow:
            print("📋 Following logs (Ctrl+C to stop)...")
            try:
                # Use tail -f for following
                subprocess.run(['tail', '-f', str(self.log_file)])
            except KeyboardInterrupt:
                print("\n📋 Stopped following logs")
        else:
            print(f"📋 Last {lines} lines from server log:")
            try:
                result = subprocess.run(['tail', f'-{lines}', str(self.log_file)], 
                                      capture_output=True, text=True)
                print(result.stdout)
            except Exception as e:
                print(f"❌ Error reading logs: {e}")
    
    def error_logs(self, lines: int = 50):
        """Show server error logs."""
        if not self.error_log.exists():
            print("❌ No error log file found")
            return
        
        print(f"🔴 Last {lines} lines from error log:")
        try:
            result = subprocess.run(['tail', f'-{lines}', str(self.error_log)], 
                                  capture_output=True, text=True)
            print(result.stdout)
        except Exception as e:
            print(f"❌ Error reading error logs: {e}")

def main():
    """Main CLI interface."""
    manager = SpotiPiServerManager()
    
    if len(sys.argv) < 2:
        print("🎵 SpotiPi Server Manager")
        print("Usage: python server_manager.py <command>")
        print("")
        print("Commands:")
        print("  start     - Start server in background")
        print("  stop      - Stop background server")
        print("  restart   - Restart server")
        print("  status    - Show server status")
        print("  logs      - Show recent logs")
        print("  logs -f   - Follow logs in real-time")
        print("  errors    - Show error logs")
        return
    
    command = sys.argv[1].lower()
    
    if command == 'start':
        manager.start()
    elif command == 'stop':
        manager.stop()
    elif command == 'restart':
        manager.restart()
    elif command == 'status':
        status = manager.get_status()
        print("🎵 SpotiPi Server Status")
        print("=" * 30)
        if status['status'] == 'running':
            print("Status: 🟢 Running")
            print(f"PID: {status['pid']}")
            print(f"Uptime: {status['uptime']}")
            print(f"Memory: {status['memory_mb']} MB")
            print(f"CPU: {status['cpu_percent']}%")
            print("URL: http://localhost:5001")
        else:
            print(f"Status: 🔴 {status['status'].title()}")
    elif command == 'logs':
        follow = len(sys.argv) > 2 and sys.argv[2] == '-f'
        manager.logs(follow=follow)
    elif command == 'errors':
        manager.error_logs()
    else:
        print(f"❌ Unknown command: {command}")

if __name__ == "__main__":
    main()
