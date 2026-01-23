#!/bin/bash
#
# Orange Nethack - Update Script
#
# Run this on the production server to pull and deploy changes.
# Usage: sudo ./deploy/update.sh
#

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[+]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }

APP_DIR="/opt/orange-nethack"
APP_USER="orange-nethack"
VENV="$APP_DIR/.venv"

cd "$APP_DIR"

# Check what changed
log "Pulling latest changes..."
sudo -u "$APP_USER" git fetch
CHANGES=$(sudo -u "$APP_USER" git diff --name-only HEAD origin/master)

if [ -z "$CHANGES" ]; then
    log "Already up to date."
    exit 0
fi

echo "$CHANGES"
echo ""

# Pull
sudo -u "$APP_USER" git pull

# Check what needs updating
RESTART_SERVICES=false
REBUILD_FRONTEND=false
UPDATE_SHELL=false

if echo "$CHANGES" | grep -q "^src/"; then
    RESTART_SERVICES=true
fi

if echo "$CHANGES" | grep -q "^web/"; then
    REBUILD_FRONTEND=true
fi

if echo "$CHANGES" | grep -q "scripts/orange-shell.sh"; then
    UPDATE_SHELL=true
fi

# Apply updates
if [ "$RESTART_SERVICES" = true ]; then
    log "Python code changed - reinstalling and restarting services..."
    sudo -u "$APP_USER" "$VENV/bin/pip" install -q -e .
    systemctl restart orange-nethack-api orange-nethack-monitor
fi

if [ "$REBUILD_FRONTEND" = true ]; then
    log "Frontend changed - rebuilding..."
    cd "$APP_DIR/web"
    sudo -u "$APP_USER" npm install --silent
    sudo -u "$APP_USER" npm run build
    cd "$APP_DIR"
fi

if [ "$UPDATE_SHELL" = true ]; then
    log "Shell script changed - updating..."
    cp "$APP_DIR/scripts/orange-shell.sh" /usr/local/bin/
    chmod +x /usr/local/bin/orange-shell.sh
fi

# Verify
log "Verifying services..."
if systemctl is-active --quiet orange-nethack-api && systemctl is-active --quiet orange-nethack-monitor; then
    log "Services running."
else
    warn "Service issue detected. Check: systemctl status orange-nethack-api orange-nethack-monitor"
    exit 1
fi

log "Update complete!"
