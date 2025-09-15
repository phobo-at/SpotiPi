#!/bin/bash

# 🔍 SpotiPi Migration Verification Script
# Verifies successful migration from spotify_wakeup to spotipi

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SPOTIPI_APP_NAME="${SPOTIPI_APP_NAME:-spotipi}"
SPOTIPI_PI_HOST="${SPOTIPI_PI_HOST:-pi@spotipi.local}"
SPOTIPI_PI_PATH="${SPOTIPI_PI_PATH:-/home/pi/spotipi}"
SPOTIPI_SERVICE_NAME="${SPOTIPI_SERVICE_NAME:-spotify-web.service}"

# Counters
PASSED=0
FAILED=0
WARNINGS=0

# Functions
print_header() {
    echo -e "\n${BLUE}=== $1 ===${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
    ((PASSED++))
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
    ((FAILED++))
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
    ((WARNINGS++))
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Test functions
test_local_environment() {
    print_header "Local Environment Verification"
    
    # Check if we're in the correct directory
    if [[ $(basename "$PWD") == "$SPOTIPI_APP_NAME" ]]; then
        print_success "Working directory is correctly named '$SPOTIPI_APP_NAME'"
    else
        print_error "Working directory is '$(basename "$PWD")', should be '$SPOTIPI_APP_NAME'"
    fi
    
    # Check if old scripts exist as backups
    if [[ -f "scripts/deploy_to_pi_old.sh" ]]; then
        print_success "Old deployment script backed up as deploy_to_pi_old.sh"
    else
        print_warning "Old deployment script backup not found"
    fi
    
    # Check if new scripts are executable
    if [[ -x "scripts/deploy_to_pi.sh" ]]; then
        print_success "New deployment script is executable"
    else
        print_error "New deployment script is not executable"
    fi
    
    # Check if migration guide exists
    if [[ -f "MIGRATION_GUIDE.md" ]]; then
        print_success "Migration guide exists"
    else
        print_warning "Migration guide not found"
    fi
}

test_pi_connectivity() {
    print_header "Raspberry Pi Connectivity"
    
    if ssh -o ConnectTimeout=5 -o BatchMode=yes "$SPOTIPI_PI_HOST" "exit" 2>/dev/null; then
        print_success "SSH connection to Pi successful"
        return 0
    else
        print_error "Cannot connect to Pi via SSH"
        return 1
    fi
}

test_pi_directories() {
    print_header "Pi Directory Structure"
    
    # Test new app directory
    if ssh "$SPOTIPI_PI_HOST" "test -d '$SPOTIPI_PI_PATH'"; then
        print_success "New app directory exists: $SPOTIPI_PI_PATH"
    else
        print_error "New app directory not found: $SPOTIPI_PI_PATH"
    fi
    
    # Check if old directory still exists (should be cleaned up)
    if ssh "$SPOTIPI_PI_HOST" "test -d '/home/pi/spotify_wakeup'"; then
        print_warning "Old directory still exists: /home/pi/spotify_wakeup (cleanup pending?)"
    else
        print_success "Old app directory cleaned up"
    fi
    
    # Test config directory
    if ssh "$SPOTIPI_PI_HOST" "test -d '~/.${SPOTIPI_APP_NAME}'"; then
        print_success "New config directory exists: ~/.${SPOTIPI_APP_NAME}"
    else
        print_error "New config directory not found: ~/.${SPOTIPI_APP_NAME}"
    fi
    
    # Check if old config directory still exists
    if ssh "$SPOTIPI_PI_HOST" "test -d '~/.spotify_wakeup'"; then
        print_warning "Old config directory still exists: ~/.spotify_wakeup (cleanup pending?)"
    else
        print_success "Old config directory cleaned up"
    fi
}

test_pi_files() {
    print_header "Pi File Migration"
    
    # Check essential files
    ESSENTIAL_FILES=("run.py" "requirements.txt" "src/app.py" "src/config.py")
    
    for file in "${ESSENTIAL_FILES[@]}"; do
        if ssh "$SPOTIPI_PI_HOST" "test -f '$SPOTIPI_PI_PATH/$file'"; then
            print_success "Essential file exists: $file"
        else
            print_error "Essential file missing: $file"
        fi
    done
    
    # Check .env file
    if ssh "$SPOTIPI_PI_HOST" "test -f '$SPOTIPI_PI_PATH/.env'"; then
        print_success ".env file exists"
    else
        print_warning ".env file not found (may need to be created)"
    fi
    
    # Check virtual environment
    if ssh "$SPOTIPI_PI_HOST" "test -d '$SPOTIPI_PI_PATH/venv'"; then
        print_success "Virtual environment directory exists"
    else
        print_error "Virtual environment not found"
    fi
}

test_systemd_service() {
    print_header "Systemd Service"
    
    # Check if service file exists
    if ssh "$SPOTIPI_PI_HOST" "test -f '/etc/systemd/system/$SPOTIPI_SERVICE_NAME'"; then
        print_success "Service file exists: $SPOTIPI_SERVICE_NAME"
    else
        print_error "Service file not found: $SPOTIPI_SERVICE_NAME"
    fi
    
    # Check service status
    SERVICE_STATUS=$(ssh "$SPOTIPI_PI_HOST" "sudo systemctl is-active $SPOTIPI_SERVICE_NAME" 2>/dev/null || echo "unknown")
    case $SERVICE_STATUS in
        "active")
            print_success "Service is active and running"
            ;;
        "inactive")
            print_warning "Service exists but is not running"
            ;;
        "failed")
            print_error "Service failed to start"
            ;;
        *)
            print_error "Service status unknown: $SERVICE_STATUS"
            ;;
    esac
    
    # Check if service is enabled
    if ssh "$SPOTIPI_PI_HOST" "sudo systemctl is-enabled $SPOTIPI_SERVICE_NAME" >/dev/null 2>&1; then
        print_success "Service is enabled for auto-start"
    else
        print_warning "Service is not enabled for auto-start"
    fi
}

