#!/bin/bash
# Quick Docker test - builds, starts, tests, and stops

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=================================================="
echo "  Orange Nethack - Quick Docker Test"
echo "=================================================="
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "Creating .env for testing..."
    cat > .env << 'EOF'
# Strike configuration (mock mode)
STRIKE_API_KEY=test_key_docker
MOCK_LIGHTNING=true

# Security settings
WEBHOOK_SECRET=test_webhook_secret_docker_12345
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:8000

# Game settings
ANTE_SATS=1000
POT_INITIAL=0

# SMTP (disabled)
SMTP_HOST=
EOF
fi

echo -e "${YELLOW}Step 1: Building Docker image...${NC}"
docker-compose build

echo ""
echo -e "${YELLOW}Step 2: Starting services...${NC}"
docker-compose up -d

echo ""
echo -e "${YELLOW}Step 3: Waiting for services to be ready...${NC}"
sleep 10

for i in {1..30}; do
    if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Services ready${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Error: Services failed to start"
        echo "Check logs: docker-compose logs"
        exit 1
    fi
    sleep 1
done

echo ""
echo -e "${YELLOW}Step 4: Running security tests...${NC}"
echo ""

./scripts/test-docker.sh

TEST_EXIT_CODE=$?

echo ""
echo -e "${YELLOW}Step 5: Cleanup${NC}"
read -p "Stop Docker containers? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    docker-compose down
    echo -e "${GREEN}Containers stopped${NC}"
else
    echo "Containers still running. Stop with: docker-compose down"
fi

exit $TEST_EXIT_CODE
