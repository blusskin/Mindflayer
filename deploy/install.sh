#!/bin/bash
#
# Orange Nethack - Bare Metal Deployment Script for Debian 12
#
# Usage: sudo ./install.sh
#
# This script will:
# 1. Install system dependencies
# 2. Create the orange-nethack user and directories
# 3. Set up the Python environment
# 4. Install the application
# 5. Configure SSH for game users
# 6. Set up systemd services
# 7. Install and configure nginx with SSL (optional)
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[+]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    error "Please run as root: sudo ./install.sh"
fi

# Configuration
APP_DIR="/opt/orange-nethack"
APP_USER="orange-nethack"
NETHACK_GROUP="games"
VENV_DIR="$APP_DIR/.venv"
DATA_DIR="/var/lib/orange-nethack"
GAMES_DIR="/var/games/nethack"

echo ""
echo "=========================================="
echo "  Orange Nethack Deployment Script"
echo "  Debian 12 Bare Metal Installation"
echo "=========================================="
echo ""

# Step 1: Install system dependencies
log "Installing system dependencies..."
apt-get update
apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    nethack-console \
    openssh-server \
    nginx \
    certbot \
    python3-certbot-nginx \
    git \
    sudo \
    curl

# Step 2: Create application user (for running the service)
log "Creating application user..."
if ! id "$APP_USER" &>/dev/null; then
    useradd --system --shell /bin/bash --home "$APP_DIR" --create-home "$APP_USER"
fi

# Add app user to games group
usermod -aG "$NETHACK_GROUP" "$APP_USER"

# Step 3: Create directory structure
log "Creating directory structure..."

# Application data directory
mkdir -p "$DATA_DIR"
chown "$APP_USER:$APP_USER" "$DATA_DIR"
chmod 755 "$DATA_DIR"

# Nethack game directories
mkdir -p "$GAMES_DIR"/{save,dumps,recordings,users}
chown -R root:"$NETHACK_GROUP" "$GAMES_DIR"
chmod 775 "$GAMES_DIR"
chmod 777 "$GAMES_DIR/recordings"
chmod 755 "$GAMES_DIR/users"

# Create xlogfile
touch "$GAMES_DIR/xlogfile"
chown "$NETHACK_GROUP:$NETHACK_GROUP" "$GAMES_DIR/xlogfile"
chmod 664 "$GAMES_DIR/xlogfile"

# Create other nethack files
touch "$GAMES_DIR/perm" "$GAMES_DIR/logfile" "$GAMES_DIR/record"
chown root:"$NETHACK_GROUP" "$GAMES_DIR/perm" "$GAMES_DIR/logfile" "$GAMES_DIR/record"
chmod 664 "$GAMES_DIR/perm" "$GAMES_DIR/logfile" "$GAMES_DIR/record"

# Step 4: Copy application files (assumes script is run from repo directory)
log "Setting up application directory..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ "$SCRIPT_DIR" != "$APP_DIR" ]; then
    # Copy files to /opt/orange-nethack
    mkdir -p "$APP_DIR"
    cp -r "$SCRIPT_DIR"/{src,scripts,web,pyproject.toml,README.md} "$APP_DIR/" 2>/dev/null || true

    # Create deploy directory for reference
    mkdir -p "$APP_DIR/deploy"
    cp "$SCRIPT_DIR/deploy"/* "$APP_DIR/deploy/" 2>/dev/null || true
fi

chown -R "$APP_USER:$APP_USER" "$APP_DIR"

# Step 5: Set up Python virtual environment
log "Setting up Python virtual environment..."
sudo -u "$APP_USER" python3.11 -m venv "$VENV_DIR"
sudo -u "$APP_USER" "$VENV_DIR/bin/pip" install --upgrade pip
sudo -u "$APP_USER" "$VENV_DIR/bin/pip" install -e "$APP_DIR"

# Step 5b: Build frontend (if not already built)
if [ -d "$APP_DIR/web" ] && [ ! -d "$APP_DIR/web/dist" ]; then
    log "Building frontend..."
    apt-get install -y nodejs npm
    cd "$APP_DIR/web"
    sudo -u "$APP_USER" npm install
    sudo -u "$APP_USER" npm run build
    cd "$APP_DIR"
fi

# Step 6: Install the custom shell script
log "Installing custom SSH shell..."
cp "$APP_DIR/scripts/orange-shell.sh" /usr/local/bin/
chmod +x /usr/local/bin/orange-shell.sh

# Add to valid shells
if ! grep -q "orange-shell.sh" /etc/shells; then
    echo "/usr/local/bin/orange-shell.sh" >> /etc/shells
fi

# Step 7: Configure SSH
log "Configuring SSH..."
SSH_CONFIG="/etc/ssh/sshd_config"

# Backup original config
cp "$SSH_CONFIG" "$SSH_CONFIG.backup.$(date +%Y%m%d)" 2>/dev/null || true

# Ensure password authentication is enabled (needed for game users)
sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication yes/' "$SSH_CONFIG"
sed -i 's/^#*ChallengeResponseAuthentication.*/ChallengeResponseAuthentication no/' "$SSH_CONFIG"

# Restart SSH
systemctl restart sshd

# Step 8: Create .env file template if it doesn't exist
log "Creating .env template..."
ENV_FILE="$APP_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    cat > "$ENV_FILE" << 'EOF'
# Orange Nethack Production Configuration
# IMPORTANT: Fill in the values below before starting the service

