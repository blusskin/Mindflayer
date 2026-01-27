"""CLI tools for local testing of Orange Nethack.

Commands:
    simulate-payment: Manually trigger payment confirmation for a session
    simulate-game: Append a fake xlogfile entry and process it
    test-flow: Run a complete automated test
    show-sessions: List active sessions
    show-pot: Show current pot balance
    setup-strike-webhook: Register webhook subscription with Strike API
"""
import argparse
import asyncio
import logging
import secrets
import sys
import time
from datetime import datetime
from pathlib import Path

from orange_nethack.api.webhooks import confirm_payment
from orange_nethack.config import get_settings, _get_env_file
from orange_nethack.database import Database, get_db, init_db
from orange_nethack.game.monitor import GameMonitor
from orange_nethack.game.xlogfile import XlogfileWatcher
from orange_nethack.lightning.strike import get_lightning_client, StrikeClient
from orange_nethack.models import XlogEntry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_test_xlogfile_path() -> Path:
    """Get path to test xlogfile (local or configured)."""
    settings = get_settings()
    # In mock mode, use a local test file
    if settings.mock_lightning:
        test_path = Path("./test_xlogfile")
        return test_path
    return settings.xlogfile_path


def format_xlog_entry(
    name: str,
    death: str = "killed by a goblin",
    score: int = 100,
    turns: int = 50,
    uid: int = 1000,
    role: str = "Val",
    race: str = "Hum",
    gender: str = "Fem",
    align: str = "Neu",
    deathlev: int = 1,
    hp: int = -1,
    maxhp: int = 12,
    conduct: str = "0x0",
    achieve: str = "0x0",
) -> str:
    """Format an xlogfile entry line."""
    now = int(time.time())
    date = datetime.now().strftime("%Y%m%d")

    fields = [
        f"version=3.6.6",
        f"points={score}",
        f"deathdnum=0",
        f"deathlev={deathlev}",
        f"maxlvl={deathlev}",
        f"hp={hp}",
        f"maxhp={maxhp}",
        f"deaths=1",
        f"deathdate={date}",
        f"birthdate={date}",
        f"uid={uid}",
        f"role={role}",
        f"race={race}",
        f"gender={gender}",
        f"align={align}",
        f"name={name}",
        f"death={death}",
        f"conduct={conduct}",
        f"turns={turns}",
        f"achieve={achieve}",
        f"realtime={turns * 2}",
        f"starttime={now - turns * 2}",
        f"endtime={now}",
        f"gender0={gender}",
        f"align0={align}",
        f"flags=0x0",
    ]
    return "\t".join(fields) + "\n"


async def cmd_simulate_payment(session_id: int) -> int:
    """Simulate payment confirmation for a session."""
    await init_db()

    print(f"Simulating payment for session {session_id}...")

    result = await confirm_payment(session_id=session_id, skip_user_creation=True)

    if not result.success:
        print(f"Error: {result.error}")
        return 1

    if result.already_processed:
        print(f"Session {session_id} was already processed")
        return 0

    print(f"Payment confirmed!")
    print(f"  Session ID: {result.session_id}")
    print(f"  Username: {result.username}")
    print(f"  Pot Balance: {result.pot_balance} sats")
    return 0


