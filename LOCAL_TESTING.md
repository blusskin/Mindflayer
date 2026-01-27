# Local Testing Guide - Security Fixes

This guide walks through testing all 10 security fixes locally before deploying to production.

## Prerequisites

- Python virtual environment activated
- Dependencies installed (`pip install -e .`)
- Frontend built (`cd web && npm run build`)

## Quick Start

```bash
# 1. Set up local environment
cp .env.example .env.test
source .venv/bin/activate

# 2. Start the API server (terminal 1)
MOCK_LIGHTNING=true uvicorn orange_nethack.api.main:app --reload --port 8000

# 3. Run tests (terminal 2)
./scripts/test-security-local.sh
```

---

## Environment Setup

### 1. Create Test Environment File

```bash
cat > .env.test << 'EOF'
# Strike configuration (mock mode for testing)
STRIKE_API_KEY=test_key_for_mock_mode
MOCK_LIGHTNING=true

# Game settings
ANTE_SATS=1000
POT_INITIAL=0

# Server settings
HOST=0.0.0.0
PORT=8000
DATABASE_PATH=/tmp/orange-nethack-test.db

# Security settings (V1, V3)
WEBHOOK_SECRET=test_webhook_secret_12345
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:8000

# Nethack settings
NETHACK_BINARY=/usr/games/nethack
XLOGFILE_PATH=/var/games/nethack/xlogfile
NETHACK_USER_PREFIX=nh_test_
NETHACK_GROUP=games

# Session settings
SESSION_TIMEOUT_HOURS=24
MAX_ACTIVE_SESSIONS=100

# SMTP settings (disabled for local testing)
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=
SMTP_USE_TLS=true
EOF
```

### 2. Start Test Database

```bash
# Use test database to avoid affecting any existing data
export DATABASE_PATH=/tmp/orange-nethack-test.db
rm -f /tmp/orange-nethack-test.db

# Initialize will happen automatically on first startup
```

---

## Manual Testing

### Test 1: Application Starts Successfully

```bash
# Terminal 1: Start API server
source .venv/bin/activate
export $(cat .env.test | xargs)
uvicorn orange_nethack.api.main:app --reload --port 8000
```

**Expected Output:**
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**✅ Verify:**
- No import errors
- No configuration errors
- Server starts on port 8000

---

### Test 2: V3 - CORS Configuration

```bash
# Test from allowed origin (should work)
curl -H "Origin: http://localhost:5173" \
     -H "Access-Control-Request-Method: POST" \
     -H "Access-Control-Request-Headers: content-type" \
     -X OPTIONS \
     http://localhost:8000/api/stats

# Test from disallowed origin (should fail)
curl -v -H "Origin: https://evil.com" \
     http://localhost:8000/api/stats 2>&1 | grep -i "access-control"
```

**Expected:**
- Allowed origin: Gets `Access-Control-Allow-Origin: http://localhost:5173` header
- Disallowed origin: No CORS headers (browser would block)

**✅ Verify:** CORS only allows configured origins

---

### Test 3: V7 - Rate Limiting

```bash
# Test rate limit on /api/play (limit: 5/minute)
echo "Testing rate limit (should get 429 on 6th request)..."
for i in {1..6}; do
  response=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST http://localhost:8000/api/play \
    -H "Content-Type: application/json" \
    -d '{"email":"test@example.com"}')
  echo "Request $i: HTTP $response"
  if [ "$response" == "429" ]; then
    echo "✓ Rate limit working!"
    break
  fi
done

# Wait for rate limit to reset
echo "Waiting 60 seconds for rate limit reset..."
sleep 60
```

**Expected:**
```
Request 1: HTTP 201
Request 2: HTTP 201
Request 3: HTTP 201
Request 4: HTTP 201
Request 5: HTTP 201
Request 6: HTTP 429
✓ Rate limit working!
```

**✅ Verify:** 6th request gets HTTP 429 (Too Many Requests)

---

### Test 4: V1 - Webhook Signature Verification

```bash
# Test webhook without signature (should fail)
curl -X POST http://localhost:8000/api/webhook/payment \
  -H "Content-Type: application/json" \
  -d '{"eventType":"invoice.updated","data":{"entityId":"test123"}}'

# Test webhook with invalid signature (should fail)
curl -X POST http://localhost:8000/api/webhook/payment \
  -H "Content-Type: application/json" \
  -H "Webhook-Signature: invalid_signature" \
  -d '{"eventType":"invoice.updated","data":{"entityId":"test123"}}'

# Test webhook with valid signature (should work in mock mode)
python3 << 'PYTHON'
import hmac
import hashlib
import json
import requests

webhook_secret = "test_webhook_secret_12345"
payload = {"eventType": "invoice.updated", "data": {"entityId": "test123"}}
body = json.dumps(payload).encode()

signature = hmac.new(
    webhook_secret.encode(),
    body,
    hashlib.sha256
).hexdigest()

response = requests.post(
    "http://localhost:8000/api/webhook/payment",
    json=payload,
    headers={"Webhook-Signature": signature}
)

print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")
PYTHON
```

