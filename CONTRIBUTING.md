# Contributing to SpotiPi

Thank you for your interest in contributing to SpotiPi! This guide will help you get started with development and contributions.

## 🚀 Development Setup

### Prerequisites
- Python 3.8+
- Spotify Premium account
- Git

### Setup Environment
```bash
# Clone repository
git clone https://github.com/phobo-at/SpotiPi.git
cd SpotiPi

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup .env file
cp .env.example .env
# Edit .env with your Spotify credentials

# Generate token
python generate_token.py

# Start development server
python run.py
```

## 📁 Modern Project Structure

```
SpotiPi/
├── src/                    # Main application code
│   ├── app.py             # Flask app & routes
│   ├── config.py          # Configuration management
│   ├── api/               # Spotify API integration
│   ├── core/              # Core logic (alarm, sleep, scheduler)
│   ├── services/          # Service layer architecture
│   └── utils/             # Utilities (logger, cache, etc.)
├── static/                # Frontend assets
├── templates/             # HTML templates
├── config/                # Configuration files
├── run.py                 # Application entry point
└── generate_token.py      # Spotify token generator
```

## 🔧 Development Workflow

### 1. Create Feature Branch
```bash
git checkout -b feature/your-feature-name
```

### 2. Development
- **Environment detection**: Code automatically detects dev vs Pi
- **Hot reload**: Changes reload automatically in development
- **Logging**: Verbose logs in development, minimal on Pi
- **Ports**: Auto-uses 5001 for dev, 5000 for production

### 3. Testing
```bash
# Run locally
python run.py

# Test Pi mode (without Pi hardware)
SPOTIPI_RASPBERRY_PI=1 python run.py

# Run tests (if available)
python -m pytest
```

### 4. Commit & Push
```bash
git add .
git commit -m "feat: add your feature description"
git push origin feature/your-feature-name
```

## 🎨 Code Standards

### Python Code Style
- **PEP 8**: Follow Python style guidelines
- **Type Hints**: Use type annotations for all functions
- **Docstrings**: Document public functions and classes
- **Error Handling**: Proper exception handling and logging

Example:
```python
def process_alarm(alarm_config: Dict[str, Any]) -> ServiceResult:
    """Process alarm configuration and validate settings.
    
    Args:
        alarm_config: Dictionary containing alarm settings
        
    Returns:
        ServiceResult with success status and any error messages
    """
    try:
        # Implementation here
        return ServiceResult.success("Alarm processed")
    except Exception as e:
        logger.error(f"Alarm processing failed: {e}")
        return ServiceResult.error(f"Failed to process alarm: {e}")
```

### Frontend Standards
- **Responsive Design**: Mobile-first approach
- **Accessibility**: Proper ARIA labels and keyboard navigation
- **Performance**: Optimize images and minimize requests
- **Browser Support**: Chrome, Safari, Firefox, Mobile browsers

## 🐛 Bug Reports

### Information to Include
1. **Environment**: OS, Python version, browser
2. **Steps to reproduce**: Clear, numbered steps
3. **Expected behavior**: What should happen
4. **Actual behavior**: What actually happens
5. **Logs**: Relevant console/server logs
6. **Screenshots**: If UI-related

### Getting Logs
```bash
# Development logs (console output)
python run.py

# Production logs on Pi
tail -f ~/spotipi/logs/spotipi.log

# Browser console (F12 → Console tab)
```

## 📋 Pull Request Guidelines

### Before Submitting
- [ ] Code follows style guidelines
- [ ] Functions have type hints and docstrings
- [ ] Tested on both development and Pi environments
- [ ] No hardcoded credentials or sensitive data
- [ ] Error handling implemented
- [ ] Documentation updated if needed

### PR Description Template
```markdown
## What does this PR do?
Brief description of changes

## Testing
- [ ] Tested locally in development mode
- [ ] Tested Pi mode (if applicable)
- [ ] Tested responsive design (if UI changes)
- [ ] No console errors

## Screenshots (if UI changes)
[Add screenshots here]

## Breaking Changes
List any breaking changes (if any)
```

## 🔒 Security Guidelines

### Credentials & Secrets
- **Never commit**: API keys, tokens, or passwords
- **Use .env**: All credentials go in environment variables
- **Validate .gitignore**: Ensure sensitive files are ignored

### Code Security
- **Input validation**: Sanitize all user inputs
- **API calls**: Use timeouts and error handling
- **Logging**: Don't log sensitive information

## 🎵 Spotify API Guidelines

### Best Practices
- **Rate limiting**: Respect API limits (avoid rapid successive calls)
- **Error handling**: Handle 401 (auth), 429 (rate limit), 503 (service unavailable)
- **Caching**: Cache responses when appropriate to reduce API calls
- **Scopes**: Only request necessary permissions

### Token Management
- Tokens auto-refresh via `generate_token.py`
- Don't manually handle refresh tokens in code
- Use the existing token cache system

## 🧪 Testing

### Manual Testing Checklist
- [ ] Alarm setting/editing works
- [ ] Sleep timer functions correctly
- [ ] Music library browsing responsive
- [ ] Mobile interface usable
- [ ] Error states handled gracefully
- [ ] Auto-environment detection works

### Browser Testing
- **Desktop**: Chrome, Safari, Firefox
- **Mobile**: iOS Safari, Android Chrome
- **Responsive**: Test various screen sizes

## � Raspberry Pi Development

### Testing Pi Features
```bash
# Force Pi mode for testing
SPOTIPI_RASPBERRY_PI=1 python run.py

# Test auto-detection
python -c "from src.config import get_config; print(get_config().environment)"
```

### Pi-Specific Considerations
- **SD Card Protection**: Minimal file I/O, reduced logging
- **Performance**: Optimize for limited Pi resources
- **Service Integration**: Test with systemd if possible

## 💡 Feature Ideas

### Current Priorities
1. **Multiple Alarms**: Support for several concurrent alarms
2. **Advanced Scheduling**: Complex recurring patterns
3. **Smart Home Integration**: Home Assistant, MQTT support
4. **Enhanced Sleep Timer**: Gradual volume reduction, nature sounds

### Architecture Improvements
- **Service Tests**: Unit tests for service layer
- **API Documentation**: OpenAPI/Swagger docs
- **Performance Monitoring**: Metrics and health checks
- **Configuration UI**: Web-based settings management

## 🆘 Getting Help

- **Documentation**: Check README.md first
- **Issues**: Search existing GitHub issues
- **Code Questions**: Open a discussion on GitHub
- **Bugs**: Create detailed issue with reproduction steps

## 📈 Release Process

### Versioning
We use semantic versioning (MAJOR.MINOR.PATCH):
- **PATCH**: Bug fixes, minor improvements
- **MINOR**: New features, non-breaking changes  
- **MAJOR**: Breaking changes, major architecture updates

### Changelog
Update CHANGELOG.md with:
- **🆕 Features**: New functionality
- **� Bug Fixes**: Fixed issues
- **� Improvements**: Enhancements
- **⚠️ Breaking Changes**: Compatibility notes

---

**Thank you for contributing to SpotiPi!** 🎵

*Every contribution makes mornings better for SpotiPi users worldwide.*
