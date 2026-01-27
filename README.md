# Orange Nethack

Bitcoin-themed Nethack server where players pay a Lightning ante to play, with the pot paid out on ascension.

## How It Works

1. Player visits the web UI and submits their Lightning address + email
2. Server returns a Lightning invoice for the ante (default: 1000 sats)
3. Upon payment, SSH credentials are created and emailed to the player
4. Player SSHs in, enters their character name, and plays Nethack
5. If the player ascends, they win the entire pot!
6. If they die, their ante is added to the pot for the next player

The pot starts at 0 and is purely player-funded.

## Features

- **Lightning payments** via Strike API
- **Browser terminal** - play directly in the web UI via WebSocket
- **SSH access** - traditional SSH connection for terminal purists
- **Enhanced leaderboard** with character class, race, death level, and achievement badges
- **Conduct tracking** - displays badges for pacifist, vegan, wishless, and other conducts
- **Email notifications** - payment confirmation and game results
- **Anti-cheat** - explore/wizard mode games are detected and don't count

## Quick Start (Docker)

The easiest way to run Orange Nethack is with Docker:

```bash
# Clone the repository
git clone https://github.com/yourusername/orange-nethack.git
cd orange-nethack

# Create .env file with your Strike API key
cat > .env << EOF
STRIKE_API_KEY=your_strike_api_key_here
MOCK_LIGHTNING=false
EOF

# Start the server
docker-compose up -d

# View logs
docker-compose logs -f
```

The server will be available at `http://localhost:8000` with:
- Web UI at `/`
- API at `/api/`
- SSH on port 22

### Strike API Setup

1. Create a Strike account at https://strike.me
2. Get your API key from the Strike dashboard
3. Set up a webhook subscription (one-time):

```bash
docker exec -it orange-nethack orange-nethack-cli setup-strike-webhook https://your-domain.com/api/webhook/payment
```

**Note:** The webhook URL must be `/api/webhook/payment` (not `/api/webhook/strike`).

## CLI Commands

The `orange-nethack-cli` tool provides admin commands:

```bash
# Show server statistics
orange-nethack-cli stats

# Show current pot balance (alias: pot)
orange-nethack-cli pot

# Set pot to specific amount
orange-nethack-cli set-pot 50000

# Reset pot to initial (0)
orange-nethack-cli reset-pot

# List active sessions (alias: sessions)
orange-nethack-cli sessions

# List all sessions (including ended)
orange-nethack-cli list-all-sessions

# Show recent games (alias: games)
orange-nethack-cli games

# Delete a game from leaderboard
orange-nethack-cli delete-game <game_id>

# Clear all games from leaderboard
orange-nethack-cli clear-games --confirm

# End a session manually
orange-nethack-cli end-session <session_id>

# Delete a Linux user
orange-nethack-cli delete-user <username>

# Simulate a game (for testing)
orange-nethack-cli simulate-game <username>
orange-nethack-cli simulate-game --ascend <username>

# Simulate with character details
orange-nethack-cli simulate-game <username> --role Wiz --race Elf --conduct 0x222 --achieve 0xC00

# Simulate payment confirmation (mock mode)
orange-nethack-cli simulate-payment <session_id>

# Run full integration test
orange-nethack-cli test-flow

# Set up Strike webhook
orange-nethack-cli setup-strike-webhook https://yourdomain.com/api/webhook/payment
```