async def cmd_simulate_game(
    username: str,
    ascend: bool = False,
    score: int = 100,
    death: str | None = None,
    role: str = "Val",
    race: str = "Hum",
    gender: str = "Fem",
    align: str = "Neu",
    deathlev: int = 1,
    hp: int = -1,
    maxhp: int = 12,
    conduct: str = "0x0",
    achieve: str = "0x0",
) -> int:
    """Simulate a game completion by appending to xlogfile."""
    await init_db()
    db = get_db()

    # Determine death message
    if ascend:
        death_msg = "ascended to demigod-hood"
        if score < 1000:
            score = 50000  # Reasonable ascension score
        # Set reasonable ascension values
        deathlev = 0  # Ascended from Astral
        hp = maxhp  # Full HP on ascension
        # Add some achievements for ascension (Bell + Candelabrum + Book + Invocation + Amulet + Planes + Astral + Ascended)
        if achieve == "0x0":
            achieve = "0xFF"  # All major achievements
    else:
        death_msg = death or "killed by a goblin"

    print(f"Simulating game for {username}...")
    print(f"  Death: {death_msg}")
    print(f"  Score: {score}")
    print(f"  Class: {role}-{race} {gender[0]}/{align[0]}")
    print(f"  Level: {deathlev}, HP: {hp}/{maxhp}")
    print(f"  Conduct: {conduct}, Achieve: {achieve}")
    print(f"  Ascended: {ascend}")

    # Check if user has an active session and get the UID
    session = await db.get_session_by_username(username)
    linux_uid = 1000  # Default UID for testing
    if not session:
        print(f"Warning: No session found for username {username}")
        print("Creating xlogfile entry with default UID 1000...")
    elif session["status"] not in ("active", "playing"):
        print(f"Warning: Session status is '{session['status']}', not active/playing")
        linux_uid = session.get("linux_uid") or 1000
    else:
        linux_uid = session.get("linux_uid") or 1000
        print(f"  Linux UID: {linux_uid}")

    # Get xlogfile path
    xlogfile_path = get_test_xlogfile_path()
    print(f"  Xlogfile: {xlogfile_path}")

    # Create xlogfile entry with the session's UID
    # Use a character name (not the Linux username) since Nethack prompts for it
    character_name = "TestHero"
    entry = format_xlog_entry(
        name=character_name,
        death=death_msg,
        score=score,
        uid=linux_uid,
        role=role,
        race=race,
        gender=gender,
        align=align,
        deathlev=deathlev,
        hp=hp,
        maxhp=maxhp,
        conduct=conduct,
        achieve=achieve,
    )

    # Append to xlogfile
    xlogfile_path.parent.mkdir(parents=True, exist_ok=True)
    with open(xlogfile_path, "a") as f:
        f.write(entry)

    print(f"Xlogfile entry appended (character: {character_name}, UID: {linux_uid}).")

    # Process the entry with GameMonitor
    print("Processing game end...")

    # Create a monitor and process the entry directly
    monitor = GameMonitor()
    # Override xlogfile path for testing
    monitor.watcher = XlogfileWatcher(xlogfile_path)
    # Reset position to before our entry
    file_size = xlogfile_path.stat().st_size
    monitor.watcher.position = max(0, file_size - len(entry) - 10)

    # Process new entries
    entries = monitor.watcher.get_new_entries()
    for e in entries:
        if e.uid == linux_uid:
            await monitor._handle_game_end(e)
            print("Game processed!")
            break

    # Show results
    if session:
        updated_session = await db.get_session(session["id"])
        if updated_session:
            print(f"  Session status: {updated_session['status']}")

    pot_balance = await db.get_pot_balance()
    print(f"  Pot balance: {pot_balance} sats")

    return 0


