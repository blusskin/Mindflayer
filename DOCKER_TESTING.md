# Docker Testing Guide - Security Fixes

Test all security fixes locally using Docker (matching your existing workflow).

## Quick Start

```bash
# 1. Build with new dependencies
docker-compose build

# 2. Start services
docker-compose up -d

# 3. Run security tests
./scripts/test-docker.sh

# 4. View logs
docker-compose logs -f

# 5. Stop when done
docker-compose down
```

---

## Setup

### 1. Create Test Environment

```bash
# Create .env for testing (if you don't have one)
cat > .env << 'EOF'
# Strike configuration (mock mode for testing)
STRIKE_API_KEY=test_key_for_docker
MOCK_LIGHTNING=true

# Security settings (NEW - V1, V3)
WEBHOOK_SECRET=test_webhook_secret_docker_12345
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:8000

# Game settings
ANTE_SATS=1000
POT_INITIAL=0

# SMTP (disabled for local testing)
SMTP_HOST=
EOF
```

### 2. Rebuild Docker Image

The new dependencies need to be installed in the Docker image:

```bash
docker-compose build
```

**What gets installed:**
- `slowapi>=0.1.9` (rate limiting)
- `pydantic[email]>=2.5.0` (email validation)

---

## Running Tests

### Option 1: Automated Test Script

```bash
./scripts/test-docker.sh
```

This will:
1. Check if container is running
2. Run all 10 security tests
3. Show pass/fail summary

### Option 2: Manual Testing

```bash
# Start container
docker-compose up -d

# Wait for startup
sleep 5

# Run individual tests
docker-compose exec orange-nethack bash -c "source .venv/bin/activate && python3 -c 'from orange_nethack.api.main import app; print(\"✓ Imports working\")'"

# Test API endpoints
curl http://localhost:8000/api/health

# View logs
docker-compose logs -f
```

---

## Security Tests (Docker)

### Test 1: Container Starts Successfully

```bash
docker-compose up -d
docker-compose ps
```

**Expected:**
```
NAME                  STATUS
orange-nethack-...    Up 10 seconds
```

**✅ Verify:**
- Container status is "Up"
- No crash loops

---

### Test 2: Dependencies Installed

```bash
docker-compose exec orange-nethack bash -c "pip list | grep -E 'slowapi|email-validator'"
```

**Expected:**
```
email-validator    2.3.0
slowapi           0.1.9
```

**✅ Verify:** Both packages present

---

### Test 3: Application Imports

```bash
docker-compose exec orange-nethack bash -c "
source .venv/bin/activate && python3 << 'PYTHON'
try:
    from orange_nethack.api.main import app
    from orange_nethack.api.limiter import limiter
    from orange_nethack.models import PlayRequest, SetAddressRequest
    print('✓ All imports successful')
except Exception as e:
    print(f'✗ Import failed: {e}')
    exit(1)
PYTHON
"
```

**Expected:**
```
✓ All imports successful
```

---

### Test 4: Health Check

```bash
curl -s http://localhost:8000/api/health | python3 -m json.tool
```

**Expected:**
```json
{
  "status": "ok",
  "pot_balance": 0,
  "active_sessions": 0,
  "mock_mode": true
}
```

---

### Test 5: Email Validation (V9)

```bash
# Invalid email - should fail
curl -X POST http://localhost:8000/api/play \
  -H "Content-Type: application/json" \
  -d '{"email":"invalid-email"}' | python3 -m json.tool

# Valid email - should succeed
curl -X POST http://localhost:8000/api/play \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com"}' | python3 -m json.tool
```

**Expected:**
```
# Invalid: HTTP 422 with validation error
# Valid: HTTP 201 with session data
```

---

### Test 6: Rate Limiting (V7)

```bash
echo "Testing rate limit (should get 429 on 6th request)..."
for i in {1..6}; do
  response=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST http://localhost:8000/api/play \
    -H "Content-Type: application/json" \
    -d '{}')
  echo "Request $i: HTTP $response"
  if [ "$response" == "429" ]; then
    echo "✓ Rate limit enforced!"
    break
  fi
done

# Wait 60 seconds for reset
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
✓ Rate limit enforced!
```

---

### Test 7: Webhook Signature (V1)

```bash
# Without signature - should fail
curl -X POST http://localhost:8000/api/webhook/payment \
  -H "Content-Type: application/json" \
  -d '{"eventType":"invoice.updated","data":{"entityId":"test"}}'

# Should return: HTTP 401 or 200 (in mock mode without signature may be allowed)
```

**Expected in production mode:**
```
HTTP 401 Unauthorized
```

---

### Test 8: Lightning Address Validation (V5)

```bash
# Create session
SESSION=$(curl -s -X POST http://localhost:8000/api/play \
  -H "Content-Type: application/json" \
  -d '{}')
SESSION_ID=$(echo $SESSION | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")

echo "Session ID: $SESSION_ID"

# Invalid address
curl -X POST http://localhost:8000/api/play/$SESSION_ID/address \
  -H "Content-Type: application/json" \
  -d '{"lightning_address":"invalid"}' | python3 -m json.tool

# Valid address
curl -X POST http://localhost:8000/api/play/$SESSION_ID/address \
  -H "Content-Type: application/json" \
  -d '{"lightning_address":"user@getalby.com"}' | python3 -m json.tool
```

