# Claude Project Notes - Orange Nethack

Notes for re-familiarizing with this project in future sessions.

## Project Overview

Orange Nethack is a Bitcoin-powered Nethack server. Players pay a Lightning ante (1000 sats) to get SSH credentials, play Nethack, and if they ascend, they win the entire pot.

## Key Architecture Decisions

### Session Tracking by Linux UID
- Sessions are tracked by Linux UID, NOT by character name
- When payment confirmed: Linux user created (e.g., `nh_abc12345`) -> UID stored in DB
- When game ends: xlogfile entry contains UID -> matched to session
- Character names are prompted on first SSH login and stored in `~/.nethack_name`

### Per-User Nethack Directories
Each player gets their own Nethack directory at `/var/games/nethack/users/<username>/`:
- Avoids lock file conflicts between players
- Bypasses Nethack's MAXPLAYERS limit (default 10)
- Contains: `save/`, `perm`, `record`, `logfile`
- Symlinks `xlogfile` to global `/var/games/nethack/xlogfile` (for game monitor)
- Symlinks data files (`nhdat`, `symbols`, `license`) from `/usr/lib/games/nethack/`
- Set via `NETHACKDIR` environment variable in shell script
- Created by `UserManager._create_nethack_directory()` on user creation
- Cleaned up by `UserManager._cleanup_nethack_directory()` on session end

### Session Race Condition Prevention
To prevent players from reconnecting after death (before cleanup):
- Shell script writes session start time to `~/.session_start`
- On reconnect, checks xlogfile for entries with `endtime > session_start`
- If found, blocks reconnection with "game already ended" message

### Payment Flow
1. Player submits Lightning address + email via web UI
2. Strike API creates invoice, returned to player
3. Payment detected via webhook OR polling (GET `/api/session/{id}`)
4. `confirm_payment()` creates Linux user, sends email with SSH creds
5. Player SSHs in, custom shell (`orange-shell.sh`) launches Nethack

### Game End Flow
1. `GameMonitor` watches xlogfile for new entries
2. Entry parsed, UID matched to active session
3. If ascended: `PayoutService` sends pot to player's Lightning address via Strike LNURL
4. Session ended, Linux user deleted

### Browser Terminal
Players can play via browser instead of SSH client:
- WebSocket endpoint at `/api/terminal/ws/{session_id}`
- `SSHBridge` class spawns `su -l <username>` process
- Uses asyncssh-style PTY for terminal emulation
- xterm.js on frontend renders terminal
- Disconnect sends SIGHUP for Nethack emergency save

## Important Files

| File | Purpose |
|------|---------|
| `src/orange_nethack/api/routes.py` | API endpoints, session creation |
| `src/orange_nethack/api/webhooks.py` | `confirm_payment()` - creates user on payment |
| `src/orange_nethack/api/terminal.py` | WebSocket SSH bridge for browser terminal |
| `src/orange_nethack/game/monitor.py` | Watches xlogfile, handles game end |
| `src/orange_nethack/game/payout.py` | Sends pot to winner via Strike |
| `src/orange_nethack/lightning/strike.py` | Strike API client (invoices, LNURL payments) |
| `src/orange_nethack/database.py` | SQLite DB, session/game/pot operations |
| `src/orange_nethack/users/manager.py` | Linux user creation/deletion, per-user directories |
| `src/orange_nethack/cli.py` | Admin CLI commands |
| `scripts/orange-shell.sh` | Custom SSH shell, session tracking, launches Nethack |
| `web/src/components/Terminal.tsx` | xterm.js terminal component for browser play |
| `web/src/components/ConductIcons.tsx` | Conduct badge icons with tooltips |
| `web/src/components/AchievementIcons.tsx` | Achievement badge icons with tooltips |
| `web/src/pages/TerminalPage.tsx` | Browser terminal page |
| `web/src/pages/StatsPage.tsx` | Leaderboard with enhanced game details |
| `deploy/install.sh` | Bare metal deployment script for Debian 12 |
| `deploy/DEPLOYMENT.md` | Production deployment guide |

## Database Schema

- `pot` - Single row, tracks pot balance
- `sessions` - Player sessions (username, password, linux_uid, lightning_address, email, status)
- `games` - Game results (character_name, death_reason, score, turns, ascended, payout, role, race, gender, align, deathlev, hp, maxhp, conduct, achieve)

## Production Directory Structure

```
/opt/orange-nethack/           # Application code
├── .env                       # Configuration (sensitive!)
├── .venv/                     # Python virtual environment
├── src/                       # Source code
├── web/dist/                  # Built frontend
└── scripts/                   # Shell scripts

/var/lib/orange-nethack/       # Application data
└── db.sqlite                  # Database

/var/games/nethack/            # Game files
├── xlogfile                   # Global game results log
└── users/                     # Per-user directories
    └── nh_*/                  # Individual user game dirs
        ├── save/              # Save files
        ├── nhdat -> ...       # Symlink to system data
        └── xlogfile -> ...    # Symlink to global xlogfile
```

## Common Issues & Fixes

### Strike API field name
The LNURL payment endpoint uses `lnAddressOrUrl` (not `lnUrlOrAddress`).

### Pot restoration on failed payout
Use `set_pot_balance()` not `add_to_pot()` to restore exact amount.

### Stats with no games
Database returns `None` for aggregates when no rows exist. Use `or 0` pattern.

### Docker API key
Never commit API keys to docker-compose.yml. Use `.env` file instead.