async def cmd_test_flow() -> int:
    """Run a complete automated test flow."""
    await init_db()
    db = get_db()
    settings = get_settings()
    lightning = get_lightning_client()

    print("=" * 60)
    print("Orange Nethack - Full Test Flow")
    print("=" * 60)
    print(f"Mock Lightning: {settings.mock_lightning}")
    print(f"SMTP Configured: {settings.smtp_configured}")
    print()

    # Use random UIDs to avoid collisions with previous test runs
    import random
    test_uid_1 = random.randint(50000, 59999)
    test_uid_2 = random.randint(60000, 69999)

    # Step 1: Check initial state
    print("Step 1: Initial state")
    initial_pot = await db.get_pot_balance()
    print(f"  Initial pot balance: {initial_pot} sats")
    print()

    # Step 2: Create a session with email
    print("Step 2: Creating session with email...")
    from orange_nethack.api.routes import generate_username, generate_password

    username = generate_username()
    password = generate_password()
    test_email = "player@example.com"

    invoice = await lightning.create_invoice(
        amount_sats=settings.ante_sats,
        memo=f"Test - {username}",
    )

    session_id = await db.create_session(
        username=username,
        password=password,
        payment_hash=invoice.payment_hash,
        ante_sats=settings.ante_sats,
        email=test_email,
    )

    # Set a test lightning address
    await db.set_lightning_address(session_id, "test@getalby.com")

    print(f"  Session ID: {session_id}")
    print(f"  Username: {username}")
    print(f"  Email: {test_email}")
    print(f"  Payment hash: {invoice.payment_hash[:16]}...")
    print()

    # Step 3: Verify email stored in DB
    print("Step 3: Verifying session data in database...")
    session = await db.get_session(session_id)
    if session.get("email") != test_email:
        print(f"  Error: Email mismatch! Expected '{test_email}', got '{session.get('email')}'")
        return 1
    print(f"  Email stored: {session.get('email')}")
    print()

    # Step 4: Simulate payment (this would send payment confirmation email)
    # In mock mode, we skip user creation but manually set the UID
    print("Step 4: Simulating payment...")
    print("  (Payment confirmation email would be sent if SMTP configured)")
    result = await confirm_payment(session_id=session_id, skip_user_creation=True, hostname="test.example.com")
    if not result.success:
        print(f"  Error: {result.error}")
        return 1

    # Set fake UID since we skipped user creation
    await db.set_linux_uid(session_id, test_uid_1)
    print(f"  Payment confirmed!")
    print(f"  Pot balance: {result.pot_balance} sats")
    print(f"  Linux UID set: {test_uid_1}")
    print()

    # Step 5: Verify session is active
    print("Step 5: Verifying session status...")
    session = await db.get_session(session_id)
    print(f"  Status: {session['status']}")
    if session["status"] != "active":
        print("  Error: Session should be active!")
        return 1
    print()

    # Step 6: Simulate a game (death, not ascension)
    print("Step 6: Simulating game (death)...")
    print("  (Game result email would be sent if SMTP configured)")
    xlogfile_path = get_test_xlogfile_path()

    # Use the test UID and a character name (not username)
    test_character = "Conan"
    entry = format_xlog_entry(
        name=test_character,
        death="killed by a test goblin",
        score=1234,
        uid=test_uid_1,
        role="Bar",
        race="Hum",
        gender="Mal",
        align="Neu",
        deathlev=5,
        hp=-3,
        maxhp=24,
        conduct="0x4",  # Vegetarian
        achieve="0xC00",  # Mines End + Sokoban
    )
    xlogfile_path.parent.mkdir(parents=True, exist_ok=True)
    with open(xlogfile_path, "a") as f:
        f.write(entry)

    # Process with monitor
    monitor = GameMonitor()
    monitor.watcher = XlogfileWatcher(xlogfile_path)
    file_size = xlogfile_path.stat().st_size
    monitor.watcher.position = max(0, file_size - len(entry) - 10)

    entries = monitor.watcher.get_new_entries()
    for e in entries:
        if e.uid == test_uid_1:
            await monitor._handle_game_end(e)
            break

    # Verify session ended
    session = await db.get_session(session_id)
    print(f"  Session status: {session['status']}")
    if session["status"] != "ended":
        print("  Error: Session should be ended!")
        return 1

    # Check game was recorded
    games = await db.get_recent_games(limit=1)
    if games and games[0]["username"] == username:
        print(f"  Game recorded: score={games[0]['score']}, death='{games[0]['death_reason']}'")
    print()

    # Step 7: Check pot wasn't drained (no ascension)
    print("Step 7: Checking pot balance...")
    pot_after_death = await db.get_pot_balance()
    print(f"  Pot balance: {pot_after_death} sats")
    expected = initial_pot + settings.ante_sats
    if pot_after_death != expected:
        print(f"  Warning: Expected {expected} sats")
    print()

    # Step 8: Test ascension flow with email
    print("Step 8: Testing ascension flow...")

    # Create another session
    username2 = generate_username()
    password2 = generate_password()
    test_email2 = "winner@example.com"

    invoice2 = await lightning.create_invoice(
        amount_sats=settings.ante_sats,
        memo=f"Test ascension - {username2}",
    )

    session_id2 = await db.create_session(
        username=username2,
        password=password2,
        payment_hash=invoice2.payment_hash,
        ante_sats=settings.ante_sats,
        email=test_email2,
    )
    await db.set_lightning_address(session_id2, "winner@getalby.com")

    print(f"  New session: {session_id2} ({username2})")
    print(f"  Email: {test_email2}")

    # Confirm payment and set fake UID
    result2 = await confirm_payment(session_id=session_id2, skip_user_creation=True, hostname="test.example.com")
    await db.set_linux_uid(session_id2, test_uid_2)
    print(f"  Payment confirmed, pot: {result2.pot_balance} sats")
    print(f"  Linux UID set: {test_uid_2}")
    print("  (Payment confirmation email would be sent if SMTP configured)")

    # Simulate ascension
    print("  Simulating ascension...")
    test_character2 = "Gandalf"
    entry2 = format_xlog_entry(
        name=test_character2,
        death="ascended to demigod-hood",
        score=999999,
        uid=test_uid_2,
        role="Wiz",
        race="Elf",
        gender="Mal",
        align="Cha",
        deathlev=0,  # Astral
        hp=150,
        maxhp=150,
        conduct="0x222",  # Vegan + Polypileless + Wishless
        achieve="0xFFF",  # All achievements
    )
    with open(xlogfile_path, "a") as f:
        f.write(entry2)

    # Process
    monitor.watcher.position = xlogfile_path.stat().st_size - len(entry2) - 10
    entries = monitor.watcher.get_new_entries()
    for e in entries:
        if e.uid == test_uid_2:
            await monitor._handle_game_end(e)
            break

    # Verify ascension was recorded
    games = await db.get_recent_games(limit=1)
    if games and games[0]["username"] == username2:
        print(f"  Game recorded: score={games[0]['score']}, ascended={games[0]['ascended']}")
        if games[0]["payout_sats"]:
            print(f"  Payout: {games[0]['payout_sats']} sats")
    print("  (Ascension email would be sent if SMTP configured)")

    pot_after_ascension = await db.get_pot_balance()
    print(f"  Pot after ascension: {pot_after_ascension} sats")
    print()

    # Summary
    print("=" * 60)
    print("Test Flow Complete!")
    print("=" * 60)

    # Show final stats
    stats = await db.get_stats()
    print(f"Total games: {stats.get('total_games', 0)}")
    print(f"Total ascensions: {stats.get('total_ascensions', 0)}")
    print(f"High score: {stats.get('high_score', 0)}")
    print()

    if not settings.smtp_configured:
        print("Note: SMTP not configured. To test actual email sending, set:")
        print("  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM_EMAIL")
        print()

    return 0


