#!/bin/bash
# Quick local testing script - runs server and tests automatically

set -e

echo "=================================================="
echo "  Orange Nethack - Quick Local Test"
echo "=================================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check prerequisites
if [ ! -f ".venv/bin/activate" ]; then
    echo "Error: Virtual environment not found"
    echo "Run: python3 -m venv .venv && source .venv/bin/activate && pip install -e ."
    exit 1
fi

# Activate venv
source .venv/bin/activate

# Create test env if needed
if [ ! -f ".env.test" ]; then
    echo "Creating .env.test..."
    cat > .env.test << 'EOF'
STRIKE_API_KEY=test_key
MOCK_LIGHTNING=true
ANTE_SATS=1000
POT_INITIAL=0
HOST=0.0.0.0
PORT=8000
DATABASE_PATH=/tmp/orange-nethack-test.db
WEBHOOK_SECRET=test_webhook_secret_12345
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:8000
NETHACK_BINARY=/usr/games/nethack
XLOGFILE_PATH=/var/games/nethack/xlogfile
NETHACK_USER_PREFIX=nh_test_
NETHACK_GROUP=games
SESSION_TIMEOUT_HOURS=24
MAX_ACTIVE_SESSIONS=100
SMTP_HOST=
EOF
fi

# Clean test database
rm -f /tmp/orange-nethack-test.db

# Export test config
export $(cat .env.test | grep -v '^#' | xargs)

echo -e "${YELLOW}Step 1: Starting API server...${NC}"
# Start server in background
uvicorn orange_nethack.api.main:app --port 8000 > /tmp/orange-nethack-server.log 2>&1 &
SERVER_PID=$!

# Cleanup function
cleanup() {
    echo ""
    echo "Stopping server..."
    kill $SERVER_PID 2>/dev/null || true
    wait $SERVER_PID 2>/dev/null || true
    rm -f /tmp/orange-nethack-test.db
}
trap cleanup EXIT

# Wait for server to start
echo "Waiting for server to start..."
for i in {1..30}; do
    if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Server started${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Error: Server failed to start"
        echo "Check logs: tail /tmp/orange-nethack-server.log"
        exit 1
    fi
    sleep 1
done

echo ""
echo -e "${YELLOW}Step 2: Running security tests...${NC}"
echo ""

# Run tests
./scripts/test-security-local.sh

echo ""
echo -e "${GREEN}Done! Server will stop automatically.${NC}"