test_web_interface() {
    print_header "Web Interface Functionality"
    
    # Get Pi IP for web testing
    PI_IP=$(ssh "$SPOTIPI_PI_HOST" "hostname -I | awk '{print \$1}'" 2>/dev/null || echo "spotipi.local")
    WEB_URL="http://${PI_IP}:5000"
    
    print_info "Testing web interface at: $WEB_URL"
    
    # Test main page
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 "$WEB_URL" 2>/dev/null || echo "000")
    if [[ "$HTTP_CODE" == "200" ]]; then
        print_success "Web interface responds with HTTP 200"
    elif [[ "$HTTP_CODE" == "000" ]]; then
        print_error "Cannot connect to web interface"
    else
        print_warning "Web interface responds with HTTP $HTTP_CODE (not 200)"
    fi
    
    # Test API endpoints
    API_ENDPOINTS=("/api/alarm_status" "/api/spotify/library_status")
    
    for endpoint in "${API_ENDPOINTS[@]}"; do
        API_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "${WEB_URL}${endpoint}" 2>/dev/null || echo "000")
        if [[ "$API_CODE" == "200" ]]; then
            print_success "API endpoint responds: $endpoint"
        else
            print_warning "API endpoint issue ($API_CODE): $endpoint"
        fi
    done
}

test_python_environment() {
    print_header "Python Environment"
    
    # Test Python executable in venv
    if ssh "$SPOTIPI_PI_HOST" "cd '$SPOTIPI_PI_PATH' && ./venv/bin/python --version" >/dev/null 2>&1; then
        PYTHON_VERSION=$(ssh "$SPOTIPI_PI_HOST" "cd '$SPOTIPI_PI_PATH' && ./venv/bin/python --version")
        print_success "Python environment working: $PYTHON_VERSION"
    else
        print_error "Python virtual environment not working"
    fi
    
    # Test if requirements are installed
    if ssh "$SPOTIPI_PI_HOST" "cd '$SPOTIPI_PI_PATH' && ./venv/bin/python -c 'import flask, spotipy; print(\"OK\")'" >/dev/null 2>&1; then
        print_success "Essential Python packages available (flask, spotipy)"
    else
        print_error "Essential Python packages missing"
    fi
    
    # Test if application can import
    if ssh "$SPOTIPI_PI_HOST" "cd '$SPOTIPI_PI_PATH' && ./venv/bin/python -c 'from src.app import app; print(\"OK\")'" >/dev/null 2>&1; then
        print_success "Application imports successfully"
    else
        print_error "Application import failed"
    fi
}