In Docker:
```bash
docker exec -it orange-nethack orange-nethack-cli stats
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Web UI (React SPA) |
| POST | `/api/play` | Start session, get invoice |
| GET | `/api/session/{id}` | Get session status/credentials |
| POST | `/api/webhook/payment` | Strike payment webhook |
| GET | `/api/pot` | Current pot balance |
| GET | `/api/stats` | Leaderboard and stats |
| GET | `/api/health` | Health check |
| WS | `/api/ws/terminal/{id}` | Browser terminal WebSocket |

## Configuration

Environment variables (set in `.env` or docker-compose):

| Variable | Default | Description |
|----------|---------|-------------|
| `STRIKE_API_KEY` | (required) | Strike API key for payments |
| `MOCK_LIGHTNING` | `true` | Use fake payments for testing |
| `WEBHOOK_SECRET` | (optional) | Secret for verifying Strike webhook signatures |
| `ALLOWED_ORIGINS` | `http://localhost:5173` | Comma-separated CORS allowed origins |
| `ANTE_SATS` | `1000` | Cost to play in satoshis |
| `POT_INITIAL` | `0` | Starting pot balance |
| `DATABASE_PATH` | `/var/lib/orange-nethack/db.sqlite` | SQLite database path |
| `XLOGFILE_PATH` | `/var/games/nethack/xlogfile` | Nethack xlogfile path |
| `SMTP_HOST` | (optional) | SMTP server for email notifications |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_USER` | (optional) | SMTP username |
| `SMTP_PASSWORD` | (optional) | SMTP password |
| `SMTP_FROM_EMAIL` | (optional) | From address for emails |

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Web Server    │────▶│    Strike       │────▶│  Lightning      │
│   (FastAPI)     │◀────│    API          │◀────│  Network        │
└────────┬────────┘     └─────────────────┘     └─────────────────┘
         │
         │ payment confirmed (webhook or polling)
         ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  User Manager   │────▶│   SSH Server    │────▶│    Nethack      │
│  (create user)  │     │   (OpenSSH)     │     │    Game         │
└─────────────────┘     └────────┬────────┘     └────────┬────────┘
                                 │                       │
                                 │                       │ game ends
                                 ▼                       ▼
                        ┌─────────────────┐     ┌─────────────────┐
                        │  Game Monitor   │◀────│   xlogfile      │
                        │  (watchdog)     │     │   Parser        │
                        └────────┬────────┘     └─────────────────┘
                                 │
                                 │ ascension detected
                                 ▼
                        ┌─────────────────┐
                        │  Payout Service │
                        │  (Strike LNURL) │
                        └─────────────────┘
```

### Session Tracking

Sessions are tracked by Linux UID (not character name):
- When a player pays, a Linux user is created (e.g., `nh_abc12345`)
- The user's UID is stored in the database
- When a game ends, the xlogfile entry's UID matches to the session
- Character names are chosen by players on first SSH login

## Development

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run API server locally (mock mode)
MOCK_LIGHTNING=true python -m orange_nethack.api.main

# Run monitor locally
python -m orange_nethack.game.monitor
```

## Manual Installation (without Docker)

For running directly on a Linux server, see `deploy/DEPLOYMENT.md` for the full guide.

Quick overview:

```bash
# Prerequisites
apt install nethack-console openssh-server python3.11 python3.11-venv nginx

# Clone to /opt
cd /opt
git clone https://github.com/yourusername/orange-nethack.git
cd orange-nethack

# Run the install script
sudo ./deploy/install.sh

# Configure
sudo nano /opt/orange-nethack/.env
# Fill in your Strike API key and email settings

# Start services
sudo systemctl enable --now orange-nethack-api orange-nethack-monitor

# Set up Strike webhook
orange-nethack-cli setup-strike-webhook https://yourdomain.com/api/webhook/payment
```

### Directory Permissions

Critical permissions for the game to work:

```bash
# Players need to traverse to their game directory
sudo chown root:games /var/games/nethack
sudo chmod 755 /var/games/nethack

# Players write game results here
sudo chown root:games /var/games/nethack/xlogfile
sudo chmod 664 /var/games/nethack/xlogfile

# API creates per-user directories here
sudo chown root:orange-nethack /var/games/nethack/users
sudo chmod 775 /var/games/nethack/users
```

## Troubleshooting

### Viewing Logs

```bash
# API server logs
sudo journalctl -u orange-nethack-api -f

# Game monitor logs
sudo journalctl -u orange-nethack-monitor -f

# Combined logs
sudo journalctl -u 'orange-nethack-*' -f
```

### Common Issues

**"Permission denied" on game start:**
Check directory permissions (see Directory Permissions section above).

**Strike webhook not working:**
1. Verify the webhook URL ends with `/api/webhook/payment`
2. Ensure your domain has valid SSL (Strike requires HTTPS)
3. Check API logs: `sudo journalctl -u orange-nethack-api | grep webhook`

**"Cannot open file xlogfile":**
The xlogfile needs to be writable by the games group:
```bash
sudo chown root:games /var/games/nethack/xlogfile
sudo chmod 664 /var/games/nethack/xlogfile
```

**Players getting "Too many hacks running":**
Stale lock files in the user's game directory. Clean up or delete the user:
```bash
orange-nethack-cli delete-user <username>
```

## Security Notes

- Create a non-root admin user for server management (see `deploy/DEPLOYMENT.md`)
- The game monitor service requires root to manage user accounts
- Player accounts are isolated with a custom shell (can only run Nethack)
- SSH access is restricted to the Nethack game only
- Consider running behind a reverse proxy (nginx/Caddy) with HTTPS
- Never commit `.env` files or API keys to git

## License

MIT
