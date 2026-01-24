#!/bin/bash
#
# Orange Nethack SSH Shell
# This script is the login shell for Orange Nethack players.
# It shows a welcome message and launches nethack directly.
#

# Configuration
NETHACK_BINARY="${NETHACK_BINARY:-/usr/games/nethack}"
NETHACK_NAME_FILE="$HOME/.nethack_name"
XLOGFILE="${XLOGFILE_PATH:-/var/games/nethack/xlogfile}"

# Per-user Nethack directory (avoids lock file conflicts and MAXPLAYERS limit)
USER_NETHACK_DIR="/var/games/nethack/users/$USER"
export NETHACKDIR="$USER_NETHACK_DIR"

# Point Nethack to the user's config file in their game directory
export NETHACKOPTIONS="$USER_NETHACK_DIR/.nethackrc"

# Get current user's UID
CURRENT_UID=$(id -u)

# Lock file for concurrent session prevention
LOCK_FILE="$HOME/.nethack_lock"

# Session start time file - used to detect if game ended during THIS session
SESSION_START_FILE="$HOME/.session_start"

check_concurrent_session() {
    if [ -f "$LOCK_FILE" ]; then
        LOCK_PID=$(cat "$LOCK_FILE" 2>/dev/null)
        if [ -n "$LOCK_PID" ] && kill -0 "$LOCK_PID" 2>/dev/null; then
            return 0  # Another session is running
        fi
        rm -f "$LOCK_FILE"  # Stale lock
    fi
    return 1
}

create_lock() {
    echo $$ > "$LOCK_FILE"
}

cleanup_lock() {
    # Only delete the lock if we own it (contains our PID)
    if [ -f "$LOCK_FILE" ]; then
        LOCK_PID=$(cat "$LOCK_FILE" 2>/dev/null)
        if [ "$LOCK_PID" = "$$" ]; then
            rm -f "$LOCK_FILE"
        fi
    fi
}
trap cleanup_lock EXIT

# Check if this user has a game entry in xlogfile from THIS session
# This prevents the race condition where a player reconnects before
# the game monitor processes their death.
# We compare against session start time to avoid false positives from UID recycling.
check_game_already_ended() {
    if [ ! -f "$XLOGFILE" ]; then
        return 1  # No xlogfile, OK to play
    fi

    # Get session start time (written when session first started)
    if [ ! -f "$SESSION_START_FILE" ]; then
        return 1  # No session start file, this is a fresh session
    fi
    SESSION_START=$(cat "$SESSION_START_FILE" 2>/dev/null)
    if [ -z "$SESSION_START" ]; then
        return 1  # Empty file, OK to play
    fi

    # Find entries for this UID where endtime is AFTER session start
    # This means the game ended during THIS session (not a previous one)
    GAME_ENDED=$(grep "uid=$CURRENT_UID[^0-9]" "$XLOGFILE" 2>/dev/null | \
        awk -F'[\t:]' -v session_start="$SESSION_START" '
        {
            for (i=1; i<=NF; i++) {
                if ($i ~ /^endtime=/) {
                    split($i, a, "=")
                    if (a[2] > session_start) {
                        print "found"
                        exit
                    }
                }
            }
        }')

    if [ "$GAME_ENDED" = "found" ]; then
        return 0  # Game ended during this session
    fi

    return 1  # No game end during this session, OK to play
}

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

# Record session start time if not already recorded
# This is used to distinguish xlogfile entries from THIS session vs previous sessions
if [ ! -f "$SESSION_START_FILE" ]; then
    date +%s > "$SESSION_START_FILE"
fi

# Check if game has already ended during THIS session (prevents race condition exploit)
if check_game_already_ended; then
    echo -e "${RED}Your game has already ended.${NC}"
    echo ""
    echo "Your session is being cleaned up. To play again,"
    echo "please pay a new ante at the website."
    echo ""
    echo -e "Visit: ${YELLOW}https://orangenethack.com${NC}"
    echo ""
    sleep 5
    exit 0
fi

# Check for concurrent session (only one game at a time)
if check_concurrent_session; then
    echo -e "${RED}A game session is already active.${NC}"
    echo ""
    echo "Only one game per session is allowed."
    echo "Close the other connection first."
    echo ""
    sleep 3
    exit 0
fi

create_lock

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
