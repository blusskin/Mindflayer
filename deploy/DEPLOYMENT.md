# Orange Nethack - Production Deployment Guide

This guide covers deploying Orange Nethack to a bare metal Debian 12 server (e.g., Linode).

## Prerequisites

- Debian 12 server with root access
- Domain name pointed to your server's IP
- Strike API key (from https://strike.me)
- Mailtrap account for transactional emails (from https://mailtrap.io)

## Quick Start

1. **SSH into your server as root**

2. **Clone the repository:**
   ```bash
   cd /opt
   git clone https://github.com/yourusername/orange-nethack.git
   cd orange-nethack
   ```

3. **Run the install script:**
   ```bash
   chmod +x deploy/install.sh
   sudo ./deploy/install.sh
   ```

4. **Configure the application:**
   ```bash
   sudo nano /opt/orange-nethack/.env
   ```
   Fill in your production values (see Configuration section below).

5. **Configure nginx with your domain:**
   ```bash
   sudo nano /etc/nginx/sites-available/orange-nethack
   # Replace server_name _; with server_name yourdomain.com;
   sudo nginx -t && sudo systemctl reload nginx
   ```

6. **Set up SSL:**
   ```bash
   sudo certbot --nginx -d yourdomain.com
   ```

7. **Start the services:**
   ```bash
   sudo systemctl enable --now orange-nethack-api
   sudo systemctl enable --now orange-nethack-monitor
   ```

8. **Set up Strike webhook:**
   ```bash
   sudo -u orange-nethack /opt/orange-nethack/.venv/bin/orange-nethack-cli \
       setup-strike-webhook https://yourdomain.com/api/webhook/strike
   ```

9. **Configure firewall:**
   ```bash
   sudo ufw allow 22/tcp    # SSH (for game connections)
   sudo ufw allow 80/tcp    # HTTP (redirects to HTTPS)
   sudo ufw allow 443/tcp   # HTTPS
   sudo ufw enable
   ```

## Configuration

### .env File

Edit `/opt/orange-nethack/.env` with your production values:

```env
# Lightning/Strike API
MOCK_LIGHTNING=false
STRIKE_API_KEY=your_actual_strike_api_key

# Email (Mailtrap transactional)
SMTP_HOST=live.smtp.mailtrap.io
SMTP_PORT=587
SMTP_USER=api
SMTP_PASSWORD=your_mailtrap_api_token
SMTP_FROM_EMAIL=noreply@yourdomain.com
SMTP_USE_TLS=true

# Game settings
ANTE_SATS=1000
POT_INITIAL=0

# Server settings (don't change these)
HOST=127.0.0.1
PORT=8000
DATABASE_PATH=/var/lib/orange-nethack/db.sqlite
XLOGFILE_PATH=/var/games/nethack/xlogfile
```

### Getting API Keys

**Strike API Key:**
1. Go to https://dashboard.strike.me
2. Navigate to API Keys
3. Create a new API key with invoice permissions

**Mailtrap API Token:**
1. Go to https://mailtrap.io
2. Navigate to Email Sending → Sending Domains
3. Add and verify your domain
4. Go to Integration → SMTP
5. Copy the API token

## Service Management

```bash
# Check status
sudo systemctl status orange-nethack-api
sudo systemctl status orange-nethack-monitor

# View logs
sudo journalctl -u orange-nethack-api -f
sudo journalctl -u orange-nethack-monitor -f

# Restart services
sudo systemctl restart orange-nethack-api
sudo systemctl restart orange-nethack-monitor

# Stop services
sudo systemctl stop orange-nethack-api
sudo systemctl stop orange-nethack-monitor
```

## CLI Commands

Run CLI commands as the orange-nethack user:

```bash
# Show active sessions
sudo -u orange-nethack /opt/orange-nethack/.venv/bin/orange-nethack-cli show-sessions

# Show pot balance
sudo -u orange-nethack /opt/orange-nethack/.venv/bin/orange-nethack-cli show-pot

# Show game statistics
sudo -u orange-nethack /opt/orange-nethack/.venv/bin/orange-nethack-cli stats

# Show recent games
sudo -u orange-nethack /opt/orange-nethack/.venv/bin/orange-nethack-cli show-games
```

## Directory Structure

```
/opt/orange-nethack/          # Application code
├── .env                      # Configuration (sensitive!)
├── .venv/                    # Python virtual environment
├── src/                      # Source code
├── web/                      # Frontend (built)
└── scripts/                  # Shell scripts

/var/lib/orange-nethack/      # Application data
└── db.sqlite                 # Database

/var/games/nethack/           # Game files
├── xlogfile                  # Game results log
├── users/                    # Per-user game directories
│   └── nh_*/                 # Individual user dirs
├── save/                     # (legacy, not used)
└── recordings/               # TTY recordings
```

## Updating

To update to a new version:

```bash
cd /opt/orange-nethack

# Stop services
sudo systemctl stop orange-nethack-api orange-nethack-monitor

# Pull latest code
sudo -u orange-nethack git pull

# Rebuild frontend if needed
cd web && npm install && npm run build && cd ..

# Update Python dependencies
sudo -u orange-nethack .venv/bin/pip install -e .

# Restart services
sudo systemctl start orange-nethack-api orange-nethack-monitor
```

## Troubleshooting

### SSH connections failing

Check that:
- Port 22 is open in firewall
- SSH is configured for password authentication
- The game user exists: `id nh_username`

### "Permission denied" errors

The orange-nethack user needs sudo access for user management. Check:
```bash
sudo cat /etc/sudoers.d/orange-nethack
```

### Game not starting

Check the shell script:
```bash
cat /usr/local/bin/orange-shell.sh
# Verify it's in /etc/shells
grep orange-shell /etc/shells
```

### WebSocket connection failing

Ensure nginx is configured for WebSocket upgrades and the proxy timeout is set high enough.

### Strike webhook not working

1. Verify webhook is set up:
   ```bash
   sudo -u orange-nethack /opt/orange-nethack/.venv/bin/orange-nethack-cli setup-strike-webhook https://yourdomain.com/api/webhook/strike
   ```

2. Check that your domain has valid SSL (Strike requires HTTPS)

3. Check API logs for webhook requests:
   ```bash
   sudo journalctl -u orange-nethack-api | grep webhook
   ```

## Security Notes

- The `.env` file contains sensitive API keys - ensure it's only readable by the app user
- Game users (nh_*) have restricted shells and can only play Nethack
- The orange-nethack user has limited sudo access only for user management commands
- All web traffic should go through HTTPS (enforced by nginx after certbot setup)

## Backup

Important files to backup:
- `/opt/orange-nethack/.env` - Configuration
- `/var/lib/orange-nethack/db.sqlite` - Database (sessions, games, pot)
- `/var/games/nethack/xlogfile` - Game history

```bash
# Example backup script
tar -czf backup-$(date +%Y%m%d).tar.gz \
    /opt/orange-nethack/.env \
    /var/lib/orange-nethack/db.sqlite \
    /var/games/nethack/xlogfile
```