async def cmd_show_sessions() -> int:
    """Show all active sessions."""
    await init_db()
    db = get_db()

    sessions = await db.get_active_sessions()

    if not sessions:
        print("No active sessions.")
        return 0

    print(f"Active sessions ({len(sessions)}):")
    print("-" * 140)
    print(f"{'ID':<6} {'Username':<16} {'Status':<10} {'Email':<30} {'Lightning':<40} {'Created':<20}")
    print("-" * 140)

    for s in sessions:
        email = (s.get('email') or '-')[:28]
        lightning = (s.get('lightning_address') or '-')[:38]
        print(
            f"{s['id']:<6} {s['username']:<16} {s['status']:<10} "
            f"{email:<30} {lightning:<40} {s['created_at'][:19]}"
        )

    return 0


async def cmd_show_pot() -> int:
    """Show current pot balance."""
    await init_db()
    db = get_db()
    settings = get_settings()

    balance = await db.get_pot_balance()

    print(f"Pot Balance: {balance:,} sats")
    print(f"Ante: {settings.ante_sats:,} sats")

    return 0


async def cmd_show_games(limit: int = 10) -> int:
    """Show recent games."""
    await init_db()
    db = get_db()

    games = await db.get_recent_games(limit=limit)

    if not games:
        print("No games recorded yet.")
        return 0

    print(f"Recent games ({len(games)}):")
    print("-" * 130)
    print(f"{'ID':<6} {'Username':<16} {'Score':<10} {'Ascended':<10} {'Death':<70}")
    print("-" * 130)

    for g in games:
        death = (g["death_reason"] or "")[:68]
        ascended = "YES!" if g["ascended"] else "no"
        print(f"{g['id']:<6} {g['username']:<16} {g['score']:<10} {ascended:<10} {death}")

    return 0


