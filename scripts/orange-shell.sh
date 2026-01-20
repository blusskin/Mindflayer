#!/bin/bash
#
# Orange Nethack SSH Shell
# This script is the login shell for Orange Nethack players.
# It shows a welcome message and launches nethack directly.
# Optionally records gameplay with ttyrec for spectator mode.
#

# Configuration
NETHACK_BINARY="${NETHACK_BINARY:-/usr/games/nethack}"
NETHACK_NAME_FILE="$HOME/.nethack_name"
TTYREC_BINARY="${TTYREC_BINARY:-/usr/bin/ttyrec}"
RECORDINGS_DIR="${RECORDINGS_DIR:-/var/games/nethack/recordings}"

# Read character name if the file exists
CHARACTER_NAME=""
if [ -f "$NETHACK_NAME_FILE" ]; then
    CHARACTER_NAME=$(cat "$NETHACK_NAME_FILE" | tr -d '\n')
fi

# Determine recording filename (use username)
RECORDING_FILE="$RECORDINGS_DIR/$USER.ttyrec"

# Colors
ORANGE='\033[0;33m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Clear screen
clear

# Welcome banner
echo -e "${ORANGE}"
cat << 'EOF'
  ___                              _   _      _   _                _
 / _ \ _ __ __ _ _ __   __ _  ___ | \ | | ___| |_| |__   __ _  ___| | __
| | | | '__/ _` | '_ \ / _` |/ _ \|  \| |/ _ \ __| '_ \ / _` |/ __| |/ /
| |_| | | | (_| | | | | (_| |  __/| |\  |  __/ |_| | | | (_| | (__|   <
 \___/|_|  \__,_|_| |_|\__, |\___|_| \_|\___|\__|_| |_|\__,_|\___|_|\_\
                       |___/
EOF
echo -e "${NC}"

echo -e "${YELLOW}Welcome to Orange Nethack!${NC}"
echo ""
echo -e "Ascend to win the pot! ${GREEN}⚡${NC}"
echo ""
echo "Rules:"
echo "  - One game per ante"
echo "  - Ascend to win the entire pot"
echo "  - Die and lose your ante"
echo ""
echo -e "${ORANGE}Press ENTER to start your adventure...${NC}"
read -r

# Build the nethack command
if [ -n "$CHARACTER_NAME" ]; then
    NETHACK_CMD="$NETHACK_BINARY -u $CHARACTER_NAME"
else
    NETHACK_CMD="$NETHACK_BINARY"
fi

# Launch nethack (with ttyrec recording if available)
if [ -x "$NETHACK_BINARY" ]; then
    # Try to record with ttyrec for spectator mode
    if [ -x "$TTYREC_BINARY" ] && [ -d "$RECORDINGS_DIR" ]; then
        # ttyrec will record the session to file
        exec "$TTYREC_BINARY" -e "$NETHACK_CMD" "$RECORDING_FILE"
    else
        # Fallback: run nethack directly without recording
        exec $NETHACK_CMD
    fi
else
    echo -e "${RED}Error: Nethack not found at $NETHACK_BINARY${NC}"
    echo "Please contact the administrator."
    sleep 5
    exit 1
fi
