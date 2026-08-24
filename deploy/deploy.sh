#!/bin/bash
# Grid Trader Deployment Script
# 
# Usage:
#   ./deploy/deploy.sh --install    # Initial installation
#   ./deploy/deploy.sh --update     # Update from git
#   ./deploy/deploy.sh --start      # Start service
#   ./deploy/deploy.sh --stop       # Stop service
#   ./deploy/deploy.sh --restart    # Restart service
#   ./deploy/deploy.sh --logs       # View logs
#

set -e

# Configuration
APP_DIR="/opt/gridtrader"
APP_USER="gridtrader"
SERVICE_NAME="gridtrader"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "Please run as root (use sudo)"
        exit 1
    fi
}

install() {
    check_root
    log_info "Installing Grid Trader Headless Service..."
    
    # Create user if not exists
    if ! id "$APP_USER" &>/dev/null; then
        useradd -r -s /bin/false "$APP_USER"
        log_info "Created user: $APP_USER"
    fi
    
    # Create app directory
    mkdir -p "$APP_DIR"
    
    # Copy application files
    log_info "Copying application files to $APP_DIR..."
    cp -r . "$APP_DIR/"
    
    # Create required directories
    mkdir -p "$APP_DIR/logs" "$APP_DIR/data"
    
    # Install dependencies
    log_info "Installing Python dependencies..."
    cd "$APP_DIR"
    pip3 install -r requirements.txt
    
    # Set permissions
    chown -R "$APP_USER:$APP_USER" "$APP_DIR"
    
    # Install systemd service
    log_info "Installing systemd service..."
    cp "$APP_DIR/deploy/gridtrader.service" /etc/systemd/system/
    systemctl daemon-reload
    
    # Copy config file
    if [ ! -f "$APP_DIR/config/headless.yaml" ]; then
        cp "$APP_DIR/config/headless.yaml.example" "$APP_DIR/config/headless.yaml"
        log_warn "Please configure $APP_DIR/config/headless.yaml with your API keys"
    fi
    
    log_info "Installation complete!"
    log_info ""
    log_info "Next steps:"
    log_info "1. Edit config: nano $APP_DIR/config/headless.yaml"
    log_info "2. Start service: systemctl start $SERVICE_NAME"
    log_info "3. Enable on boot: systemctl enable $SERVICE_NAME"
    log_info "4. Check status: systemctl status $SERVICE_NAME"
}

update() {
    check_root
    log_info "Updating Grid Trader..."
    
    # Stop service
    systemctl stop "$SERVICE_NAME" 2>/dev/null || true
    
    # Pull latest code
    cd "$APP_DIR"
    git pull origin feature/headless-service
    
    # Update dependencies
    pip3 install -r requirements.txt --upgrade
    
    # Restart service
    systemctl start "$SERVICE_NAME"
    
    log_info "Update complete!"
}

start_service() {
    systemctl start "$SERVICE_NAME"
    log_info "Service started"
}

stop_service() {
    systemctl stop "$SERVICE_NAME"
    log_info "Service stopped"
}

restart_service() {
    systemctl restart "$SERVICE_NAME"
    log_info "Service restarted"
}

status_service() {
    systemctl status "$SERVICE_NAME"
}

view_logs() {
    journalctl -u "$SERVICE_NAME" -f
}

uninstall() {
    check_root
    log_warn "This will remove the Grid Trader service!"
    read -p "Are you sure? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        systemctl stop "$SERVICE_NAME" 2>/dev/null || true
        systemctl disable "$SERVICE_NAME" 2>/dev/null || true
        rm /etc/systemd/system/"$SERVICE_NAME.service"
        rm -rf "$APP_DIR"
        userdel "$APP_USER" 2>/dev/null || true
        log_info "Uninstallation complete"
    fi
}

show_help() {
    echo "Grid Trader Deployment Script"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  --install    Install the service"
    echo "  --update     Update from git"
    echo "  --start      Start the service"
    echo "  --stop       Stop the service"
    echo "  --restart    Restart the service"
    echo "  --status     Show service status"
    echo "  --logs       View service logs"
    echo "  --uninstall  Remove the service"
    echo "  --help       Show this help message"
}

# Main
case "${1:-}" in
    --install)
        install
        ;;
    --update)
        update
        ;;
    --start)
        start_service
        ;;
    --stop)
        stop_service
        ;;
    --restart)
        restart_service
        ;;
    --status)
        status_service
        ;;
    --logs)
        view_logs
        ;;
    --uninstall)
        uninstall
        ;;
    --help|-h)
        show_help
        ;;
    *)
        show_help
        exit 1
        ;;
esac
