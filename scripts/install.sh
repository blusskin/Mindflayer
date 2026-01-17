#!/bin/bash
#
# Orange Nethack Installation Script
# Run as root on a fresh Linux server
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    log_error "Please run as root"
    exit 1
fi

# Configuration
INSTALL_DIR="/opt/orange-nethack"
DATA_DIR="/var/lib/orange-nethack"
SERVICE_USER="orange-nethack"
PYTHON_VERSION="3.11"

log_info "Starting Orange Nethack installation..."

# Install system dependencies
log_info "Installing system dependencies..."
apt-get update
apt-get install -y \
    python${PYTHON_VERSION} \
    python${PYTHON_VERSION}-venv \
    python3-pip \
    nethack-console \
    openssh-server \
    git

# Create service user
if ! id "$SERVICE_USER" &>/dev/null; then
    log_info "Creating service user: $SERVICE_USER"
    useradd -r -s /bin/false "$SERVICE_USER"
else
    log_info "Service user already exists: $SERVICE_USER"
fi

# Create directories
log_info "Creating directories..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$DATA_DIR"
chown "$SERVICE_USER:$SERVICE_USER" "$DATA_DIR"

# Clone or copy the application
if [ -d ".git" ]; then
    log_info "Copying application to $INSTALL_DIR..."
    cp -r . "$INSTALL_DIR/"
else
    log_warn "Not in a git repository. Please copy the application manually to $INSTALL_DIR"
fi

# Create virtual environment
log_info "Creating Python virtual environment..."
cd "$INSTALL_DIR"
python${PYTHON_VERSION} -m venv .venv
source .venv/bin/activate

# Install Python dependencies
log_info "Installing Python dependencies..."
pip install --upgrade pip
pip install -e .

# Install shell script
log_info "Installing custom shell..."
cp scripts/orange-shell.sh /usr/local/bin/
chmod +x /usr/local/bin/orange-shell.sh

# Add shell to allowed shells
if ! grep -q "orange-shell.sh" /etc/shells; then
    echo "/usr/local/bin/orange-shell.sh" >> /etc/shells
    log_info "Added orange-shell.sh to /etc/shells"
fi

# Configure nethack
log_info "Configuring Nethack..."
XLOGFILE="/var/games/nethack/xlogfile"
if [ ! -f "$XLOGFILE" ]; then
    touch "$XLOGFILE"
fi
chmod 664 "$XLOGFILE"
chown games:games "$XLOGFILE"

# Create environment file
if [ ! -f "$INSTALL_DIR/.env" ]; then
    log_info "Creating .env file from template..."
    cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
    chmod 600 "$INSTALL_DIR/.env"
    log_warn "Please edit $INSTALL_DIR/.env with your LNbits credentials"
fi

# Install systemd services
log_info "Installing systemd services..."
cp systemd/*.service /etc/systemd/system/
systemctl daemon-reload

# Enable services
log_info "Enabling services..."
systemctl enable orange-nethack-api
systemctl enable orange-nethack-monitor

# Initialize database
log_info "Initializing database..."
source .venv/bin/activate
python -c "import asyncio; from orange_nethack.database import init_db; asyncio.run(init_db())"
chown "$SERVICE_USER:$SERVICE_USER" "$DATA_DIR/db.sqlite"

log_info "Installation complete!"
echo ""
echo "Next steps:"
echo "1. Edit $INSTALL_DIR/.env with your LNbits API keys"
echo "2. Start the services:"
echo "   systemctl start orange-nethack-api"
echo "   systemctl start orange-nethack-monitor"
echo "3. Check status:"
echo "   systemctl status orange-nethack-api"
echo "   systemctl status orange-nethack-monitor"
echo ""
echo "The API will be available at http://localhost:8000"
