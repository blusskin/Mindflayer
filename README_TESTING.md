# Testing the Security Fixes

Choose your testing approach based on how you plan to deploy.

## 🐋 Docker Testing (Recommended)

**Use this if:** You deploy with Docker (matches production environment)

### Quick Test

```bash
./scripts/test-docker-quick.sh
```

This will:
- Build Docker image with new dependencies
- Start container
- Run all security tests
- Show results
- Ask if you want to stop the container

### Manual Docker Testing

```bash
# 1. Build image
docker-compose build

# 2. Start services
docker-compose up -d

# 3. Run tests
./scripts/test-docker.sh

# 4. Check results and logs
docker-compose logs -f

# 5. Stop when done
docker-compose down
```

**Detailed guide:** [DOCKER_TESTING.md](DOCKER_TESTING.md)

---

## 🐍 Native Python Testing (Alternative)

**Use this if:** You want faster iteration or deploy without Docker

### Quick Test

```bash
./scripts/test-local-quick.sh
```

### Manual Native Testing

```bash
# Terminal 1: Start server
source .venv/bin/activate
MOCK_LIGHTNING=true uvicorn orange_nethack.api.main:app --port 8000

# Terminal 2: Run tests
source .venv/bin/activate
./scripts/test-security-local.sh
```

**Detailed guide:** [LOCAL_TESTING.md](LOCAL_TESTING.md)

---

## What Gets Tested

Both approaches test all 10 security fixes:

### CRITICAL ⚠️
- ✅ **V1:** Webhook signature verification
- ✅ **V2:** Payment race condition prevention
- ✅ **V3:** CORS configuration (no wildcards)
- ✅ **V4:** Atomic pot operations

### HIGH ⚡
- ✅ **V5:** Lightning address validation
- ✅ **V6:** Constant-time token comparison

### MEDIUM 📋
- ✅ **V7:** Rate limiting (5/min on /api/play)
- ✅ **V8:** Authorization header support
- ✅ **V9:** Email validation
- ✅ **V10:** Credentials not in emails

---

## Expected Results

All tests should pass:

```
==================================================
  Test Results Summary
==================================================
Passed: 15-20 (depending on test depth)
Failed: 0

✓ All security tests passed!
You're ready to deploy to production.
```

---

## Test Individual Features

Quick manual tests (server must be running):

### Test Rate Limiting
```bash
for i in {1..6}; do
  curl -X POST http://localhost:8000/api/play -d '{}'
done
# 6th request should get HTTP 429
```

### Test Email Validation
```bash
# Should fail
curl -X POST http://localhost:8000/api/play \
  -H "Content-Type: application/json" \
  -d '{"email":"invalid"}'
```

### Test Webhook Signature
```bash
# Should return 401
curl -X POST http://localhost:8000/api/webhook/payment \
  -H "Content-Type: application/json" \
  -d '{}'
```

---

## Troubleshooting

### Docker Issues

```bash
# Rebuild completely
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d

# Check logs
docker-compose logs -f

# Check inside container
docker-compose exec orange-nethack bash
source .venv/bin/activate
python3 -c "from orange_nethack.api.main import app; print('OK')"
```

### Native Python Issues

```bash
# Reinstall dependencies
source .venv/bin/activate
pip install -e .

# Check imports
python3 -c "from orange_nethack.api.main import app; print('OK')"

# Clean test database
rm -f /tmp/orange-nethack-test.db
```

---

## Next Steps

Once all tests pass:

### 1. Review Changes
```bash
git status
git diff
```

### 2. Commit
```bash
git add .
git commit -m "Add security fixes: webhook signatures, race conditions, CORS, validation, rate limiting

- V1: Webhook HMAC-SHA256 signature verification
- V2: Atomic payment confirmation (prevents race conditions)
- V3: CORS explicit origin whitelist
- V4: Atomic pot operations with RETURNING clause
- V5: Lightning address validation
- V6: Constant-time token comparison
- V7: Rate limiting with slowapi
- V8: Authorization header support
- V9: Email validation with EmailStr
- V10: Credentials removed from emails

All 10 vulnerabilities fixed and tested."
```

### 3. Deploy to Production

**For Docker deployment:**
```bash
# On production server
cd /opt/orange-nethack
git pull
docker-compose build
docker-compose down
docker-compose up -d

# Or using the install script
./deploy/install.sh
```

**For bare metal deployment:**
```bash
# On production server
cd /opt/orange-nethack
git pull
source .venv/bin/activate
pip install -e .
sudo systemctl restart orange-nethack-api orange-nethack-monitor
```

### 4. Post-Deployment Verification

```bash
# Health check
curl https://your-domain.com/api/health

# Test webhook signature requirement
curl -X POST https://your-domain.com/api/webhook/payment -d '{}'
# Should return 401

# Re-register webhook with signature
orange-nethack-cli setup-strike-webhook https://your-domain.com/api/webhook/payment
```

---

## Documentation

- **[TESTING_QUICKSTART.md](TESTING_QUICKSTART.md)** - This guide (detailed version)
- **[DOCKER_TESTING.md](DOCKER_TESTING.md)** - Complete Docker testing guide
- **[LOCAL_TESTING.md](LOCAL_TESTING.md)** - Complete native Python testing guide
- **[SECURITY.md](SECURITY.md)** - Security fixes documentation
- **[TEST_RESULTS.md](TEST_RESULTS.md)** - Test results and verification

---

## Questions?

- **Can't get tests to pass?** Check the troubleshooting sections in detailed guides
- **Docker vs Native?** Use Docker if that's how you deploy (matches production)
- **Which tests are most important?** All 10 are important, but CRITICAL > HIGH > MEDIUM
- **Ready for production?** Yes, if all tests pass and you've updated `.env` with production values

---

**Pro tip:** Run `./scripts/test-docker-quick.sh` before every deployment to catch issues early!
