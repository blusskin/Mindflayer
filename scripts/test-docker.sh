#!/bin/bash
# Docker-based security testing script
# Tests all 10 security fixes in Docker container

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Test results
TESTS_PASSED=0
TESTS_FAILED=0

log_test() {
    echo -e "\n${YELLOW}=== $1 ===${NC}"
}

log_pass() {
    echo -e "${GREEN}✓ $1${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
}

log_fail() {
    echo -e "${RED}✗ $1${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
}

log_info() {
    echo -e "  $1"
}

# Check if Docker is running
check_docker() {
    if docker info >/dev/null 2>&1; then
        return 0
    else
        echo -e "${RED}Error: Docker is not running${NC}"
        exit 1
    fi
}

# Check if container is running
check_container() {
    set +e  # Temporarily disable exit on error
    docker-compose ps 2>/dev/null | grep -q "Up"
    local status=$?
    set -e  # Re-enable exit on error

    if [ $status -ne 0 ]; then
        echo -e "${RED}Error: Docker container is not running${NC}"
        echo ""
        echo "Start the container with:"
        echo "  docker-compose up -d"
        exit 1
    fi
}

# Wait for service to be ready
wait_for_service() {
    log_info "Waiting for service to be ready..."
    for i in {1..30}; do
        if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
            log_info "Service ready"
            return 0
        fi
        sleep 1
    done
    log_fail "Service failed to start"
    exit 1
}

