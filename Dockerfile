# Orange Nethack - Full Test Environment
#
# Build:  docker build -t orange-nethack .
# Run:    docker-compose up
#

# Stage 1: Build frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# Stage 2: Python app with Nethack
FROM debian:bookworm-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    nethack-console \
    openssh-server \
    sudo \
    procps \
    ttyrec \
    && rm -rf /var/lib/apt/lists/*

# Setup SSH
RUN mkdir /var/run/sshd
RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin no/' /etc/ssh/sshd_config
RUN sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config

# Create directories
RUN mkdir -p /opt/orange-nethack /var/lib/orange-nethack /var/games/nethack /var/games/nethack/recordings /var/games/nethack/users

# Setup nethack xlogfile
RUN touch /var/games/nethack/xlogfile && \
    chmod 664 /var/games/nethack/xlogfile && \
    chown games:games /var/games/nethack/xlogfile

# Setup recordings directory for ttyrec (spectator mode)
RUN chmod 777 /var/games/nethack/recordings

# Setup per-user Nethack directories parent (writable by root for user creation)
RUN chmod 755 /var/games/nethack/users

# Copy application
WORKDIR /opt/orange-nethack
COPY . .

# Copy built frontend from Stage 1
COPY --from=frontend-builder /app/web/dist ./web/dist

# Install the shell script
RUN cp scripts/orange-shell.sh /usr/local/bin/ && \
    chmod +x /usr/local/bin/orange-shell.sh && \
    echo "/usr/local/bin/orange-shell.sh" >> /etc/shells

# Create virtual environment and install
RUN python3.11 -m venv .venv && \
    .venv/bin/pip install --upgrade pip && \
    .venv/bin/pip install -e .

# Create .env with mock mode enabled
RUN echo "MOCK_LIGHTNING=true" > .env && \
    echo "DATABASE_PATH=/var/lib/orange-nethack/db.sqlite" >> .env && \
    echo "XLOGFILE_PATH=/var/games/nethack/xlogfile" >> .env

# Initialize database
RUN .venv/bin/python -c "import asyncio; from orange_nethack.database import init_db; asyncio.run(init_db())"

# Create startup script
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# Start SSH\n\
/usr/sbin/sshd\n\
\n\
# Start game monitor in background\n\
cd /opt/orange-nethack\n\
source .venv/bin/activate\n\
orange-nethack-monitor &\n\
\n\
# Start API server (foreground)\n\
exec orange-nethack-api\n\
' > /start.sh && chmod +x /start.sh

EXPOSE 8000 22

CMD ["/start.sh"]
