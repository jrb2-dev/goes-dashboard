#!/bin/bash
#
# GOES Satellite Dashboard Installer
# https://github.com/YOUR_USERNAME/goes-dashboard
#
# Usage:
#   ./install.sh              # Install with defaults
#   ./install.sh --uninstall  # Remove installation
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="/opt/goes-dashboard"
SERVICE_NAME="goes-dashboard"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
DEFAULT_PORT=8080

# Print colored output
info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Check if running as root or with sudo available
check_sudo() {
    if [ "$EUID" -ne 0 ]; then
        if ! command -v sudo &> /dev/null; then
            error "This script requires root privileges. Please run as root or install sudo."
        fi
        SUDO="sudo"
    else
        SUDO=""
    fi
}

# Detect the current user (even when running with sudo)
detect_user() {
    if [ -n "$SUDO_USER" ]; then
        INSTALL_USER="$SUDO_USER"
    else
        INSTALL_USER="$(whoami)"
    fi
    USER_HOME=$(eval echo ~$INSTALL_USER)
}

# Uninstall function
uninstall() {
    info "Uninstalling GOES Dashboard..."
    
    # Stop and disable service
    if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        $SUDO systemctl stop "$SERVICE_NAME"
    fi
    if systemctl is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
        $SUDO systemctl disable "$SERVICE_NAME"
    fi
    
    # Remove service file
    [ -f "$SERVICE_FILE" ] && $SUDO rm -f "$SERVICE_FILE"
    
    # Remove installation directory
    [ -d "$INSTALL_DIR" ] && $SUDO rm -rf "$INSTALL_DIR"
    
    # Reload systemd
    $SUDO systemctl daemon-reload
    
    success "GOES Dashboard uninstalled successfully!"
    exit 0
}

# Main installation
install() {
    echo ""
    echo -e "${GREEN}🛰️  GOES Satellite Dashboard Installer${NC}"
    echo "========================================="
    echo ""

    # Check for uninstall flag
    if [ "$1" = "--uninstall" ] || [ "$1" = "-u" ]; then
        uninstall
    fi

    check_sudo
    detect_user

    # Check Python version
    info "Checking Python version..."
    if ! command -v python3 &> /dev/null; then
        error "Python 3 is required but not installed."
    fi
    
    PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    success "Python $PYTHON_VERSION found"

    # Install Python dependencies
    info "Installing Python dependencies..."
    if pip3 install fastapi uvicorn psutil --break-system-packages 2>/dev/null; then
        success "Dependencies installed"
    elif pip3 install fastapi uvicorn psutil --user 2>/dev/null; then
        success "Dependencies installed (user mode)"
    elif pip3 install fastapi uvicorn psutil 2>/dev/null; then
        success "Dependencies installed"
    else
        error "Failed to install Python dependencies"
    fi

    # Create installation directory
    info "Creating installation directory..."
    $SUDO mkdir -p "$INSTALL_DIR/static"
    success "Created $INSTALL_DIR"

    # Copy files
    info "Copying files..."
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    
    if [ -f "$SCRIPT_DIR/src/main.py" ]; then
        $SUDO cp "$SCRIPT_DIR/src/main.py" "$INSTALL_DIR/"
        $SUDO cp -r "$SCRIPT_DIR/src/static/"* "$INSTALL_DIR/static/"
    elif [ -f "$SCRIPT_DIR/main.py" ]; then
        $SUDO cp "$SCRIPT_DIR/main.py" "$INSTALL_DIR/"
        $SUDO cp -r "$SCRIPT_DIR/static/"* "$INSTALL_DIR/static/"
    else
        error "Source files not found. Make sure main.py exists."
    fi
    success "Files copied"

    # Create default config if it doesn't exist
    if [ ! -f "$INSTALL_DIR/config.json" ]; then
        info "Creating default configuration..."
        
        # Try to auto-detect setup
        SATELLITE="GOES-16"
        DATA_DIR="$USER_HOME/goes16"
        
        if [ -d "$USER_HOME/goes19" ]; then
            SATELLITE="GOES-19"
            DATA_DIR="$USER_HOME/goes19"
        elif [ -d "$USER_HOME/goes18" ]; then
            SATELLITE="GOES-18"
            DATA_DIR="$USER_HOME/goes18"
        fi
        
        # Detect services
        RECEIVER="goesrecv"
        PROCESSORS='["goesproc"]'
        
        if systemctl list-unit-files | grep -q "goesproc-emwin"; then
            PROCESSORS='["goesproc-emwin", "goesproc-main"]'
        fi
        
        $SUDO tee "$INSTALL_DIR/config.json" > /dev/null << EOF
{
  "satellite": "$SATELLITE",
  "data_dir": "$DATA_DIR",
  "images_dir": "$DATA_DIR",
  "emwin_dir": "$USER_HOME/goes16/emwinTEXT/emwin",
  "upload_logs_dir": "$USER_HOME",
  "services": {
    "receiver": "$RECEIVER",
    "processors": $PROCESSORS
  },
  "upload_stations": [],
  "image_types": {
    "fd_fc": "fd/fc",
    "m1_fc": "m1/fc",
    "m2_fc": "m2/fc"
  },
  "dashboard_port": $DEFAULT_PORT,
  "refresh_interval": 5000
}
EOF
        success "Configuration created at $INSTALL_DIR/config.json"
        warn "You may want to edit the configuration to match your setup"
    else
        success "Existing configuration preserved"
    fi

    # Set ownership
    $SUDO chown -R "$INSTALL_USER:$INSTALL_USER" "$INSTALL_DIR"

    # Create systemd service
    info "Creating systemd service..."
    $SUDO tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=GOES Satellite Dashboard
Documentation=https://github.com/YOUR_USERNAME/goes-dashboard
After=network.target goesrecv.service
Wants=goesrecv.service

[Service]
Type=simple
User=$INSTALL_USER
Group=$INSTALL_USER
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port $DEFAULT_PORT
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=$INSTALL_DIR

[Install]
WantedBy=multi-user.target
EOF
    success "Service file created"

    # Enable and start service
    info "Enabling and starting service..."
    $SUDO systemctl daemon-reload
    $SUDO systemctl enable "$SERVICE_NAME"
    $SUDO systemctl start "$SERVICE_NAME"

    # Wait for service to start
    sleep 2

    # Check if service is running
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        success "Service started successfully!"
    else
        warn "Service may have failed to start. Check: journalctl -u $SERVICE_NAME -n 50"
    fi

    # Get IP address
    IP_ADDR=$(hostname -I | awk '{print $1}')
    HOSTNAME=$(hostname)

    # Print success message
    echo ""
    echo -e "${GREEN}=========================================${NC}"
    echo -e "${GREEN}✅ Installation Complete!${NC}"
    echo -e "${GREEN}=========================================${NC}"
    echo ""
    echo "Access your dashboard at:"
    echo -e "  ${BLUE}http://${IP_ADDR}:${DEFAULT_PORT}${NC}"
    echo -e "  ${BLUE}http://${HOSTNAME}.local:${DEFAULT_PORT}${NC}"
    echo ""
    echo "Configuration file:"
    echo -e "  ${YELLOW}$INSTALL_DIR/config.json${NC}"
    echo ""
    echo "Useful commands:"
    echo "  sudo systemctl status $SERVICE_NAME    # Check status"
    echo "  sudo systemctl restart $SERVICE_NAME   # Restart"
    echo "  journalctl -u $SERVICE_NAME -f         # View logs"
    echo ""
    echo -e "🛰️ ${GREEN}Happy receiving!${NC} 📡"
    echo ""
}

# Run installation
install "$@"