async def cmd_setup_strike_webhook(webhook_url: str) -> int:
    """Register a webhook subscription with Strike API.

    Strike uses global webhook subscriptions rather than per-invoice URLs.
    This command registers your server's webhook endpoint to receive
    invoice.updated events.
    """
    settings = get_settings()

    if settings.mock_lightning:
        print("Error: Cannot setup Strike webhook in mock mode.")
        print("Set MOCK_LIGHTNING=false and configure STRIKE_API_KEY first.")
        return 1

    if not settings.strike_api_key:
        print("Error: STRIKE_API_KEY is not configured.")
        return 1

    print(f"Registering Strike webhook subscription...")
    print(f"  Webhook URL: {webhook_url}")

    client = get_lightning_client()
    if not isinstance(client, StrikeClient):
        print("Error: Lightning client is not StrikeClient.")
        return 1

    try:
        subscription_id = await client.subscribe_to_webhooks(webhook_url)
        print(f"  Subscription ID: {subscription_id}")
        print()
        print("Webhook subscription created successfully!")
        print("Strike will now send invoice.updated events to your webhook URL.")

        # Generate and save webhook secret to .env file
        print()
        print("Generating webhook secret...")
        webhook_secret = secrets.token_hex(32)

        env_file = _get_env_file()
        if not env_file:
            print("Warning: Could not find .env file to save webhook secret.")
            print(f"Please manually add to your .env file:")
            print(f"  WEBHOOK_SECRET={webhook_secret}")
            return 0

        # Read existing .env content
        try:
            env_content = env_file.read_text()
            lines = env_content.split('\n')

            # Update or add WEBHOOK_SECRET
            secret_found = False
            for i, line in enumerate(lines):
                if line.startswith('WEBHOOK_SECRET='):
                    lines[i] = f'WEBHOOK_SECRET={webhook_secret}'
                    secret_found = True
                    break

            if not secret_found:
                # Add WEBHOOK_SECRET after the security settings section
                lines.append(f'WEBHOOK_SECRET={webhook_secret}')

            # Write back to .env
            env_file.write_text('\n'.join(lines))

            print(f"  Webhook secret saved to: {env_file}")
            print()
            print("IMPORTANT: Restart your services for the webhook secret to take effect:")
            print("  sudo systemctl restart orange-nethack-api orange-nethack-monitor")

        except Exception as e:
            print(f"Warning: Failed to save webhook secret to .env: {e}")
            print(f"Please manually add to {env_file}:")
            print(f"  WEBHOOK_SECRET={webhook_secret}")

        return 0
    except Exception as e:
        print(f"Error: Failed to create webhook subscription: {e}")
        return 1


async def cmd_set_pot(amount: int) -> int:
    """Set pot balance to a specific amount."""
    await init_db()
    db = get_db()

    old_balance = await db.get_pot_balance()
    await db.set_pot_balance(amount)

    print(f"Pot balance updated:")
    print(f"  Previous: {old_balance:,} sats")
    print(f"  New:      {amount:,} sats")

    return 0


