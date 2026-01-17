# Orange Nethack

Bitcoin-themed Nethack server where players pay a Lightning ante to play, with the pot paid out on ascension.

## How It Works

1. Player requests a game session via the API
2. Server returns a Lightning invoice for the ante (default: 1000 sats)
3. Upon payment, SSH credentials are created
4. Player SSHs in and plays Nethack
5. If the player ascends, they win the entire pot!
6. If they die, their ante stays in the pot

## Quick Start

### Prerequisites

- Linux server with:
  - Python 3.11+
  - Nethack installed (`apt install nethack-console`)
  - OpenSSH server
- LNbits wallet (or compatible Lightning backend)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/orange-nethack.git
cd orange-nethack

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .

# Copy and configure environment
cp .env.example .env
# Edit .env with your LNbits credentials

# Initialize database
python -c "import asyncio; from orange_nethack.database import init_db; asyncio.run(init_db())"
```

### Server Setup

```bash
# Create service user
sudo useradd -r -s /bin/false orange-nethack

# Create data directory
sudo mkdir -p /var/lib/orange-nethack
sudo chown orange-nethack:orange-nethack /var/lib/orange-nethack

# Install shell script
sudo cp scripts/orange-shell.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/orange-shell.sh

# Add shell to allowed shells
echo "/usr/local/bin/orange-shell.sh" | sudo tee -a /etc/shells

# Install systemd services
sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable orange-nethack-api orange-nethack-monitor
sudo systemctl start orange-nethack-api orange-nethack-monitor
```

### Nethack Configuration

Ensure Nethack is configured to write to xlogfile:

```bash
# Edit /etc/nethack/nethack.conf or equivalent
# Make sure xlogfile is enabled and writable
sudo chmod 664 /var/games/nethack/xlogfile
sudo chown games:games /var/games/nethack/xlogfile
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Landing page with instructions |
| POST | `/api/play` | Start session, get invoice |
| POST | `/api/play/{id}/address` | Submit Lightning address for payout |
| GET | `/api/session/{id}` | Get session status/credentials |
| POST | `/api/webhook/payment` | LNbits payment webhook |
| GET | `/api/pot` | Current pot balance |
| GET | `/api/stats` | Leaderboard and stats |
| GET | `/api/health` | Health check |

## Usage Example

```bash
# 1. Create session and get invoice
curl -X POST https://your-server.com/api/play \
  -H "Content-Type: application/json" \
  -d '{"lightning_address": "you@getalby.com"}'

# Response:
# {
#   "session_id": 1,
#   "payment_request": "lnbc10u1p...",
#   "payment_hash": "abc123...",
#   "amount_sats": 1000
# }

# 2. Pay the invoice with your Lightning wallet

# 3. Get your credentials
curl https://your-server.com/api/session/1

# Response (after payment):
# {
#   "id": 1,
#   "status": "active",
#   "username": "nh_abc12345",
#   "password": "randompassword123",
#   "ssh_command": "ssh nh_abc12345@your-server.com"
# }

# 4. SSH in and play!
ssh nh_abc12345@your-server.com
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run API server locally
python -m orange_nethack.api.main

# Run monitor locally
python -m orange_nethack.game.monitor
```

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Web Server    │────▶│    LNbits       │────▶│  Lightning      │
│   (FastAPI)     │◀────│    API          │◀────│  Network        │
└────────┬────────┘     └─────────────────┘     └─────────────────┘
         │
         │ payment confirmed
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
                        │  (LNbits send)  │
                        └─────────────────┘
```

## Configuration

See `.env.example` for all configuration options.

## Security Notes

- The game monitor service runs as root to manage user accounts
- Player accounts are isolated with the custom shell
- SSH access is restricted to the Nethack game only
- Consider running behind a reverse proxy (nginx) with HTTPS

## License

MIT