test_config_migration() {
    print_header "Configuration Migration"
    
    # Check if config files exist in new location
    CONFIG_FILES=("default_config.json")
    
    for config in "${CONFIG_FILES[@]}"; do
        # Check in app directory
        if ssh "$SPOTIPI_PI_HOST" "test -f '$SPOTIPI_PI_PATH/config/$config'"; then
            print_success "Config file exists: config/$config"
        else
            print_warning "Config file not found: config/$config"
        fi
        
        # Check in home config directory
        if ssh "$SPOTIPI_PI_HOST" "test -f '~/.${SPOTIPI_APP_NAME}/$config'"; then
            print_success "User config exists: ~/.${SPOTIPI_APP_NAME}/$config"
        fi
    done
    
    # Test if app can load config
    if ssh "$SPOTIPI_PI_HOST" "cd '$SPOTIPI_PI_PATH' && ./venv/bin/python -c 'from src.config import load_config; load_config(); print(\"OK\")'" >/dev/null 2>&1; then
        print_success "Configuration loads successfully"
    else
        print_error "Configuration loading failed"
    fi
}

test_logs_and_caching() {
    print_header "Logs and Caching"
    
    # Check if log directory exists
    if ssh "$SPOTIPI_PI_HOST" "test -d '$SPOTIPI_PI_PATH/logs'"; then
        print_success "Logs directory exists"
    else
        print_warning "Logs directory not found"
    fi
    
    # Check if cache files are accessible
    if ssh "$SPOTIPI_PI_HOST" "test -f '$SPOTIPI_PI_PATH/logs/music_library_cache.json'"; then
        print_success "Music library cache file exists"
    else
        print_info "Music library cache file not found (will be created on first use)"
    fi
    
    # Check service logs
    if ssh "$SPOTIPI_PI_HOST" "sudo journalctl -u $SPOTIPI_SERVICE_NAME --since '1 hour ago' --quiet" >/dev/null 2>&1; then
        print_success "Service logs accessible"
    else
        print_warning "Cannot access service logs"
    fi
}

# Main execution
main() {
    echo -e "${BLUE}"
    echo "🔍 SpotiPi Migration Verification"
    echo "=================================="
    echo -e "${NC}"
    echo "App Name: $SPOTIPI_APP_NAME"
    echo "Pi Host: $SPOTIPI_PI_HOST"
    echo "Pi Path: $SPOTIPI_PI_PATH"
    echo "Service: $SPOTIPI_SERVICE_NAME"
    
    # Run all tests
    test_local_environment
    
    if test_pi_connectivity; then
        test_pi_directories
        test_pi_files
        test_systemd_service
        test_python_environment
        test_config_migration
        test_logs_and_caching
        test_web_interface
    else
        print_error "Skipping Pi tests due to connectivity issues"
    fi
    
    # Summary
    print_header "Verification Summary"
    echo -e "${GREEN}✅ Passed: $PASSED${NC}"
    if [[ $WARNINGS -gt 0 ]]; then
        echo -e "${YELLOW}⚠️  Warnings: $WARNINGS${NC}"
    fi
    if [[ $FAILED -gt 0 ]]; then
        echo -e "${RED}❌ Failed: $FAILED${NC}"
    fi
    
    echo ""
    if [[ $FAILED -eq 0 ]]; then
        if [[ $WARNINGS -eq 0 ]]; then
            echo -e "${GREEN}🎉 Migration verification PASSED completely!${NC}"
            exit 0
        else
            echo -e "${YELLOW}⚠️  Migration verification PASSED with warnings.${NC}"
            echo -e "${YELLOW}Please review warnings above.${NC}"
            exit 1
        fi
    else
        echo -e "${RED}❌ Migration verification FAILED!${NC}"
        echo -e "${RED}Please address the failed items above.${NC}"
        exit 2
    fi
}

# Help function
show_help() {
    echo "SpotiPi Migration Verification Script"
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -h, --help              Show this help message"
    echo ""
    echo "Environment Variables:"
    echo "  SPOTIPI_APP_NAME        App name (default: spotipi)"
    echo "  SPOTIPI_PI_HOST         Pi SSH host (default: pi@spotipi.local)"
    echo "  SPOTIPI_PI_PATH         Pi app path (default: /home/pi/spotipi)"
    echo "  SPOTIPI_SERVICE_NAME    Service name (default: spotify-web.service)"
}

# Parse arguments
case "${1:-}" in
    -h|--help)
        show_help
        exit 0
        ;;
    "")
        main
        ;;
    *)
        echo "Unknown option: $1"
        show_help
        exit 1
        ;;
esac