async def cmd_reset_pot() -> int:
    """Reset pot balance to initial value."""
    await init_db()
    db = get_db()
    settings = get_settings()

    old_balance = await db.get_pot_balance()
    await db.set_pot_balance(settings.pot_initial)

    print(f"Pot balance reset:")
    print(f"  Previous: {old_balance:,} sats")
    print(f"  New:      {settings.pot_initial:,} sats (initial)")

    return 0


async def cmd_end_session(session_id: int) -> int:
    """Force-end a session."""
    await init_db()
    db = get_db()

    session = await db.get_session(session_id)
    if not session:
        print(f"Error: Session {session_id} not found.")
        return 1

    if session["status"] == "ended":
        print(f"Session {session_id} is already ended.")
        return 0

    await db.update_session_status(session_id, "ended")
    print(f"Session {session_id} ({session['username']}) marked as ended.")
    print(f"  Previous status: {session['status']}")

    return 0


async def cmd_delete_user(username: str) -> int:
    """Delete a Linux user."""
    from orange_nethack.users.manager import UserManager

    user_manager = UserManager()

    if not await user_manager.user_exists(username):
        print(f"User {username} does not exist.")
        return 1

    await user_manager.delete_user(username)
    print(f"User {username} deleted.")

    return 0


async def cmd_list_all_sessions(limit: int = 50) -> int:
    """Show all sessions (not just active)."""
    await init_db()
    db = get_db()

    sessions = await db.get_all_sessions(limit=limit)

    if not sessions:
        print("No sessions found.")
        return 0

    print(f"All sessions (showing up to {limit}):")
    print("-" * 150)
    print(f"{'ID':<6} {'Username':<16} {'Status':<10} {'Email':<30} {'Lightning':<40} {'Created':<20}")
    print("-" * 150)

    for s in sessions:
        email = (s.get('email') or '-')[:28]
        lightning = (s.get('lightning_address') or '-')[:38]
        print(
            f"{s['id']:<6} {s['username']:<16} {s['status']:<10} "
            f"{email:<30} {lightning:<40} {s['created_at'][:19]}"
        )

    return 0


async def cmd_delete_game(game_id: int) -> int:
    """Delete a specific game from the leaderboard."""
    await init_db()
    db = get_db()

    # First show the game being deleted
    games = await db.get_recent_games(limit=100)
    game = next((g for g in games if g["id"] == game_id), None)

    if not game:
        print(f"Error: Game {game_id} not found.")
        return 1

    print(f"Deleting game {game_id}:")
    print(f"  Player: {game['username']}")
    print(f"  Score: {game['score']:,}")
    print(f"  Death: {game['death_reason']}")

    deleted = await db.delete_game(game_id)
    if deleted:
        print("Game deleted.")
        return 0
    else:
        print("Error: Failed to delete game.")
        return 1


async def cmd_clear_games(confirm: bool = False) -> int:
    """Clear all games from the leaderboard."""
    await init_db()
    db = get_db()

    stats = await db.get_stats()
    total = stats.get("total_games") or 0

    if total == 0:
        print("No games to clear.")
        return 0

    if not confirm:
        print(f"This will delete {total} games from the leaderboard.")
        print("Run with --confirm to proceed.")
        return 1

    count = await db.clear_games()
    print(f"Cleared {count} games from the leaderboard.")
    return 0