**Expected:**
```
# Invalid: HTTP 422 with validation error
# Valid: HTTP 200 with success
```

---

### Test 9: CORS Configuration (V3)

```bash
# Test CORS headers
curl -v -H "Origin: http://localhost:5173" \
  http://localhost:8000/api/stats 2>&1 | grep -i "access-control"
```

**Expected:**
```
< access-control-allow-origin: http://localhost:5173
```

---

### Test 10: CLI Commands

```bash
# Test CLI inside container
docker-compose exec orange-nethack bash -c "
source .venv/bin/activate
orange-nethack-cli --help
"

# Run test flow
docker-compose exec orange-nethack bash -c "
source .venv/bin/activate
orange-nethack-cli test-flow
"
```

**Expected:**
```
Creating session...
Session created: ID=1
Simulating payment...
Payment confirmed
✓ Test flow completed successfully
```

---

## Viewing Logs

```bash
# All logs
docker-compose logs -f

# Just API server logs
docker-compose logs -f orange-nethack | grep "INFO"

# Check for errors
docker-compose logs orange-nethack | grep -i error
```

---

## Inside Container Testing

For detailed testing, exec into the container:

```bash
# Enter container
docker-compose exec orange-nethack bash

# Activate venv
source .venv/bin/activate

# Run Python tests
python3 -c "from orange_nethack.api.main import app; print('OK')"

# Check configuration
python3 << 'PYTHON'
from orange_nethack.config import get_settings
settings = get_settings()
print(f"CORS origins: {settings.cors_origins}")
print(f"Webhook secret configured: {bool(settings.webhook_secret)}")
print(f"Mock mode: {settings.mock_lightning}")
PYTHON

# Run CLI commands
orange-nethack-cli --help

# Exit container
exit
```

---

## Database Access

```bash
# Access database inside container
docker-compose exec orange-nethack bash -c "
sqlite3 /var/lib/orange-nethack/db.sqlite << 'SQL'
.headers on
.mode column
SELECT * FROM sessions LIMIT 5;
SELECT * FROM pot;
SQL
"
```

---

## Troubleshooting

### Container Won't Start

```bash
# Check build logs
docker-compose build --no-cache

# Check container logs
docker-compose logs orange-nethack

# Check if port is available
lsof -i :8000
```

### Dependencies Not Installed

```bash
# Rebuild image
docker-compose build --no-cache

# Verify inside container
docker-compose exec orange-nethack pip list | grep slowapi
```

### Tests Failing

```bash
# Restart services
docker-compose restart

# Fresh start
docker-compose down
docker-compose up -d

# Wait for services to be ready
sleep 10
```

### Database Issues

```bash
# Reset database
docker-compose down -v  # Removes volumes
docker-compose up -d
```

---

## Clean Slate Testing

Start completely fresh:

```bash
# Stop and remove everything
docker-compose down -v

# Remove old image
docker-compose rm -f
docker image rm orange-nethack_orange-nethack

# Rebuild from scratch
docker-compose build --no-cache

# Start fresh
docker-compose up -d

# Wait for initialization
sleep 10

# Run tests
./scripts/test-docker.sh
```

---

## Production Testing in Docker

To test with production-like settings:

```bash
# Create production .env
cat > .env << 'EOF'
STRIKE_API_KEY=your_actual_api_key
MOCK_LIGHTNING=false
WEBHOOK_SECRET=your_webhook_secret
ALLOWED_ORIGINS=https://your-domain.com
ANTE_SATS=1000
POT_INITIAL=0
EOF

# Rebuild and start
docker-compose down
docker-compose build
docker-compose up -d

# Test real payment flow
# (requires actual Strike API access)
```

---

## Automated Testing Script

For convenience, use the Docker test script:

```bash
./scripts/test-docker.sh
```

See script contents for details on what gets tested.

---

## Success Criteria

All tests should pass:

- ✅ Container builds successfully
- ✅ Dependencies installed (slowapi, email-validator)
- ✅ Application imports without errors
- ✅ Health endpoint responds
- ✅ Email validation rejects invalid emails
- ✅ Lightning address validation works
- ✅ Rate limiting enforces limits
- ✅ CORS headers present for allowed origins
- ✅ CLI commands work
- ✅ Test flow completes successfully

---

## Next Steps

After successful Docker testing:

1. **Commit changes:**
   ```bash
   git add .
   git commit -m "Add security fixes with Docker support"
   ```

2. **Push to repository:**
   ```bash
   git push origin main
   ```

3. **Deploy to production server:**
   - Pull latest code
   - Update production `.env`
   - Rebuild Docker image
   - Restart services
   - Run smoke tests

See `SECURITY.md` for production deployment checklist.