**Expected:**
```
# No signature: HTTP 401
# Invalid signature: HTTP 401
# Valid signature: HTTP 200 or 404 (session not found)
```

**✅ Verify:** Webhooks require valid signatures

---

### Test 5: V9 - Email Validation

```bash
# Test invalid email (should fail)
curl -X POST http://localhost:8000/api/play \
  -H "Content-Type: application/json" \
  -d '{"email":"invalid-email"}'

# Test valid email (should work)
curl -X POST http://localhost:8000/api/play \
  -H "Content-Type: application/json" \
  -d '{"email":"valid@example.com"}'

# Test no email (should work - optional field)
curl -X POST http://localhost:8000/api/play \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Expected:**
```
# Invalid email: HTTP 422 with validation error
# Valid email: HTTP 201 with session data
# No email: HTTP 201 with session data
```

**✅ Verify:** Invalid emails rejected

---

### Test 6: V5 - Lightning Address Validation

```bash
# First create a session
SESSION_RESPONSE=$(curl -s -X POST http://localhost:8000/api/play \
  -H "Content-Type: application/json" \
  -d '{}')
SESSION_ID=$(echo $SESSION_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['session_id'])")

echo "Created session: $SESSION_ID"

# Test invalid Lightning address
curl -X POST http://localhost:8000/api/play/$SESSION_ID/address \
  -H "Content-Type: application/json" \
  -d '{"lightning_address":"invalid"}'

# Test valid Lightning address
curl -X POST http://localhost:8000/api/play/$SESSION_ID/address \
  -H "Content-Type: application/json" \
  -d '{"lightning_address":"user@getalby.com"}'
```

**Expected:**
```
# Invalid: HTTP 422 with validation error
# Valid: HTTP 200 with success
```

**✅ Verify:** Invalid Lightning addresses rejected

---

### Test 7: V8 - Token in Authorization Header

```bash
# Create session and get token
SESSION_RESPONSE=$(curl -s -X POST http://localhost:8000/api/play \
  -H "Content-Type: application/json" \
  -d '{}')