### Browser terminal not disconnecting
When navigating away from terminal page, explicitly call `disconnect()` before navigation.
The Terminal component exposes this via `forwardRef`/`useImperativeHandle`.

### "Too many hacks running" error
Caused by stale level files or lock conflicts. Per-user directories solve this.
If it happens, clean up `/var/games/nethack/users/<username>/` directory.

### Nethack "Cannot open dungeon description"
Per-user directory missing data file symlinks. Ensure `nhdat`, `symbols`, `license`
are symlinked from `/usr/lib/games/nethack/`.

### UID recycling false positives
Old xlogfile entries can match new sessions with same UID. Session start time
tracking in `~/.session_start` prevents this by comparing timestamps.

### Directory permission chain
Critical permissions for game to work:
- `/var/games/nethack` - 755 root:games (players need to traverse)
- `/var/games/nethack/xlogfile` - 664 root:games (players write game results)
- `/var/games/nethack/users` - 775 root:orange-nethack (API creates user dirs)
- `/var/lib/orange-nethack` - 770 root:orange-nethack (database)
- `/opt/orange-nethack/.env` - 640 root:orange-nethack (config with secrets)

### Strike webhook URL
Must be `/api/webhook/payment` (NOT `/api/webhook/strike`). Wrong URL causes 405 errors.

## Testing

### Mock Mode
Set `MOCK_LIGHTNING=true` - invoices auto-paid, payouts always succeed.

### CLI Testing
```bash
# In Docker
docker exec -it orange-nethack bash
source .venv/bin/activate

# Simulate payment for existing session
orange-nethack-cli simulate-payment <session_id>

# Simulate game end (death)
orange-nethack-cli simulate-game <username>

# Simulate ascension (triggers payout)
orange-nethack-cli simulate-game --ascend <username>
```

### Full Flow Test
```bash
orange-nethack-cli test-flow
```

## Web UI Development

The web UI is a React SPA in `web/`:
```bash
cd web
npm install
npm run dev      # Dev server on :5173
npm run build    # Build to web/dist (served by FastAPI)
```

Changes require `npm run build` then Docker rebuild.

## Configuration

Key env vars:
- `STRIKE_API_KEY` - Required for real payments
- `MOCK_LIGHTNING` - `true` for testing, `false` for production
- `ANTE_SATS` - Cost to play (default: 1000)
- `POT_INITIAL` - Starting pot (default: 0, purely player-funded)

Email (Mailtrap transactional):
- `SMTP_HOST` - `live.smtp.mailtrap.io` for production
- `SMTP_PORT` - `587`
- `SMTP_USER` - `api`
- `SMTP_PASSWORD` - Mailtrap API token
- `SMTP_FROM_EMAIL` - Must be verified domain in Mailtrap
- `SMTP_USE_TLS` - `true`

Security:
- `WEBHOOK_SECRET` - Secret for verifying Strike webhook signatures (set via `setup-strike-webhook`)
- `ALLOWED_ORIGINS` - Comma-separated list of allowed CORS origins (e.g., `https://example.com,https://www.example.com`)

## Security Features

The codebase includes several security hardening measures:

### Payment Security
- **Webhook Signature Verification** - All Strike webhooks are verified using HMAC-SHA256 signatures to prevent forged payment confirmations
- **Payment Race Condition Prevention** - Atomic database operations ensure each payment is processed exactly once, even with concurrent webhook deliveries
- **Atomic Pot Operations** - Database transactions with RETURNING clause prevent pot balance inconsistencies

### API Security
- **CORS Restrictions** - Explicit origin whitelist prevents CSRF attacks (configure via `ALLOWED_ORIGINS`)
- **Rate Limiting** - slowapi middleware protects against API abuse:
  - Session creation: 5/minute per IP
  - Payment polling: 30/minute per IP
  - Webhooks: 100/minute per IP
  - Stats queries: 60/minute per IP
- **Constant-Time Token Comparison** - Uses `secrets.compare_digest()` to prevent timing attacks
- **Authorization Header Support** - Tokens accepted via `Authorization: Bearer <token>` header (query param deprecated)

### Input Validation
- **Lightning Address Validation** - Pydantic validators ensure proper format before payouts
- **Email Validation** - EmailStr type validates email addresses
- **Credentials Not in Email** - SSH credentials not sent in plaintext email; users access via web UI

## Strike Webhook Setup

One-time setup for payment notifications:
```bash
orange-nethack-cli setup-strike-webhook https://your-domain.com/api/webhook/payment
```

The webhook receives `invoice.updated` events when payments are received.

## Deployment

### Bare Metal (Recommended for Production)
See `deploy/DEPLOYMENT.md` for full guide. Quick start:
```bash
cd /opt
git clone <repo> orange-nethack
cd orange-nethack
sudo ./deploy/install.sh
# Edit /opt/orange-nethack/.env with production values
sudo systemctl enable --now orange-nethack-api orange-nethack-monitor
```

The install script handles: system deps, user creation, Python venv, per-user
Nethack directories, SSH config, systemd services, nginx, and sudo permissions.

### Docker (Development/Testing)
```bash
docker-compose up -d
```

### Post-Deployment Checklist
1. Set `STRIKE_API_KEY` and `MOCK_LIGHTNING=false` in `.env`
2. Configure email (Mailtrap) settings in `.env`
3. Set up SSL with certbot
4. Set up Strike webhook: `orange-nethack-cli setup-strike-webhook https://domain.com/api/webhook/payment`
5. Open ports: 22 (SSH), 80 (HTTP), 443 (HTTPS)
