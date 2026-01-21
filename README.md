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
docker exec -it orange-nethack orange-nethack-cli setup-strike-webhook https://your-domain.com/api/webhook/strike
```

## CLI Commands

The `orange-nethack-cli` tool provides admin commands:

```bash
# Show server statistics
orange-nethack-cli stats

# Show current pot balance
orange-nethack-cli show-pot

# Set pot to specific amount
orange-nethack-cli set-pot 50000

# Reset pot to initial (0)
orange-nethack-cli reset-pot

# List active sessions
orange-nethack-cli show-sessions

# List all sessions (including ended)
orange-nethack-cli list-all-sessions

# End a session manually
orange-nethack-cli end-session <session_id>

# Delete a Linux user
orange-nethack-cli delete-user <username>

# Simulate a game (for testing)
orange-nethack-cli simulate-game <username>
orange-nethack-cli simulate-game --ascend <username>

# Set up Strike webhook
orange-nethack-cli setup-strike-webhook <webhook_url>
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
| POST | `/api/webhook/strike` | Strike payment webhook |
| GET | `/api/pot` | Current pot balance |
| GET | `/api/stats` | Leaderboard and stats |
| GET | `/api/health` | Health check |

## Configuration

Environment variables (set in `.env` or docker-compose):

| Variable | Default | Description |
|----------|---------|-------------|
| `STRIKE_API_KEY` | (required) | Strike API key for payments |
| `MOCK_LIGHTNING` | `true` | Use fake payments for testing |
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

For running directly on a Linux server:

```bash
# Prerequisites
apt install nethack-console openssh-server python3.11 python3.11-venv

# Clone and install
git clone https://github.com/yourusername/orange-nethack.git
cd orange-nethack
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .

# Configure
cp .env.example .env
# Edit .env with your Strike API key

# Install shell script
sudo cp scripts/orange-shell.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/orange-shell.sh
echo "/usr/local/bin/orange-shell.sh" | sudo tee -a /etc/shells

# Nethack xlogfile permissions
sudo chmod 664 /var/games/nethack/xlogfile
sudo chown games:games /var/games/nethack/xlogfile

# Install systemd services
sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable orange-nethack-api orange-nethack-monitor
sudo systemctl start orange-nethack-api orange-nethack-monitor
```

## Security Notes

- The game monitor service requires root to manage user accounts
- Player accounts are isolated with a custom shell (can only run Nethack)
- SSH access is restricted to the Nethack game only
- Consider running behind a reverse proxy (nginx/Caddy) with HTTPS
- Never commit `.env` files or API keys to git

## License

MIT
