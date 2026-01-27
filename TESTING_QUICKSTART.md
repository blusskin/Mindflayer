# Testing Quick Start

Quick guide to test all security fixes locally before production deployment.

## Option 1: Docker (Recommended - Matches Production)

This is the recommended approach since you're using Docker for deployment:

```bash
./scripts/test-docker-quick.sh
```

**What it does:**
1. ✅ Builds Docker image with new dependencies
2. ✅ Starts container
3. ✅ Runs all 10 security tests
4. ✅ Shows pass/fail results
5. ✅ Optionally stops container when done

**Or manually:**

```bash
# Build and start
docker-compose build
docker-compose up -d

# Run tests
./scripts/test-docker.sh

# View logs
docker-compose logs -f

# Stop when done
docker-compose down
```

See **[DOCKER_TESTING.md](DOCKER_TESTING.md)** for detailed Docker testing guide.

---

## Option 2: Native Python (Alternative)

This script starts the server, runs all tests, and stops automatically:

```bash
./scripts/test-local-quick.sh
```

**What it does:**
1. Creates test environment (`.env.test`)
2. Starts API server in background
3. Runs all 10 security tests
4. Shows pass/fail summary
5. Stops server automatically

**Expected output:**
```
================================================
  Orange Nethack - Quick Local Test
================================================

Step 1: Starting API server...
✓ Server started

Step 2: Running security tests...

=== Test 1: Health Check ===
✓ Health endpoint responding

=== Test 2: Email Validation (V9) ===
✓ Invalid email rejected (HTTP 422)
✓ Valid email accepted (HTTP 201)

... (more tests) ...

================================================
  Test Results Summary
================================================
Passed: 15
Failed: 0

✓ All security tests passed!
You're ready to deploy to production.
```

---

## Option 2: Manual Testing

For more control, run server and tests separately:

### Terminal 1: Start Server

```bash
# Create test environment
cat > .env.test << 'EOF'
MOCK_LIGHTNING=true
WEBHOOK_SECRET=test_webhook_secret_12345
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:8000
DATABASE_PATH=/tmp/orange-nethack-test.db
EOF

# Start server
source .venv/bin/activate
export $(cat .env.test | xargs)
uvicorn orange_nethack.api.main:app --reload --port 8000
```

### Terminal 2: Run Tests

```bash
source .venv/bin/activate
./scripts/test-security-local.sh
```

---

## Option 3: Individual Security Tests

Test specific security fixes one at a time (server must be running):

### Test Email Validation (V9)

```bash
# Invalid email - should fail
curl -X POST http://localhost:8000/api/play \
  -H "Content-Type: application/json" \
  -d '{"email":"invalid-email"}'

# Valid email - should succeed
curl -X POST http://localhost:8000/api/play \
  -H "Content-Type: application/json" \
  -d '{"email":"valid@example.com"}'
```

### Test Rate Limiting (V7)

```bash
# Make 6 requests - 6th should get 429
for i in {1..6}; do
  echo "Request $i:"
  curl -s -w "HTTP %{http_code}\n" -o /dev/null \
    -X POST http://localhost:8000/api/play \
    -H "Content-Type: application/json" \
    -d '{}'
done
```

### Test Webhook Signatures (V1)

```bash
# Without signature - should fail
curl -X POST http://localhost:8000/api/webhook/payment \
  -H "Content-Type: application/json" \
  -d '{"eventType":"invoice.updated","data":{"entityId":"test"}}'

# Should return: HTTP 401 Unauthorized
```

### Test Lightning Address Validation (V5)

```bash
# Create session
SESSION=$(curl -s -X POST http://localhost:8000/api/play -H "Content-Type: application/json" -d '{}')
SESSION_ID=$(echo $SESSION | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")

# Invalid address - should fail
curl -X POST http://localhost:8000/api/play/$SESSION_ID/address \
  -H "Content-Type: application/json" \
  -d '{"lightning_address":"invalid"}'

# Valid address - should succeed
curl -X POST http://localhost:8000/api/play/$SESSION_ID/address \
  -H "Content-Type: application/json" \
  -d '{"lightning_address":"user@getalby.com"}'
```

---

## Detailed Testing Guide

For comprehensive testing instructions, see:
- **`LOCAL_TESTING.md`** - Complete manual testing guide
- **`TEST_RESULTS.md`** - Test results and verification
- **`SECURITY.md`** - Security fixes documentation

---

## Troubleshooting

### Server won't start

```bash
# Check if port is in use
lsof -i :8000

# Check for errors
tail -f /tmp/orange-nethack-server.log

# Verify installation
source .venv/bin/activate
python3 -c "from orange_nethack.api.main import app; print('OK')"
```

### Tests failing

```bash
# Clean test database
rm -f /tmp/orange-nethack-test.db

# Check dependencies
pip list | grep -E "slowapi|email-validator"

# Wait for rate limits to reset
sleep 60
```

### Import errors

```bash
# Reinstall dependencies
source .venv/bin/activate
pip install -e .
```

---

## Success Criteria

All tests should pass:

- ✅ Server starts without errors
- ✅ Email validation rejects invalid emails
- ✅ Lightning address validation works
- ✅ Rate limiting enforces limits
- ✅ Webhook signatures required
- ✅ Authorization header accepted
- ✅ CORS configured correctly
- ✅ Atomic operations working
- ✅ Token comparison is constant-time
- ✅ Credentials not in emails

Once all pass, you're ready for production!

---

## Production Deployment

After successful local testing:

1. **Update production `.env`:**
   ```bash
   MOCK_LIGHTNING=false
   WEBHOOK_SECRET=<from setup-strike-webhook>
   ALLOWED_ORIGINS=https://your-domain.com
   ```

2. **Deploy and verify:**
   ```bash
   # On production server
   git pull
   source .venv/bin/activate
   pip install -e .
   orange-nethack-cli setup-strike-webhook https://your-domain.com/api/webhook/payment
   sudo systemctl restart orange-nethack-api orange-nethack-monitor
   ```

3. **Smoke test:**
   ```bash
   curl https://your-domain.com/api/health
   ```

See `SECURITY.md` for complete production checklist.
