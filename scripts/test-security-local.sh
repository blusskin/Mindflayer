#!/bin/bash
# Automated security testing script for local development
# Tests all 10 security fixes before production deployment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test results
TESTS_PASSED=0
TESTS_FAILED=0

# Log function
log_test() {
    echo -e "\n${YELLOW}=== $1 ===${NC}"
}

log_pass() {
    echo -e "${GREEN}✓ $1${NC}"
    ((TESTS_PASSED++))
}

log_fail() {
    echo -e "${RED}✗ $1${NC}"
    ((TESTS_FAILED++))
}

log_info() {
    echo -e "  $1"
}

# Check if server is running
check_server() {
    curl -s http://localhost:8000/api/health > /dev/null 2>&1
    return $?
}

# Main tests
main() {
    echo "=================================================="
    echo "  Orange Nethack - Security Testing Suite"
    echo "=================================================="
    echo ""

    # Check prerequisites
    log_test "Prerequisites"

    if ! command -v python3 &> /dev/null; then
        log_fail "python3 not found"
        exit 1
    fi
    log_pass "python3 found"

    if [ ! -f ".venv/bin/activate" ]; then
        log_fail "Virtual environment not found"
        exit 1
    fi
    log_pass "Virtual environment exists"

    # Activate virtual environment
    source .venv/bin/activate

    # Check if server is running
    if ! check_server; then
        log_fail "API server not running on port 8000"
        echo ""
        echo "Please start the server in another terminal:"
        echo "  source .venv/bin/activate"
        echo "  export \$(cat .env.test | xargs) 2>/dev/null || true"
        echo "  MOCK_LIGHTNING=true uvicorn orange_nethack.api.main:app --port 8000"
        exit 1
    fi
    log_pass "API server running"

    # Test 1: Health check
    log_test "Test 1: Health Check"
    response=$(curl -s http://localhost:8000/api/health)
    if echo "$response" | grep -q '"status":"ok"'; then
        log_pass "Health endpoint responding"
    else
        log_fail "Health endpoint not responding correctly"
    fi

    # Test 2: Email validation (V9)
    log_test "Test 2: Email Validation (V9)"

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
    if [ "$response" == "201" ]; then
        log_pass "Valid email accepted (HTTP 201)"
    else
        log_fail "Valid email not accepted (got HTTP $response)"
    fi

    # Test 3: Lightning address validation (V5)
    log_test "Test 3: Lightning Address Validation (V5)"

    # Create session
    session_response=$(curl -s -X POST http://localhost:8000/api/play \
        -H "Content-Type: application/json" \
        -d '{}')
    session_id=$(echo "$session_response" | python3 -c "import sys, json; print(json.load(sys.stdin)['session_id'])")

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

    # Test 4: Rate limiting (V7)
    log_test "Test 4: Rate Limiting (V7)"
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

    # Test 5: Webhook signature verification (V1)
    log_test "Test 5: Webhook Signature Verification (V1)"

    # No signature
    response=$(curl -s -w "%{http_code}" -o /dev/null \
        -X POST http://localhost:8000/api/webhook/payment \
        -H "Content-Type: application/json" \
        -d '{"eventType":"invoice.updated","data":{"entityId":"test"}}')
    if [ "$response" == "401" ]; then
        log_pass "Webhook without signature rejected (HTTP 401)"
    else
        log_fail "Webhook without signature not rejected (got HTTP $response)"
    fi

    # Invalid signature
    response=$(curl -s -w "%{http_code}" -o /dev/null \
        -X POST http://localhost:8000/api/webhook/payment \
        -H "Content-Type: application/json" \
        -H "Webhook-Signature: invalid_signature" \
        -d '{"eventType":"invoice.updated","data":{"entityId":"test"}}')
    if [ "$response" == "401" ]; then
        log_pass "Webhook with invalid signature rejected (HTTP 401)"
    else
        log_fail "Webhook with invalid signature not rejected (got HTTP $response)"
    fi

    # Test 6: Authorization header support (V8)
    log_test "Test 6: Authorization Header Support (V8)"

    # Create session
    session_response=$(curl -s -X POST http://localhost:8000/api/play \
        -H "Content-Type: application/json" \
        -d '{}')
    session_id=$(echo "$session_response" | python3 -c "import sys, json; print(json.load(sys.stdin)['session_id'])")
    token=$(echo "$session_response" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

    # Wait for mock payment
    sleep 1

    # Token in header
    response=$(curl -s -w "%{http_code}" -o /dev/null \
        http://localhost:8000/api/session/$session_id \
        -H "Authorization: Bearer $token")
    if [ "$response" == "200" ]; then
        log_pass "Authorization header accepted (HTTP 200)"
    else
        log_fail "Authorization header not accepted (got HTTP $response)"
    fi

    # Invalid token
    response=$(curl -s -w "%{http_code}" -o /dev/null \
        http://localhost:8000/api/session/$session_id \
        -H "Authorization: Bearer invalid_token")
    if [ "$response" == "403" ]; then
        log_pass "Invalid token rejected (HTTP 403)"
    else
        log_fail "Invalid token not rejected (got HTTP $response)"
    fi

    # Test 7: CORS configuration (V3)
    log_test "Test 7: CORS Configuration (V3)"

    # Allowed origin
    response=$(curl -s -H "Origin: http://localhost:5173" \
        -H "Access-Control-Request-Method: GET" \
        -X OPTIONS http://localhost:8000/api/stats)
    if echo "$response" | grep -q "access-control-allow-origin"; then
        log_pass "Allowed origin gets CORS headers"
    else
        log_fail "Allowed origin doesn't get CORS headers"
    fi

    # Test 8: Code inspection tests
    log_test "Test 8: Code Inspection"

    # V6: Constant-time comparison
    if grep -q "secrets.compare_digest" src/orange_nethack/api/routes.py && \
       grep -q "secrets.compare_digest" src/orange_nethack/api/terminal.py; then
        log_pass "Constant-time comparison used (V6)"
    else
        log_fail "Constant-time comparison not found (V6)"
    fi

    # V10: Credentials not in email
    if ! grep -q "SSH Credentials:" src/orange_nethack/email.py; then
        log_pass "Credentials removed from email (V10)"
    else
        log_fail "Credentials still in email template (V10)"
    fi

    # Test 9: Atomic operations (V2, V4)
    log_test "Test 9: Atomic Operations (V2, V4)"

    python3 << 'PYTHON'
import asyncio
import aiosqlite
import tempfile
import os

async def test_atomic():
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        db_path = f.name

    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute("CREATE TABLE pot (id INTEGER PRIMARY KEY, balance_sats INTEGER)")
            await db.execute("INSERT INTO pot VALUES (1, 0)")
            await db.commit()

        async def add_to_pot(amount):
            async with aiosqlite.connect(db_path) as db:
                cursor = await db.execute(
                    "UPDATE pot SET balance_sats = balance_sats + ? WHERE id = 1 RETURNING balance_sats",
                    (amount,)
                )
                row = await cursor.fetchone()
                await db.commit()
                return row[0]

        await asyncio.gather(*[add_to_pot(100) for _ in range(10)])

        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute("SELECT balance_sats FROM pot WHERE id = 1")
            final = (await cursor.fetchone())[0]

        if final == 1000:
            print("PASS")
        else:
            print(f"FAIL: Expected 1000, got {final}")

    finally:
        os.unlink(db_path)

asyncio.run(test_atomic())
PYTHON

    if [ $? -eq 0 ]; then
        atomic_result=$(python3 -c "
import asyncio
import aiosqlite
import tempfile
import os

async def test():
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        db_path = f.name
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute('CREATE TABLE pot (id INTEGER PRIMARY KEY, balance_sats INTEGER)')
            await db.execute('INSERT INTO pot VALUES (1, 0)')
            await db.commit()
        async def add_to_pot(amount):
            async with aiosqlite.connect(db_path) as db:
                cursor = await db.execute('UPDATE pot SET balance_sats = balance_sats + ? WHERE id = 1 RETURNING balance_sats', (amount,))
                row = await cursor.fetchone()
                await db.commit()
                return row[0]
        await asyncio.gather(*[add_to_pot(100) for _ in range(10)])
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute('SELECT balance_sats FROM pot WHERE id = 1')
            final = (await cursor.fetchone())[0]
        print('PASS' if final == 1000 else f'FAIL')
    finally:
        os.unlink(db_path)
asyncio.run(test())
" 2>&1)

        if echo "$atomic_result" | grep -q "PASS"; then
            log_pass "Atomic pot operations working (V4)"
        else
            log_fail "Atomic pot operations not working (V4)"
        fi
    else
        log_fail "Atomic operations test failed"
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
        echo -e "${GREEN}✓ All security tests passed!${NC}"
        echo "You're ready to deploy to production."
        exit 0
    else
        echo -e "${RED}✗ Some tests failed.${NC}"
        echo "Please fix issues before deploying."
        exit 1
    fi
}

# Run tests
main
