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
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[+]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; }

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
UPDATE_DEPS=false
CHECK_CONFIG=false

if echo "$CHANGES" | grep -q "^src/"; then
    RESTART_SERVICES=true
fi

if echo "$CHANGES" | grep -q "^web/"; then
    REBUILD_FRONTEND=true
fi

if echo "$CHANGES" | grep -q "scripts/orange-shell.sh"; then
    UPDATE_SHELL=true
fi

if echo "$CHANGES" | grep -q "pyproject.toml"; then
    UPDATE_DEPS=true
    RESTART_SERVICES=true
fi

if echo "$CHANGES" | grep -q ".env.example"; then
    CHECK_CONFIG=true
fi

# Apply updates
if [ "$UPDATE_DEPS" = true ]; then
    log "Dependencies changed - updating packages..."
    sudo -u "$APP_USER" "$VENV/bin/pip" install --upgrade pip
    sudo -u "$APP_USER" "$VENV/bin/pip" install -e .

    # Verify critical security dependencies
    log "Verifying security dependencies..."
    if sudo -u "$APP_USER" "$VENV/bin/pip" list | grep -q "slowapi"; then
        log "  ✓ slowapi (rate limiting) installed"
    else
        error "  ✗ slowapi not installed - security fix missing!"
    fi

    if sudo -u "$APP_USER" "$VENV/bin/pip" list | grep -q "email-validator"; then
        log "  ✓ email-validator (email validation) installed"
    else
        error "  ✗ email-validator not installed - security fix missing!"
    fi
elif [ "$RESTART_SERVICES" = true ]; then
    log "Python code changed - reinstalling..."
    sudo -u "$APP_USER" "$VENV/bin/pip" install -q -e .
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

# Check configuration
if [ "$CHECK_CONFIG" = true ]; then
    warn "Configuration template (.env.example) changed!"
    warn "Please review and update your .env file:"
    echo ""

    # Check for new security settings
    if ! grep -q "WEBHOOK_SECRET" "$APP_DIR/.env" 2>/dev/null; then
        warn "  [ ] WEBHOOK_SECRET not found in .env"
        warn "      Run: orange-nethack-cli setup-strike-webhook https://your-domain.com/api/webhook/payment"
    fi

    if ! grep -q "ALLOWED_ORIGINS" "$APP_DIR/.env" 2>/dev/null; then
        warn "  [ ] ALLOWED_ORIGINS not found in .env"
        warn "      Add: ALLOWED_ORIGINS=https://your-domain.com"
    fi

    echo ""
fi

# Restart services if needed
if [ "$RESTART_SERVICES" = true ]; then
    log "Restarting services..."
    systemctl restart orange-nethack-api orange-nethack-monitor
    sleep 2
fi

# Verify services
log "Verifying services..."
if systemctl is-active --quiet orange-nethack-api && systemctl is-active --quiet orange-nethack-monitor; then
    log "  ✓ orange-nethack-api running"
    log "  ✓ orange-nethack-monitor running"
else
    error "Service issue detected!"
    echo ""
    echo "Check status with:"
    echo "  systemctl status orange-nethack-api"
    echo "  systemctl status orange-nethack-monitor"
    echo ""
    echo "Check logs with:"
    echo "  journalctl -u orange-nethack-api -n 50"
    exit 1
fi

# Security verification (if security-related files changed)
if echo "$CHANGES" | grep -qE "webhooks.py|database.py|models.py|main.py|limiter.py"; then
    log "Running security verification..."

    # Test health endpoint
    if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
        log "  ✓ API responding"
    else
        error "  ✗ API not responding"
    fi

    # Test webhook signature requirement
    response=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/api/webhook/payment \
        -H "Content-Type: application/json" \
        -d '{"eventType":"invoice.updated","data":{"entityId":"test"}}' 2>/dev/null)

    if [ "$response" == "401" ]; then
        log "  ✓ Webhook signature verification enabled"
    elif [ "$response" == "404" ]; then
        warn "  ! Webhook endpoint responding but no signature check (might be mock mode)"
    else
        warn "  ! Webhook signature check unclear (HTTP $response)"
    fi

    # Test rate limiting
    request_count=0
    for i in {1..6}; do
        response=$(curl -s -o /dev/null -w "%{http_code}" \
            -X POST http://localhost:8000/api/play \
            -H "Content-Type: application/json" \
            -d '{"lightning_address":"test@example.com"}' 2>/dev/null)

        if [ "$response" == "429" ]; then
            log "  ✓ Rate limiting active (blocked on request $i)"
            break
        fi
        request_count=$i
    done

    if [ $request_count -ge 6 ]; then
        warn "  ! Rate limiting not triggered after 6 requests"
    fi

    # Wait for rate limit to reset
    sleep 60
fi

# Final summary
echo ""
log "Update complete!"
echo ""

# Show next steps if config changes detected
if [ "$CHECK_CONFIG" = true ]; then
    echo "=========================================="
    echo "  NEXT STEPS"
    echo "=========================================="
    echo ""
    echo "1. Review .env configuration:"
    echo "   sudo nano $APP_DIR/.env"
    echo ""
    echo "2. Ensure these settings are present:"
    echo "   WEBHOOK_SECRET=<set via CLI command>"
    echo "   ALLOWED_ORIGINS=https://your-domain.com"
    echo "   MOCK_LIGHTNING=false"
    echo ""
    echo "3. Re-register Strike webhook (if not done):"
    echo "   cd $APP_DIR"
    echo "   source .venv/bin/activate"
    echo "   orange-nethack-cli setup-strike-webhook https://your-domain.com/api/webhook/payment"
    echo ""
    echo "4. Restart services after .env changes:"
    echo "   sudo systemctl restart orange-nethack-api orange-nethack-monitor"
    echo ""
    echo "=========================================="
fi