async def cmd_stats() -> int:
    """Show detailed server statistics."""
    await init_db()
    db = get_db()
    settings = get_settings()

    pot_balance = await db.get_pot_balance()
    stats = await db.get_stats()
    active_sessions = await db.get_active_sessions()
    recent_games = await db.get_recent_games(limit=5)

    print("=" * 60)
    print("Orange Nethack Server Statistics")
    print("=" * 60)
    print()

    print("Pot:")
    print(f"  Balance:     {pot_balance:,} sats")
    print(f"  Ante:        {settings.ante_sats:,} sats")
    print(f"  Initial:     {settings.pot_initial:,} sats")
    print()

    print("Games:")
    print(f"  Total:       {stats.get('total_games') or 0}")
    print(f"  Ascensions:  {stats.get('total_ascensions') or 0}")
    print(f"  High Score:  {(stats.get('high_score') or 0):,}")
    print(f"  Avg Score:   {int(stats.get('avg_score') or 0):,}")
    print()

    print(f"Active Sessions: {len(active_sessions)}")
    for s in active_sessions:
        print(f"  - {s['username']} ({s['status']})")
    print()

    if recent_games:
        print("Recent Games:")
        for g in recent_games:
            status = "ASCENDED" if g['ascended'] else g['death_reason'] if g['death_reason'] else "unknown"
            print(f"  - {g['username']}: {g['score']:,} pts - {status}")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Orange Nethack CLI tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  show-sessions         List active sessions
  show-pot              Show current pot balance
  show-games            Show recent games
  stats                 Show detailed server statistics
  list-all-sessions     Show all sessions (not just active)

Admin Commands:
  set-pot               Set pot balance to specific amount
  reset-pot             Reset pot to initial value
  end-session           Force-end a session
  delete-user           Delete a Linux user
  delete-game           Delete a game from the leaderboard
  clear-games           Clear all games from the leaderboard

Testing Commands:
  simulate-payment      Manually trigger payment confirmation for a session
  simulate-game         Append a fake xlogfile entry and process it
  test-flow             Run a complete automated test

Setup Commands:
  setup-strike-webhook  Register webhook subscription with Strike API

Examples:
  %(prog)s stats
  %(prog)s set-pot 50000
  %(prog)s end-session 5
  %(prog)s delete-user nh_abc12345
  %(prog)s delete-game 42
  %(prog)s clear-games --confirm
  %(prog)s simulate-payment 1
  %(prog)s setup-strike-webhook https://your-server.com/api/webhook/payment
