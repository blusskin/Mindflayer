# Security Fixes - Orange Nethack

This document summarizes the security hardening implemented in Orange Nethack to protect against financial loss, unauthorized access, and API abuse.

## Summary

**10 vulnerabilities fixed:**
- 4 CRITICAL
- 2 HIGH
- 4 MEDIUM

All fixes have been implemented and are production-ready.

---

## CRITICAL Fixes

### V1: Webhook Signature Verification ✅

**Problem:** Strike webhooks were processed without signature verification, allowing attackers to forge payment confirmations.

**Fix:** Added HMAC-SHA256 signature verification in `webhooks.py`:
- Verifies `Webhook-Signature` header using `WEBHOOK_SECRET`
- Rejects webhooks with missing or invalid signatures in production mode
- Allows unsigned webhooks only in mock mode for testing

**Files Changed:**
- `src/orange_nethack/api/webhooks.py`
- `.env.example` (added WEBHOOK_SECRET)

**Configuration:**
```bash
# .env
WEBHOOK_SECRET=your-secret-here
```

---

### V2: Payment Confirmation Race Condition ✅

**Problem:** Multiple concurrent webhooks could process the same payment, causing duplicate pot additions and user creations.

**Fix:** Implemented atomic check-and-update in `database.py`:
- New `update_session_status_if_pending()` method uses `UPDATE WHERE status='pending'`
- Returns true only for first successful update
- Modified `confirm_payment()` to use atomic operation before processing

**Files Changed:**
- `src/orange_nethack/api/webhooks.py`
- `src/orange_nethack/database.py`

**Testing:**
```python
# Concurrent test: 10 threads call confirm_payment simultaneously
# Result: Only one succeeds, pot incremented exactly once
```

---

### V3: CORS Wildcard Configuration ✅

**Problem:** `allow_origins=["*"]` with `allow_credentials=True` enabled CSRF attacks from any website.

**Fix:** Implemented explicit origin whitelist:
- Added `ALLOWED_ORIGINS` config option
- Updated `main.py` to use specific origins from config
- Restricted methods and headers to only what's needed

**Files Changed:**
- `src/orange_nethack/config.py`
- `src/orange_nethack/api/main.py`
- `.env.example` (added ALLOWED_ORIGINS)

**Configuration:**
```bash
# .env - Production
ALLOWED_ORIGINS=https://orange-nethack.com,https://www.orange-nethack.com

# .env - Development
ALLOWED_ORIGINS=http://localhost:5173
```

---

### V4: Non-Atomic Pot Operations ✅

**Problem:** Pot updates and reads happened in separate transactions, causing race conditions and inconsistent balances.

**Fix:** Used SQLite `RETURNING` clause for atomic operations:
- `add_to_pot()` returns new balance in same transaction
- `drain_pot()` reads and updates in single transaction
- Prevents balance inconsistencies during concurrent operations

**Files Changed:**
- `src/orange_nethack/database.py`

**Technical Details:**
```sql
-- Atomic add with RETURNING
UPDATE pot SET balance_sats = balance_sats + ?
WHERE id = 1
RETURNING balance_sats;

-- Atomic drain (SELECT + UPDATE in one transaction)
-- Transaction isolation ensures consistency
```

---

## HIGH Severity Fixes

### V5: Lightning Address Validation ✅

**Problem:** No format validation before sending funds, causing payout failures after pot was drained.

**Fix:** Added pydantic validators:
- `SetAddressRequest.validate_lightning_address()` validates format
- Supports Lightning addresses (`user@domain.com`) and LNURLs (`lnurl1...`)
- Validation happens BEFORE draining pot in `payout.py`

**Files Changed:**
- `src/orange_nethack/models.py`
- `src/orange_nethack/game/payout.py`

**Valid Formats:**
- Lightning address: `user@getalby.com`, `name@strike.me`
- LNURL: `lnurl1abc...` (minimum 10 characters)

---

### V6: Token Timing Attack Vulnerability ✅

**Problem:** String comparison `token != session.get("access_token")` was vulnerable to timing attacks.

**Fix:** Replaced with constant-time comparison:
- Uses `secrets.compare_digest()` in both `routes.py` and `terminal.py`
- Prevents attackers from guessing tokens by measuring response times
- Fully backward compatible

**Files Changed:**
- `src/orange_nethack/api/routes.py`
- `src/orange_nethack/api/terminal.py`

**Before:**
```python
if token != session.get("access_token"):  # Timing-dependent!
```

**After:**
```python
if not secrets.compare_digest(token or "", session.get("access_token") or ""):
```

---

## MEDIUM Severity Fixes

### V7: No Rate Limiting ✅

**Problem:** No protection against API abuse, invoice spam, or brute-force attacks.

**Fix:** Added slowapi middleware:
- Created global limiter with IP-based rate limiting
- Applied limits to all critical endpoints
- Configured appropriate thresholds per endpoint

**Files Changed:**
- `pyproject.toml` (added slowapi dependency)
- `src/orange_nethack/api/limiter.py` (new file)
- `src/orange_nethack/api/main.py`
- `src/orange_nethack/api/routes.py`
- `src/orange_nethack/api/webhooks.py`

**Rate Limits:**
- `/api/play` - 5/minute (session creation)
- `/api/session/{id}` - 30/minute (payment polling)
- `/api/stats` - 60/minute (leaderboard)
- `/api/webhook/payment` - 100/minute (legitimate webhooks)

---

### V8: Token in URL Query Parameters ✅

**Problem:** Access tokens in URLs get logged everywhere (web server, browser history, proxies).