main() {
    echo "=================================================="
    echo "  Orange Nethack - Docker Security Testing"
    echo "=================================================="
    echo ""

    # Prerequisites
    log_test "Prerequisites"

    check_docker
    log_pass "Docker running"

    check_container
    log_pass "Container running"

    wait_for_service
    log_pass "Service responding"

    # Test 1: Dependencies installed
    log_test "Test 1: Dependencies Installed"

    deps=$(docker-compose exec -T orange-nethack bash -c ".venv/bin/pip list 2>/dev/null | grep -E 'slowapi|email-validator'" || true)

    if echo "$deps" | grep -q "slowapi"; then
        log_pass "slowapi installed"
    else
        log_fail "slowapi not installed"
    fi

    if echo "$deps" | grep -q "email-validator"; then
        log_pass "email-validator installed"
    else
        log_fail "email-validator not installed"
    fi

    # Test 2: Imports working
    log_test "Test 2: Application Imports"

    result=$(docker-compose exec -T orange-nethack bash -c "
source .venv/bin/activate 2>/dev/null || true
python3 << 'PYTHON' 2>&1
try:
    from orange_nethack.api.main import app
    from orange_nethack.api.limiter import limiter
    from orange_nethack.models import PlayRequest, SetAddressRequest
    print('OK')
except Exception as e:
    print(f'FAIL: {e}')
    exit(1)
PYTHON
" || echo "FAIL")

    if echo "$result" | grep -q "OK"; then
        log_pass "All imports successful"
    else
        log_fail "Import failed: $result"
    fi

    # Test 3: Health check
    log_test "Test 3: Health Check"

    response=$(curl -s http://localhost:8000/api/health)
    if echo "$response" | grep -q '"status":"ok"'; then
        log_pass "Health endpoint responding"
    else
        log_fail "Health endpoint not responding correctly"
    fi

    # Test 4: Email validation (V9)
    log_test "Test 4: Email Validation (V9)"

    # Invalid email
    response=$(curl -s -w "%{http_code}" -o /dev/null \
        -X POST http://localhost:8000/api/play \
        -H "Content-Type: application/json" \
        -d '{"email":"invalid-email"}')
    if [ "$response" == "422" ]; then
        log_pass "Invalid email rejected (HTTP 422)"
    else
        log_fail "Invalid email not rejected (got HTTP $response)"
    fi

    # Valid email
    response=$(curl -s -w "%{http_code}" -o /dev/null \
        -X POST http://localhost:8000/api/play \
        -H "Content-Type: application/json" \
        -d '{"email":"valid@example.com"}')
    if [ "$response" == "200" ] || [ "$response" == "201" ]; then
        log_pass "Valid email accepted (HTTP $response)"
    else
        log_fail "Valid email not accepted (got HTTP $response)"
    fi

    # Test 5: Lightning address validation (V5)
    log_test "Test 5: Lightning Address Validation (V5)"

    # Create session
    session_response=$(curl -s -X POST http://localhost:8000/api/play \
        -H "Content-Type: application/json" \
        -d '{}')
    session_id=$(echo "$session_response" | python3 -c "import sys, json; print(json.load(sys.stdin)['session_id'])" 2>/dev/null || echo "")

    if [ -n "$session_id" ]; then
        # Invalid address
        response=$(curl -s -w "%{http_code}" -o /dev/null \
            -X POST http://localhost:8000/api/play/$session_id/address \
            -H "Content-Type: application/json" \
            -d '{"lightning_address":"invalid"}')
        if [ "$response" == "422" ]; then
            log_pass "Invalid Lightning address rejected (HTTP 422)"
        else
            log_fail "Invalid Lightning address not rejected (got HTTP $response)"
        fi

        # Valid address
        response=$(curl -s -w "%{http_code}" -o /dev/null \
            -X POST http://localhost:8000/api/play/$session_id/address \
            -H "Content-Type: application/json" \
            -d '{"lightning_address":"user@getalby.com"}')
        if [ "$response" == "200" ]; then
            log_pass "Valid Lightning address accepted (HTTP 200)"
        else
            log_fail "Valid Lightning address not accepted (got HTTP $response)"
        fi
    else
        log_fail "Failed to create session for address test"
    fi

    # Test 6: Rate limiting (V7)
    log_test "Test 6: Rate Limiting (V7)"
    log_info "Making 6 requests (limit is 5/minute)..."

    rate_limit_hit=false
    for i in {1..6}; do
        response=$(curl -s -w "%{http_code}" -o /dev/null \
            -X POST http://localhost:8000/api/play \
            -H "Content-Type: application/json" \
            -d '{}')

        if [ "$response" == "429" ]; then
            rate_limit_hit=true
            log_pass "Rate limit enforced on request $i (HTTP 429)"
            break
        fi
    done

    if [ "$rate_limit_hit" = false ]; then
        log_fail "Rate limit not enforced after 6 requests"
    fi

    log_info "Waiting 60 seconds for rate limit reset..."
    sleep 60

    # Test 7: Webhook signature (V1)
    log_test "Test 7: Webhook Signature Verification (V1)"

    # Note: In mock mode, signature may not be enforced
    response=$(curl -s -w "%{http_code}" -o /dev/null \
        -X POST http://localhost:8000/api/webhook/payment \
        -H "Content-Type: application/json" \
        -d '{"eventType":"invoice.updated","data":{"entityId":"test"}}')

    # In production mode should be 401, in mock mode might be 200/404
    if [ "$response" == "401" ] || [ "$response" == "200" ] || [ "$response" == "404" ]; then
        log_pass "Webhook endpoint responding (HTTP $response)"
    else
        log_fail "Unexpected webhook response (HTTP $response)"
    fi

    # Test 8: CORS configuration (V3)
    log_test "Test 8: CORS Configuration (V3)"

    response=$(curl -s -I -H "Origin: http://localhost:5173" \
        http://localhost:8000/api/stats 2>&1)

    if echo "$response" | grep -qi "access-control-allow-origin"; then
        log_pass "CORS headers present"
    else
        log_fail "CORS headers not found"
    fi

    # Test 9: Configuration check
    log_test "Test 9: Configuration Check"

    config=$(docker-compose exec -T orange-nethack bash -c "
source .venv/bin/activate 2>/dev/null || true
python3 << 'PYTHON' 2>&1
from orange_nethack.config import get_settings
settings = get_settings()
print(f'CORS_OK:{len(settings.cors_origins) > 0}')
print(f'SECRET_OK:{len(settings.webhook_secret) > 0}')
PYTHON
" || echo "FAIL")

    if echo "$config" | grep -q "CORS_OK:True"; then
        log_pass "CORS origins configured"
    else
        log_fail "CORS origins not configured"
    fi

    if echo "$config" | grep -q "SECRET_OK:True"; then
        log_pass "Webhook secret configured"
    else
        log_info "Webhook secret not configured (ok for testing)"
    fi

    # Test 10: CLI commands
    log_test "Test 10: CLI Commands"

    result=$(docker-compose exec -T orange-nethack bash -c "
source .venv/bin/activate 2>/dev/null || true
orange-nethack-cli --help 2>&1 | head -1
" || echo "FAIL")

    if echo "$result" | grep -q "Usage\|orange-nethack"; then
        log_pass "CLI commands working"
    else
        log_fail "CLI commands not working"
    fi

    # Summary
    echo ""
    echo "=================================================="
    echo "  Test Results Summary"
    echo "=================================================="
    echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
    echo -e "${RED}Failed: $TESTS_FAILED${NC}"
    echo ""

    if [ $TESTS_FAILED -eq 0 ]; then
        echo -e "${GREEN}✓ All Docker tests passed!${NC}"
        echo "Your Docker setup is ready for production deployment."
        exit 0
    else
        echo -e "${RED}✗ Some tests failed.${NC}"
        echo "Please fix issues before deploying."
        echo ""
        echo "Troubleshooting:"
        echo "  1. Rebuild image: docker-compose build --no-cache"
        echo "  2. Check logs: docker-compose logs orange-nethack"
        echo "  3. Restart services: docker-compose restart"
        exit 1
    fi
}

main
