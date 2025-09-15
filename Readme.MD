# 🎵 SpotiPi

**Smart Spotify alarm clock and sleep timer for Raspberry Pi**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Raspberry Pi](https://img.shields.io/badge/platform-Raspberry%20Pi-red.svg)](https://www.raspberrypi.org/)

Wake up to your favorite Spotify music with this elegant web-based alarm system. Features automatic environment detection, mobile-optimized interface, and seamless Raspberry Pi integration.

## ✨ Features

- 🎵 **Spotify Integration** - Wake up to any playlist, album, or track
- ⏰ **Smart Alarms** - Weekday scheduling with automatic management
- 😴 **Sleep Timer** - Peaceful fade-out for better sleep
- 📱 **Mobile First** - Responsive web interface, PWA support
- 🍓 **Pi Optimized** - Auto-detection and SD-card protection
- 🛡️ **Secure** - Environment variables for all credentials

## 🚀 Quick Start

```bash
# Clone and setup
git clone https://github.com/phobo-at/SpotiPi.git
cd SpotiPi
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Configure Spotify (get credentials from developer.spotify.com)
cp .env.example .env
# Edit .env with your Spotify Client ID and Secret

# Generate token and run
python generate_token.py
python run.py
```

Access at `http://localhost:5001` (development) or `http://spotipi.local:5000` (Pi)

## 🔧 Configuration

Create `.env` file:
```env
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret  
SPOTIFY_USERNAME=your_username
```

Everything else is auto-configured with smart defaults.

## 🍓 Raspberry Pi Setup

```bash
# On your Pi
git clone https://github.com/phobo-at/SpotiPi.git /home/pi/.spotify_wakeup
cd /home/pi/.spotify_wakeup && python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt && python generate_token.py

# Install as service
sudo cp scripts/spotipi.service /etc/systemd/system/
sudo systemctl enable spotipi && sudo systemctl start spotipi
```

## 📸 Screenshots (coming soon)

*Mobile-optimized interface with dark theme support*

| Alarm Setup | Sleep Timer | Music Library |
|-------------|-------------|---------------|
| Set wake-up times with weekday selection | Gradual volume fade-out | Browse your complete Spotify collection |

## 🏗️ Architecture

- **Backend**: Flask with modular service architecture
- **Frontend**: Responsive vanilla JS with PWA support
- **Integration**: Spotify Web API with token caching
- **Deployment**: Auto-detection (development vs. Raspberry Pi)

## 📝 Environment Detection

SpotiPi automatically configures itself:
- **macOS/Windows**: Development mode (port 5001, verbose logging)
- **Raspberry Pi**: Production mode (port 5000, minimal logging)
- **Override**: Use environment variables to force specific behavior

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/name`
3. Follow the [Contributing Guide](CONTRIBUTING.md)
4. Submit pull request

## 📄 License

MIT License - feel free to use and modify!

## 🤖 Development Story

This app was 100% vibe-coded with GitHub Copilot and an unhealthy amount of ☕ coffee. 
If you find any bugs, blame the caffeine dependency, not the AI! 😄

## 🙏 Credits

Built with Flask, Spotify Web API, and lots of ❤️ for better mornings.

---

**🌅 Made for music lovers who want to wake up right!**