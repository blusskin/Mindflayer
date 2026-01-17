#!/bin/bash
#
# Test the full Orange Nethack flow using Docker
#
# Prerequisites:
#   - Docker running
#   - docker-compose installed
#
# This script:
#   1. Builds and starts the container
#   2. Creates a session via API
#   3. Simulates payment
#   4. Shows SSH credentials
#   5. Opens an SSH connection to play
#

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
ORANGE='\033[0;33m'
NC='\033[0m'

API_URL="http://localhost:8000"
SSH_PORT=2222

echo -e "${ORANGE}"
cat << 'EOF'
  ___                              _   _      _   _                _
 / _ \ _ __ __ _ _ __   __ _  ___ | \ | | ___| |_| |__   __ _  ___| | __
| | | | '__/ _` | '_ \ / _` |/ _ \|  \| |/ _ \ __| '_ \ / _` |/ __| |/ /
| |_| | | | (_| | | | | (_| |  __/| |\  |  __/ |_| | | | (_| | (__|   <
 \___/|_|  \__,_|_| |_|\__, |\___|_| \_|\___|\__|_| |_|\__,_|\___|_|\_\
                       |___/
EOF
echo -e "${NC}"
echo -e "${YELLOW}Full Integration Test${NC}"
echo ""

# Check if container is running
if ! docker-compose ps | grep -q "Up"; then
    echo -e "${YELLOW}Starting Docker container...${NC}"
    docker-compose up -d --build
    echo "Waiting for services to start..."
    sleep 5
fi

# Wait for API to be ready
echo -n "Waiting for API..."
for i in {1..30}; do
    if curl -s "$API_URL/api/health" > /dev/null 2>&1; then
        echo -e " ${GREEN}ready!${NC}"
        break
    fi
    echo -n "."
    sleep 1
done

# Check health
echo ""
echo -e "${GREEN}=== Step 1: Check Server Health ===${NC}"
curl -s "$API_URL/api/health" | python3 -m json.tool

# Show pot
echo ""
echo -e "${GREEN}=== Step 2: Check Pot Balance ===${NC}"
curl -s "$API_URL/api/pot" | python3 -m json.tool

# Create session
echo ""
echo -e "${GREEN}=== Step 3: Create Session ===${NC}"
RESPONSE=$(curl -s -X POST "$API_URL/api/play" \
    -H "Content-Type: application/json" \
    -d '{"lightning_address": "test@example.com"}')
echo "$RESPONSE" | python3 -m json.tool

# Extract session ID and payment hash
SESSION_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['session_id'])")
PAYMENT_HASH=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['payment_hash'])")

echo ""
echo -e "Session ID: ${YELLOW}$SESSION_ID${NC}"
echo -e "Payment Hash: ${YELLOW}${PAYMENT_HASH:0:20}...${NC}"

# Simulate payment via webhook
echo ""
echo -e "${GREEN}=== Step 4: Simulate Payment (Webhook) ===${NC}"
curl -s -X POST "$API_URL/api/webhook/payment" \
    -H "Content-Type: application/json" \
    -d "{\"payment_hash\": \"$PAYMENT_HASH\"}" | python3 -m json.tool

# Get session with credentials
echo ""
echo -e "${GREEN}=== Step 5: Get Session Credentials ===${NC}"
SESSION=$(curl -s "$API_URL/api/session/$SESSION_ID")
echo "$SESSION" | python3 -m json.tool

USERNAME=$(echo "$SESSION" | python3 -c "import sys, json; print(json.load(sys.stdin)['username'])")
PASSWORD=$(echo "$SESSION" | python3 -c "import sys, json; print(json.load(sys.stdin)['password'])")

# Display connection info
echo ""
echo -e "${GREEN}=== Step 6: SSH Connection Info ===${NC}"
echo ""
echo -e "  ${ORANGE}Username:${NC} $USERNAME"
echo -e "  ${ORANGE}Password:${NC} $PASSWORD"
echo ""
echo -e "  ${YELLOW}To connect, run:${NC}"
echo -e "  ssh -p $SSH_PORT $USERNAME@localhost"
echo ""
echo -e "  (You'll be prompted for the password above)"
echo ""

# Optionally connect
read -p "Connect now? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo -e "${YELLOW}Connecting... (password: $PASSWORD)${NC}"
    echo ""
    ssh -o StrictHostKeyChecking=no -p $SSH_PORT "$USERNAME@localhost"
fi

echo ""
echo -e "${GREEN}Done!${NC}"