# Lightning/Strike API
MOCK_LIGHTNING=false
STRIKE_API_KEY=your_strike_api_key_here

# Email (Mailtrap transactional)
SMTP_HOST=live.smtp.mailtrap.io
SMTP_PORT=587
SMTP_USER=api
SMTP_PASSWORD=your_mailtrap_api_token_here
SMTP_FROM_EMAIL=noreply@yourdomain.com
SMTP_USE_TLS=true

# Game settings
ANTE_SATS=1000
POT_INITIAL=0

# Server settings
HOST=127.0.0.1
PORT=8000
DATABASE_PATH=/var/lib/orange-nethack/db.sqlite
XLOGFILE_PATH=/var/games/nethack/xlogfile

# Nethack settings
NETHACK_BINARY=/usr/games/nethack
NETHACK_USER_PREFIX=nh_
NETHACK_GROUP=games
MAX_ACTIVE_SESSIONS=100
EOF
    chown "$APP_USER:$APP_USER" "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    warn "Created $ENV_FILE - YOU MUST EDIT THIS FILE with your production values!"
fi

# Step 9: Initialize database
log "Initializing database..."
sudo -u "$APP_USER" "$VENV_DIR/bin/python" -c "
import asyncio
from orange_nethack.database import init_db
asyncio.run(init_db())
"

# Step 10: Create systemd services
log "Creating systemd services..."

# API service
cat > /etc/systemd/system/orange-nethack-api.service << EOF
[Unit]
Description=Orange Nethack API Server
After=network.target

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
Environment=PATH=$VENV_DIR/bin:/usr/local/bin:/usr/bin:/bin
EnvironmentFile=$APP_DIR/.env
ExecStart=$VENV_DIR/bin/orange-nethack-api
Restart=always
RestartSec=5

# Note: We don't use ProtectSystem because the app needs sudo for user management

[Install]
WantedBy=multi-user.target
EOF

# Game monitor service
cat > /etc/systemd/system/orange-nethack-monitor.service << EOF
[Unit]
Description=Orange Nethack Game Monitor
After=network.target orange-nethack-api.service

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
Environment=PATH=$VENV_DIR/bin:/usr/local/bin:/usr/bin:/bin
EnvironmentFile=$APP_DIR/.env
ExecStart=$VENV_DIR/bin/orange-nethack-monitor
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
systemctl daemon-reload

# Step 11: Grant necessary permissions for user management
log "Configuring permissions for user management..."

# The app user needs to be able to create/delete game users
# Add to sudoers with specific commands only
SUDOERS_FILE="/etc/sudoers.d/orange-nethack"
cat > "$SUDOERS_FILE" << EOF
# Allow orange-nethack to manage game users
$APP_USER ALL=(ALL) NOPASSWD: /usr/sbin/useradd
$APP_USER ALL=(ALL) NOPASSWD: /usr/sbin/userdel
$APP_USER ALL=(ALL) NOPASSWD: /usr/sbin/chpasswd
$APP_USER ALL=(ALL) NOPASSWD: /usr/bin/chown
$APP_USER ALL=(ALL) NOPASSWD: /usr/bin/chmod
$APP_USER ALL=(ALL) NOPASSWD: /usr/bin/pkill
$APP_USER ALL=(ALL) NOPASSWD: /usr/sbin/chsh
EOF
chmod 440 "$SUDOERS_FILE"

# Update user manager to use sudo
log "NOTE: You may need to update the user manager to use 'sudo' for system commands"

# Step 12: Create nginx configuration
log "Creating nginx configuration..."
cat > /etc/nginx/sites-available/orange-nethack << 'EOF'
server {
    listen 80;
    server_name _;  # Replace with your domain

    # Redirect HTTP to HTTPS (uncomment after SSL setup)
    # return 301 https://$server_name$request_uri;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;  # For WebSocket connections
    }
}
EOF

# Enable the site
ln -sf /etc/nginx/sites-available/orange-nethack /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test and reload nginx
nginx -t && systemctl reload nginx

# Final summary
echo ""
echo "=========================================="
echo "  Installation Complete!"
echo "=========================================="
echo ""
log "Next steps:"
echo ""
echo "1. EDIT THE .ENV FILE with your production values:"
echo "   sudo nano $APP_DIR/.env"
echo ""
echo "2. Update the nginx config with your domain:"
echo "   sudo nano /etc/nginx/sites-available/orange-nethack"
echo ""
echo "3. Set up SSL with Let's Encrypt:"
echo "   sudo certbot --nginx -d yourdomain.com"
echo ""
echo "4. Start the services:"
echo "   sudo systemctl enable --now orange-nethack-api"
echo "   sudo systemctl enable --now orange-nethack-monitor"
echo ""
echo "5. Set up the Strike webhook (after services are running):"
echo "   sudo -u $APP_USER $VENV_DIR/bin/orange-nethack-cli setup-strike-webhook https://yourdomain.com/api/webhook/strike"
echo ""
echo "6. Configure firewall (if using ufw):"
echo "   sudo ufw allow 22/tcp   # SSH for game"
echo "   sudo ufw allow 80/tcp   # HTTP"
echo "   sudo ufw allow 443/tcp  # HTTPS"
echo "   sudo ufw enable"
echo ""
warn "IMPORTANT: Make sure to edit .env before starting the services!"
echo ""