""",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # simulate-payment
    sp_payment = subparsers.add_parser("simulate-payment", help="Simulate payment confirmation")
    sp_payment.add_argument("session_id", type=int, help="Session ID to confirm payment for")

    # simulate-game
    sp_game = subparsers.add_parser("simulate-game", help="Simulate a game completion")
    sp_game.add_argument("username", help="Username (e.g., nh_abc12345)")
    sp_game.add_argument("--ascend", action="store_true", help="Player ascended (wins pot)")
    sp_game.add_argument("--score", type=int, default=100, help="Game score (default: 100)")
    sp_game.add_argument("--death", type=str, help="Death reason (default: 'killed by a goblin')")
    sp_game.add_argument("--role", type=str, default="Val", help="Role/class (Val, Wiz, etc.)")
    sp_game.add_argument("--race", type=str, default="Hum", help="Race (Hum, Elf, Dwa, etc.)")
    sp_game.add_argument("--gender", type=str, default="Fem", help="Gender (Fem, Mal)")
    sp_game.add_argument("--align", type=str, default="Neu", help="Alignment (Law, Neu, Cha)")
    sp_game.add_argument("--deathlev", type=int, default=1, help="Death level")
    sp_game.add_argument("--hp", type=int, default=-1, help="HP at death")
    sp_game.add_argument("--maxhp", type=int, default=12, help="Max HP")
    sp_game.add_argument("--conduct", type=str, default="0x0", help="Conduct bits (hex, e.g. 0x220 for vegan+wishless)")
    sp_game.add_argument("--achieve", type=str, default="0x0", help="Achievement bits (hex, e.g. 0xC00 for mines+sokoban)")

    # test-flow
    subparsers.add_parser("test-flow", help="Run complete automated test")

    # show-sessions
    subparsers.add_parser("show-sessions", aliases=["sessions"], help="Show active sessions")

    # show-pot
    subparsers.add_parser("show-pot", aliases=["pot"], help="Show current pot balance")

    # show-games
    sp_games = subparsers.add_parser("show-games", aliases=["games"], help="Show recent games")
    sp_games.add_argument("--limit", type=int, default=10, help="Number of games to show")

    # stats
    subparsers.add_parser("stats", help="Show detailed server statistics")

    # list-all-sessions
    sp_all_sessions = subparsers.add_parser("list-all-sessions", help="Show all sessions (not just active)")
    sp_all_sessions.add_argument("--limit", type=int, default=50, help="Number of sessions to show")

    # Admin commands
    # set-pot
    sp_set_pot = subparsers.add_parser("set-pot", help="Set pot balance to specific amount")
    sp_set_pot.add_argument("amount", type=int, help="New pot balance in sats")

    # reset-pot
    subparsers.add_parser("reset-pot", help="Reset pot to initial value")

    # end-session
    sp_end_session = subparsers.add_parser("end-session", help="Force-end a session")
    sp_end_session.add_argument("session_id", type=int, help="Session ID to end")

    # delete-user
    sp_delete_user = subparsers.add_parser("delete-user", help="Delete a Linux user")
    sp_delete_user.add_argument("username", help="Username to delete (e.g., nh_abc12345)")

    # delete-game
    sp_delete_game = subparsers.add_parser("delete-game", help="Delete a game from the leaderboard")
    sp_delete_game.add_argument("game_id", type=int, help="Game ID to delete")

    # clear-games
    sp_clear_games = subparsers.add_parser("clear-games", help="Clear all games from the leaderboard")
    sp_clear_games.add_argument("--confirm", action="store_true", help="Confirm clearing all games")

    # setup-strike-webhook
    sp_webhook = subparsers.add_parser("setup-strike-webhook", help="Register Strike webhook subscription")
    sp_webhook.add_argument("webhook_url", help="Your server's webhook URL (e.g., https://your-server.com/api/webhook/payment)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Run the appropriate command
    if args.command == "simulate-payment":
        return asyncio.run(cmd_simulate_payment(args.session_id))
    elif args.command == "simulate-game":
        return asyncio.run(
            cmd_simulate_game(
                username=args.username,
                ascend=args.ascend,
                score=args.score,
                death=args.death,
                role=args.role,
                race=args.race,
                gender=args.gender,
                align=args.align,
                deathlev=args.deathlev,
                hp=args.hp,
                maxhp=args.maxhp,
                conduct=args.conduct,
                achieve=args.achieve,
            )
        )
    elif args.command == "test-flow":
        return asyncio.run(cmd_test_flow())
    elif args.command in ("show-sessions", "sessions"):
        return asyncio.run(cmd_show_sessions())
    elif args.command in ("show-pot", "pot"):
        return asyncio.run(cmd_show_pot())
    elif args.command in ("show-games", "games"):
        return asyncio.run(cmd_show_games(limit=args.limit))
    elif args.command == "stats":
        return asyncio.run(cmd_stats())
    elif args.command == "list-all-sessions":
        return asyncio.run(cmd_list_all_sessions(limit=args.limit))
    elif args.command == "set-pot":
        return asyncio.run(cmd_set_pot(amount=args.amount))
    elif args.command == "reset-pot":
        return asyncio.run(cmd_reset_pot())
    elif args.command == "end-session":
        return asyncio.run(cmd_end_session(session_id=args.session_id))
    elif args.command == "delete-user":
        return asyncio.run(cmd_delete_user(username=args.username))
    elif args.command == "delete-game":
        return asyncio.run(cmd_delete_game(game_id=args.game_id))
    elif args.command == "clear-games":
        return asyncio.run(cmd_clear_games(confirm=args.confirm))
    elif args.command == "setup-strike-webhook":
        return asyncio.run(cmd_setup_strike_webhook(webhook_url=args.webhook_url))
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
