#!/bin/bash

# 🔄 SpotiPi Migration Script: spotify_wakeup → spotipi
# Automatisiertes Migrationsskript für lokale und Pi-Migration

set -euo pipefail

# 🎨 Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# 📝 Logging functions
log_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }
log_step() { echo -e "${PURPLE}🚀 $1${NC}"; }

# ⚙️ Configuration
OLD_NAME="spotify_wakeup"
NEW_NAME="spotipi"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PARENT_DIR="$(dirname "$PROJECT_DIR")"

# Environment variables with defaults
PI_HOST="${SPOTIPI_PI_HOST:-pi@spotipi.local}"
PI_PATH="${SPOTIPI_PI_PATH:-/home/pi/$NEW_NAME}"
SERVICE_NAME="${SPOTIPI_SERVICE_NAME:-spotify-web.service}"
SHOW_STATUS="${SPOTIPI_SHOW_STATUS:-1}"

# 🔧 Functions
confirm() {
    read -p "$(echo -e "${YELLOW}❓ $1 (y/N): ${NC}")" -n 1 -r
    echo
    [[ $REPLY =~ ^[Yy]$ ]]
}

check_requirements() {
    log_step "Checking requirements..."
    
    # Check if we're in the right directory
    if [[ ! -f "$PROJECT_DIR/run.py" ]]; then
        log_error "Not in a SpotiPi project directory! Expected to find run.py"
        exit 1
    fi
    
    # Check if new scripts exist
    if [[ ! -f "$SCRIPT_DIR/deploy_to_pi_new.sh" ]]; then
        log_error "New deployment script not found! Please ensure deploy_to_pi_new.sh exists"
        exit 1
    fi
    
    if [[ ! -f "$SCRIPT_DIR/toggle_logging_new.sh" ]]; then
        log_error "New logging script not found! Please ensure toggle_logging_new.sh exists"
        exit 1
    fi
    
    log_success "Requirements check passed"
}

create_local_backup() {
    log_step "Creating local backup..."
    
    local backup_name="${OLD_NAME}_backup_$(date +%Y%m%d_%H%M%S)"
    local backup_path="$PARENT_DIR/$backup_name"
    
    if cp -r "$PROJECT_DIR" "$backup_path"; then
        log_success "Local backup created: $backup_path"
        echo "$backup_path" > "/tmp/spotipi_backup_path"
    else
        log_error "Failed to create local backup"
        exit 1
    fi
}

migrate_local_directory() {
    log_step "Migrating local directory..."
    
    local new_project_dir="$PARENT_DIR/$NEW_NAME"
    
    if [[ -d "$new_project_dir" ]] && [[ "$new_project_dir" != "$PROJECT_DIR" ]]; then
        if confirm "Directory $new_project_dir already exists. Remove it?"; then
            rm -rf "$new_project_dir"
        else
            log_error "Cannot proceed with existing directory"
            exit 1
        fi
    fi
    
    if [[ "$PROJECT_DIR" != "$new_project_dir" ]]; then
        mv "$PROJECT_DIR" "$new_project_dir"
        log_success "Local directory renamed: $PROJECT_DIR → $new_project_dir"
        
        # Update PROJECT_DIR for rest of script
        PROJECT_DIR="$new_project_dir"
        SCRIPT_DIR="$PROJECT_DIR/scripts"
    else
        log_info "Already in target directory name"
    fi
}

activate_new_scripts() {
    log_step "Activating path-agnostic scripts..."
    
    cd "$SCRIPT_DIR"
    
    # Backup old scripts
    if [[ -f "deploy_to_pi.sh" ]]; then
        mv "deploy_to_pi.sh" "deploy_to_pi_old.sh"
        log_info "Backed up old deployment script"
    fi
    
    if [[ -f "toggle_logging.sh" ]]; then
        mv "toggle_logging.sh" "toggle_logging_old.sh"
        log_info "Backed up old logging script"
    fi
    
    # Activate new scripts
    mv "deploy_to_pi_new.sh" "deploy_to_pi.sh"
    mv "toggle_logging_new.sh" "toggle_logging.sh"
    chmod +x "deploy_to_pi.sh" "toggle_logging.sh"
    
    log_success "New path-agnostic scripts activated"
}

