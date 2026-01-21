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

## Important Files

| File | Purpose |
|------|---------|
| `src/orange_nethack/api/routes.py` | API endpoints, session creation |
| `src/orange_nethack/api/webhooks.py` | `confirm_payment()` - creates user on payment |
| `src/orange_nethack/game/monitor.py` | Watches xlogfile, handles game end |
| `src/orange_nethack/game/payout.py` | Sends pot to winner via Strike |
| `src/orange_nethack/lightning/strike.py` | Strike API client (invoices, LNURL payments) |
| `src/orange_nethack/database.py` | SQLite DB, session/game/pot operations |
| `src/orange_nethack/users/manager.py` | Linux user creation/deletion |
| `src/orange_nethack/cli.py` | Admin CLI commands |
| `scripts/orange-shell.sh` | Custom SSH shell, prompts for character name |
| `web/` | React frontend (Vite + TypeScript) |

## Database Schema

- `pot` - Single row, tracks pot balance
- `sessions` - Player sessions (username, password, linux_uid, lightning_address, email, status)
- `games` - Game results (character_name, death_reason, score, turns, ascended, payout)

## Common Issues & Fixes

### Strike API field name
The LNURL payment endpoint uses `lnAddressOrUrl` (not `lnUrlOrAddress`).

### Pot restoration on failed payout
Use `set_pot_balance()` not `add_to_pot()` to restore exact amount.

### Stats with no games
Database returns `None` for aggregates when no rows exist. Use `or 0` pattern.

### Docker API key
Never commit API keys to docker-compose.yml. Use `.env` file instead.

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

## Strike Webhook Setup

One-time setup for payment notifications:
```bash
orange-nethack-cli setup-strike-webhook https://your-domain.com/api/webhook/strike
```

The webhook receives `invoice.updated` events when payments are received.

## Deployment Checklist

1. Set `STRIKE_API_KEY` and `MOCK_LIGHTNING=false` in `.env`
2. Run `docker-compose up -d`
3. Set up Strike webhook (one-time)
4. Configure reverse proxy (nginx/Caddy) with HTTPS
5. Open ports 22 (SSH) and 443 (HTTPS)