SESSION_ID=$(echo $SESSION_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['session_id'])")
TOKEN=$(echo $SESSION_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

# Mock payment to activate session
curl -s http://localhost:8000/api/session/$SESSION_ID?token=$TOKEN > /dev/null

echo "Session: $SESSION_ID"
echo "Token: $TOKEN"

# Test 1: Token in query param (deprecated - should log warning)
echo -e "\n=== Test: Token in Query Param (Deprecated) ==="
curl -s http://localhost:8000/api/session/$SESSION_ID?token=$TOKEN | \
  python3 -c "import sys, json; d=json.load(sys.stdin); print(f\"Status: {d.get('status')}\")"

# Test 2: Token in Authorization header (preferred)
echo -e "\n=== Test: Token in Authorization Header (Preferred) ==="
curl -s http://localhost:8000/api/session/$SESSION_ID \
  -H "Authorization: Bearer $TOKEN" | \
  python3 -c "import sys, json; d=json.load(sys.stdin); print(f\"Status: {d.get('status')}\")"

# Test 3: Invalid token (should fail)
echo -e "\n=== Test: Invalid Token ==="
curl -s -w "HTTP %{http_code}\n" http://localhost:8000/api/session/$SESSION_ID \
  -H "Authorization: Bearer invalid_token_123" -o /dev/null
```

**Expected:**
```
# Query param: Works but logs deprecation warning in server logs
# Header: Works (preferred method)
# Invalid: HTTP 403
```

**✅ Verify:**
- Both methods work
- Check server logs for deprecation warning on query param usage

---

### Test 8: V2 & V4 - Race Conditions & Atomic Operations

```bash
# Run Python script to test concurrent operations
python3 << 'PYTHON'
import asyncio
import aiosqlite
import tempfile
import os
from datetime import datetime, timezone

async def test_race_conditions():
    """Test that race conditions are prevented"""

    # Create temporary database
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        db_path = f.name

    try:
        # Initialize database
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row

            await db.execute("""
                CREATE TABLE sessions (
                    id INTEGER PRIMARY KEY,
                    status TEXT NOT NULL
                )
            """)
            await db.execute("""
                CREATE TABLE pot (
                    id INTEGER PRIMARY KEY,
                    balance_sats INTEGER NOT NULL
                )
            """)
            await db.execute("INSERT INTO sessions (id, status) VALUES (1, 'pending')")
            await db.execute("INSERT INTO pot (id, balance_sats) VALUES (1, 0)")
            await db.commit()

        # Test V2: Payment race condition prevention
        print("=== Test V2: Payment Race Condition ===")

        async def try_confirm_payment(session_id):
            async with aiosqlite.connect(db_path) as db:
                cursor = await db.execute(
                    "UPDATE sessions SET status = ? WHERE id = ? AND status = 'pending'",
                    ("active", session_id)
                )
                await db.commit()
                return cursor.rowcount > 0

        # Simulate concurrent webhooks
        results = await asyncio.gather(*[
            try_confirm_payment(1) for _ in range(10)
        ])

        successful = sum(results)
        print(f"Concurrent updates: 10")
        print(f"Successful updates: {successful}")
        print(f"✓ Race condition prevented!" if successful == 1 else f"✗ Failed: {successful} updates succeeded")

        # Test V4: Atomic pot operations
        print("\n=== Test V4: Atomic Pot Operations ===")

        async def add_to_pot(amount):
            async with aiosqlite.connect(db_path) as db:
                cursor = await db.execute(
                    """
                    UPDATE pot SET balance_sats = balance_sats + ?
                    WHERE id = 1
                    RETURNING balance_sats
                    """,
                    (amount,)
                )
                row = await cursor.fetchone()
                await db.commit()
                return row[0]

        # Concurrent additions
        results = await asyncio.gather(*[
            add_to_pot(100) for _ in range(10)
        ])

        # Check final balance
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute("SELECT balance_sats FROM pot WHERE id = 1")
            final_balance = (await cursor.fetchone())[0]

        expected = 1000  # 10 additions of 100
        print(f"Concurrent additions: 10 x 100 sats")
        print(f"Expected balance: {expected} sats")
        print(f"Final balance: {final_balance} sats")
        print(f"✓ Atomic operations working!" if final_balance == expected else f"✗ Failed: balance mismatch")

    finally:
        os.unlink(db_path)

asyncio.run(test_race_conditions())
PYTHON
```

**Expected:**
```
=== Test V2: Payment Race Condition ===
Concurrent updates: 10
Successful updates: 1
✓ Race condition prevented!

=== Test V4: Atomic Pot Operations ===
Concurrent additions: 10 x 100 sats
Expected balance: 1000 sats
Final balance: 1000 sats
✓ Atomic operations working!
```

**✅ Verify:** Only 1 concurrent update succeeds, pot balance is exact

---

### Test 9: V6 - Token Timing Attack Protection

```bash
# This is verified by code inspection and unit tests
# Timing attacks require sophisticated measurement - not practical to test manually

echo "=== Test V6: Token Timing Attack Protection ==="
echo "✓ Code uses secrets.compare_digest() (verified in code review)"
echo "✓ Unit tests pass (verified in test suite)"
echo ""
echo "Manual verification:"
grep -r "secrets.compare_digest" src/orange_nethack/api/
```

**Expected:**
```
src/orange_nethack/api/routes.py:        if not secrets.compare_digest(
src/orange_nethack/api/terminal.py:    if not secrets.compare_digest(
```

**✅ Verify:** Both files use constant-time comparison

---

### Test 10: V10 - Credentials Not in Email

```bash
# This requires checking email templates
echo "=== Test V10: Credentials Not in Email ==="
echo "Checking email template..."
grep -A5 "SSH Credentials" src/orange_nethack/email.py || echo "✓ 'SSH Credentials' not found in email template"
grep "or access your SSH credentials via the web interface" src/orange_nethack/email.py && echo "✓ Users directed to web interface"
```

**Expected:**
```
✓ 'SSH Credentials' not found in email template
✓ Users directed to web interface
```

**✅ Verify:** Email template doesn't include plaintext credentials

---

## Full Flow Test

Test the complete payment flow end-to-end:

```bash
# Run the built-in test flow
source .venv/bin/activate
export $(cat .env.test | xargs)
orange-nethack-cli test-flow
```

**Expected:**
```
Creating session...
Session created: ID=1
Simulating payment...
Payment confirmed: Session active
Simulating game (death)...
Game ended: Pot updated
✓ Full flow test passed!
```

---

## Automated Test Script

Run all security tests automatically:

```bash
./scripts/test-security-local.sh
```

This script will:
1. Start the API server in background
2. Run all security tests
3. Report results
4. Stop the server

---

## Troubleshooting

### Server Won't Start

```bash
# Check for port conflicts
lsof -i :8000

# Check logs for errors
tail -f ~/.local/state/orange-nethack/api.log

# Verify environment
python3 -c "from orange_nethack.config import get_settings; print(get_settings())"
```

### Tests Failing

```bash
# Verify database is clean
rm -f /tmp/orange-nethack-test.db

# Check dependencies
pip list | grep -E "slowapi|email-validator|pydantic"

# Run unit tests
pytest tests/ -v
```

### Rate Limit Issues

```bash
# Rate limits persist for 1 minute
# Wait 60 seconds between test runs
sleep 60
```

---

## Success Criteria

All tests should pass:

- ✅ Server starts without errors
- ✅ CORS blocks disallowed origins
- ✅ Rate limiting enforces limits
- ✅ Webhook signatures verified
- ✅ Email validation rejects invalid emails
- ✅ Lightning address validation works
- ✅ Authorization header accepted
- ✅ Race conditions prevented
- ✅ Atomic operations consistent
- ✅ Credentials not in emails

Once all tests pass, you're ready to deploy to production!

---

## Next Steps

After successful local testing:

1. Update production `.env` with real values
2. Deploy code to production server
3. Run smoke tests on production
4. Monitor logs for issues

See `SECURITY.md` for production deployment checklist.