migrate_pi_config() {
    log_step "Migrating Pi configuration directories..."
    
    ssh "$PI_HOST" "
        set -e
        
        echo '🔧 Creating backup of Pi config...'
        if [[ -d ~/.${OLD_NAME} ]]; then
            cp -r ~/.${OLD_NAME} ~/.${OLD_NAME}_backup_\$(date +%Y%m%d_%H%M%S) || true
        fi
        
        echo '📁 Creating new config directory...'
        mkdir -p ~/.${NEW_NAME}
        
        echo '📋 Migrating config data...'
        if [[ -d ~/.${OLD_NAME} ]]; then
            cp -r ~/.${OLD_NAME}/* ~/.${NEW_NAME}/ 2>/dev/null || true
            echo '✅ Config data migrated to ~/.${NEW_NAME}'
        else
            echo 'ℹ️  No old config directory found'
        fi
    "
    
    log_success "Pi config migration completed"
}

migrate_pi_app_directory() {
    log_step "Migrating Pi application directory..."
    
    ssh "$PI_HOST" "
        set -e
        
        echo '🛑 Stopping service...'
        sudo systemctl stop ${SERVICE_NAME} || true
        
        echo '🔧 Creating backup of Pi app directory...'
        if [[ -d /home/pi/${OLD_NAME} ]]; then
            sudo cp -r /home/pi/${OLD_NAME} /home/pi/${OLD_NAME}_backup_\$(date +%Y%m%d_%H%M%S) || true
        fi
        
        echo '📁 Creating new app directory...'
        sudo mkdir -p ${PI_PATH}
        sudo chown pi:pi ${PI_PATH}
        
        echo '📋 Migrating app data...'
        if [[ -d /home/pi/${OLD_NAME} ]]; then
            rsync -av --exclude='venv/' --exclude='*.log' --exclude='logs/' --exclude='__pycache__/' /home/pi/${OLD_NAME}/ ${PI_PATH}/
            echo '✅ App data migrated to ${PI_PATH}'
        else
            echo 'ℹ️  No old app directory found'
        fi
    "
    
    log_success "Pi app directory migration completed"
}

update_systemd_service() {
    log_step "Updating systemd service..."
    
    ssh "$PI_HOST" "
        set -e
        
        echo '🔧 Backing up old service...'
        sudo cp /etc/systemd/system/${SERVICE_NAME} /etc/systemd/system/${SERVICE_NAME}.backup || true
        
        echo '📝 Creating new service configuration...'
        sudo tee /etc/systemd/system/${SERVICE_NAME} > /dev/null << 'EOF'
[Unit]
Description=SpotiPi Web Interface
After=network.target

[Service]
User=pi
WorkingDirectory=${PI_PATH}
EnvironmentFile=${PI_PATH}/.env
Environment=\"SPOTIPI_APP_NAME=${NEW_NAME}\"
ExecStart=${PI_PATH}/venv/bin/python run.py
Restart=always
Environment=\"PYTHONUNBUFFERED=1\"
Environment=\"PORT=5000\"
StandardOutput=append:${PI_PATH}/web.log
StandardError=append:${PI_PATH}/web.log

[Install]
WantedBy=multi-user.target
EOF
        
        echo '🔄 Reloading systemd...'
        sudo systemctl daemon-reload
        
        echo '✅ Service configuration updated'
    "
    
    log_success "Systemd service updated"
}

setup_pi_python_environment() {
    log_step "Setting up Python environment on Pi..."
    
    ssh "$PI_HOST" "
        set -e
        cd ${PI_PATH}
        
        echo '🐍 Creating virtual environment...'
        python3 -m venv venv
        
        echo '📦 Installing requirements...'
        source venv/bin/activate
        pip install -r requirements.txt
        
        echo '📋 Migrating .env file...'
        # Try multiple sources for .env file
        if [[ -f /home/pi/${OLD_NAME}/.env ]]; then
            cp /home/pi/${OLD_NAME}/.env ${PI_PATH}/.env
            echo '✅ .env migrated from old app directory'
        elif [[ -f ~/.${NEW_NAME}/.env ]]; then
            cp ~/.${NEW_NAME}/.env ${PI_PATH}/.env
            echo '✅ .env migrated from config directory'
        elif [[ -f ~/.${OLD_NAME}/.env ]]; then
            cp ~/.${OLD_NAME}/.env ${PI_PATH}/.env
            echo '✅ .env migrated from old config directory'
        else
            echo '⚠️  No .env file found - you may need to create one manually'
        fi
        
        echo '✅ Python environment setup completed'
    "
    
    log_success "Pi Python environment setup completed"
}

deploy_and_test() {
    log_step "Deploying and testing new setup..."
    
    cd "$PROJECT_DIR"
    
    # Set environment variables for deployment
    export SPOTIPI_APP_NAME="$NEW_NAME"
    export SPOTIPI_PI_PATH="$PI_PATH"
    export SPOTIPI_PI_HOST="$PI_HOST"
    export SPOTIPI_SERVICE_NAME="$SERVICE_NAME"
    export SPOTIPI_SHOW_STATUS="$SHOW_STATUS"
    
    log_info "Running deployment with new scripts..."
    if ./scripts/deploy_to_pi.sh; then
        log_success "Deployment completed successfully"
    else
        log_error "Deployment failed!"
        exit 1
    fi
    
    log_info "Testing web interface..."
    sleep 5
    
    local pi_ip
    pi_ip=$(echo "$PI_HOST" | cut -d'@' -f2)
    
    if curl -s -o /dev/null -w "%{http_code}" "http://$pi_ip:5000" | grep -q "200"; then
        log_success "Web interface is responding correctly"
    else
        log_warning "Web interface test failed or returned non-200 status"
    fi
}

cleanup_old_directories() {
    log_step "Cleaning up old directories..."
    
    if confirm "Remove old directories on Pi? This cannot be undone!"; then
        ssh "$PI_HOST" "
            set -e
            
            echo '🧹 Removing old app directory...'
            if [[ -d /home/pi/${OLD_NAME} ]]; then
                sudo rm -rf /home/pi/${OLD_NAME}
                echo '✅ Removed /home/pi/${OLD_NAME}'
            fi
            
            echo '🧹 Removing old config directory...'
            if [[ -d ~/.${OLD_NAME} ]]; then
                rm -rf ~/.${OLD_NAME}
                echo '✅ Removed ~/.${OLD_NAME}'
            fi
            
            echo '🧹 Old directories cleaned up'
        "
        log_success "Pi directories cleaned up"
    else
        log_info "Skipping Pi directory cleanup"
    fi
    
    if confirm "Remove local backup? (You can do this later manually)"; then
        if [[ -f "/tmp/spotipi_backup_path" ]]; then
            local backup_path
            backup_path=$(cat "/tmp/spotipi_backup_path")
            if [[ -d "$backup_path" ]]; then
                rm -rf "$backup_path"
                rm -f "/tmp/spotipi_backup_path"
                log_success "Local backup removed: $backup_path"
            fi
        fi
    else
        log_info "Local backup preserved"
    fi
}

show_migration_summary() {
    log_success "🎉 Migration completed successfully!"
    echo
    log_info "📊 Migration Summary:"
    echo "  • Local directory: $(basename "$PARENT_DIR")/$OLD_NAME → $(basename "$PARENT_DIR")/$NEW_NAME"
    echo "  • Pi config:       ~/.${OLD_NAME} → ~/.${NEW_NAME}"
    echo "  • Pi app:          /home/pi/${OLD_NAME} → ${PI_PATH}"
    echo "  • Scripts:         Path-agnostic versions activated"
    echo "  • Service:         Updated to use new paths"
    echo
    log_info "🔧 Environment Variables for future deployments:"
    echo "  export SPOTIPI_APP_NAME=\"$NEW_NAME\""
    echo "  export SPOTIPI_PI_HOST=\"$PI_HOST\""
    echo "  export SPOTIPI_PI_PATH=\"$PI_PATH\""
    echo
    log_info "🌐 Access your SpotiPi at: http://$(echo "$PI_HOST" | cut -d'@' -f2):5000"
}

# 🚀 Main execution
main() {
    echo -e "${PURPLE}"
    echo "╔══════════════════════════════════════════════════════════════════════════════╗"
    echo "║                        🔄 SpotiPi Migration Script                          ║"
    echo "║                      spotify_wakeup → spotipi                               ║"
    echo "╚══════════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    log_info "Starting migration process..."
    log_info "Old name: $OLD_NAME"
    log_info "New name: $NEW_NAME" 
    log_info "Project directory: $PROJECT_DIR"
    log_info "Pi host: $PI_HOST"
    log_info "Pi path: $PI_PATH"
    echo
    
    if ! confirm "Do you want to proceed with the migration?"; then
        log_info "Migration cancelled by user"
        exit 0
    fi
    
    # Execute migration steps
    check_requirements
    create_local_backup
    migrate_local_directory
    activate_new_scripts
    migrate_pi_config
    migrate_pi_app_directory
    update_systemd_service
    setup_pi_python_environment
    deploy_and_test
    cleanup_old_directories
    show_migration_summary
    
    log_success "🎊 All migration steps completed successfully!"
}

# Run main function
main "$@"