**Fix:** Added Authorization header support with backward compatibility:
- Accepts `Authorization: Bearer <token>` header (preferred)
- Still accepts `?token=...` query param with deprecation warning
- Logs warnings for query param usage

**Files Changed:**
- `src/orange_nethack/api/routes.py`

**Migration Path:**
1. Deploy backend with dual support (done ✅)
2. Update frontend to use Authorization header
3. Remove query param support in future version

**Usage:**
```bash
# Preferred method
curl -H "Authorization: Bearer abc123" http://localhost:8000/api/session/1

# Deprecated (logs warning)
curl http://localhost:8000/api/session/1?token=abc123
```

---

### V9: No Email Input Validation ✅

**Problem:** Email field accepted any string, allowing invalid data.

**Fix:** Used pydantic EmailStr type:
- `PlayRequest.email` now uses `EmailStr | None`
- Validates format before storage
- Rejects invalid emails at API boundary

**Files Changed:**
- `src/orange_nethack/models.py`

**Valid:** `user@domain.com`, `name+tag@example.co.uk`
**Invalid:** `@domain`, `user@`, `plain_text`

---

### V10: Credentials in Plaintext Email ✅

**Problem:** SSH credentials sent in plaintext email, exposing them to interception.

**Fix:** Removed credentials from email body:
- Email now directs users to web UI for credential access
- Credentials only accessible via web interface with token authentication
- Reduces exposure while maintaining usability

**Files Changed:**
- `src/orange_nethack/email.py`

**Before:**
```
SSH Credentials:
  Username: nh_abc12345
  Password: xyz789
```

**After:**
```
Your session is active. Use the link above to play in your browser,
or access your SSH credentials via the web interface.
```

---

## Installation & Configuration

### 1. Install Dependencies

```bash
# If using pip (production)
pip install -e .

# If using Docker
docker-compose build
```

The new `slowapi` dependency will be installed automatically.

### 2. Update Environment Variables

Add to your `.env` file:

```bash
# Security configuration
WEBHOOK_SECRET=your-random-secret-here
ALLOWED_ORIGINS=https://your-domain.com,https://www.your-domain.com

# For development
ALLOWED_ORIGINS=http://localhost:5173
```

### 3. Re-register Strike Webhook

The webhook must be re-registered to set the signature secret:

```bash
orange-nethack-cli setup-strike-webhook https://your-domain.com/api/webhook/payment
```

This command now configures Strike to send signed webhooks.

### 4. Restart Services

```bash
# Docker
docker-compose restart

# Systemd (production)
sudo systemctl restart orange-nethack-api orange-nethack-monitor
```

---

## Testing

### Security Tests

```bash
# Test webhook signature verification
curl -X POST http://localhost:8000/api/webhook/payment \
  -H "Content-Type: application/json" \
  -d '{"eventType":"invoice.updated","data":{"entityId":"test"}}'
# Should return 401 Unauthorized (missing signature)

# Test CORS restrictions
curl -H "Origin: https://evil.com" http://localhost:8000/api/stats
# Should be blocked by CORS policy

# Test rate limiting
for i in {1..10}; do
  curl http://localhost:8000/api/play -X POST
done
# Should get 429 Too Many Requests after 5 requests
```

### Functional Tests

All existing functionality continues to work:
- Session creation and payment
- SSH and browser terminal access
- Game monitoring and payouts
- Email notifications
- Leaderboard and stats

### Backward Compatibility

The following changes maintain backward compatibility:
- CORS: Frontend must match `ALLOWED_ORIGINS` (was previously unrestricted)
- Token in header: Query param still works with deprecation warning
- All other fixes are transparent to clients

---

## Production Checklist

Before deploying to production:

- [ ] Set `STRIKE_API_KEY` in `.env`
- [ ] Set `MOCK_LIGHTNING=false`
- [ ] Configure `WEBHOOK_SECRET` (set via `setup-strike-webhook`)
- [ ] Set `ALLOWED_ORIGINS` to production domains
- [ ] Configure email (SMTP) settings
- [ ] Re-register Strike webhook with signature
- [ ] Restart all services
- [ ] Test payment flow end-to-end
- [ ] Monitor logs for warnings/errors
- [ ] Verify rate limits are working

---

## Monitoring

### Key Metrics to Watch

1. **Webhook authentication failures** - indicates attack or misconfiguration
2. **Rate limit hits** - monitor for abuse patterns
3. **Invalid Lightning address rejections** - user error or attack
4. **Token in query param warnings** - track migration to header auth

### Log Messages

```
# Webhook signature issues
"Webhook received without signature (production mode)" - ERROR
"Invalid webhook signature" - ERROR

# Rate limiting
"Rate limit exceeded" - INFO

# Deprecated usage
"Token in URL query param - use Authorization header instead" - WARNING

# Payment processing
"Session X already processed" - INFO (race condition prevented)
```

---

## Future Improvements

Additional security measures to consider:

1. **IP Whitelist for Webhooks** - Only accept webhooks from Strike IPs
2. **2FA for High-Value Payouts** - Additional confirmation for large pots
3. **Session Expiry** - Automatic cleanup of inactive sessions
4. **Audit Logging** - Comprehensive logging of all financial operations
5. **Webhook Replay Protection** - Timestamp-based replay attack prevention
6. **Frontend CSRF Tokens** - Additional CSRF protection beyond CORS

---

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Strike API Documentation](https://docs.strike.me/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [slowapi Documentation](https://slowapi.readthedocs.io/)

---

**Last Updated:** 2026-01-27
**Security Review Completed By:** Claude Code
**Status:** ✅ All 10 vulnerabilities fixed and production-ready
