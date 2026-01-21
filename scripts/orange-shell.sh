#!/bin/bash
#
# Orange Nethack SSH Shell
# This script is the login shell for Orange Nethack players.
# It shows a welcome message and launches nethack directly.
#

# Configuration
NETHACK_BINARY="${NETHACK_BINARY:-/usr/games/nethack}"
NETHACK_NAME_FILE="$HOME/.nethack_name"

# Read character name if the file exists and has content
CHARACTER_NAME=""
if [ -f "$NETHACK_NAME_FILE" ]; then
    CHARACTER_NAME=$(cat "$NETHACK_NAME_FILE" | tr -d '\n\r' | xargs)
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

# If no character name saved, prompt for one
if [ -z "$CHARACTER_NAME" ]; then
    echo -e "${ORANGE}Enter your character name (used for saves):${NC}"
    read -r CHARACTER_NAME

    # Validate: alphanumeric and underscore only, max 31 chars
    CHARACTER_NAME=$(echo "$CHARACTER_NAME" | tr -cd 'a-zA-Z0-9_' | cut -c1-31)

    # Default to "Adventurer" if empty
    if [ -z "$CHARACTER_NAME" ]; then
        CHARACTER_NAME="Adventurer"
    fi

    # Save for future sessions
    echo "$CHARACTER_NAME" > "$NETHACK_NAME_FILE"
    echo -e "Character name saved: ${GREEN}$CHARACTER_NAME${NC}"
    echo ""
fi

echo -e "Playing as: ${GREEN}$CHARACTER_NAME${NC}"
echo ""
echo -e "${ORANGE}Press ENTER to start your adventure...${NC}"
read -r

# Build the nethack command with character name
NETHACK_CMD="$NETHACK_BINARY -u $CHARACTER_NAME"

# Launch nethack
if [ -x "$NETHACK_BINARY" ]; then
    # Run nethack directly
    # TODO: Add ttyrec recording for spectator mode once terminal issues are resolved
    exec $NETHACK_CMD
else
    echo -e "${RED}Error: Nethack not found at $NETHACK_BINARY${NC}"
    echo "Please contact the administrator."
    sleep 5
    exit 1
fi
