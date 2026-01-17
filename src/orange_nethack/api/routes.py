import secrets
import string
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from orange_nethack.config import get_settings
from orange_nethack.database import get_db
from orange_nethack.lightning.lnbits import get_lnbits_client
from orange_nethack.models import (
    GameResult,
    HealthResponse,
    InvoiceResponse,
    PlayRequest,
    PotResponse,
    SessionResponse,
    SessionStatus,
    SetAddressRequest,
    StatsResponse,
)

router = APIRouter()


def generate_username() -> str:
    settings = get_settings()
    suffix = "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8))
    return f"{settings.nethack_user_prefix}{suffix}"


def generate_password() -> str:
    return secrets.token_urlsafe(16)


@router.get("/", response_class=HTMLResponse)
async def landing_page(request: Request):
    settings = get_settings()
    db = get_db()
    pot_balance = await db.get_pot_balance()

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Orange Nethack</title>
    <style>
        body {{
            font-family: monospace;
            background: #1a1a1a;
            color: #ff9500;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }}
        h1 {{ color: #ff9500; text-align: center; }}
        .pot {{ font-size: 2em; text-align: center; margin: 20px 0; }}
        .pot span {{ color: #ffcc00; }}
        pre {{ background: #2a2a2a; padding: 15px; border-radius: 5px; overflow-x: auto; }}
        a {{ color: #ff9500; }}
        .btn {{
            display: inline-block;
            background: #ff9500;
            color: #1a1a1a;
            padding: 10px 20px;
            text-decoration: none;
            border-radius: 5px;
            font-weight: bold;
        }}
        .center {{ text-align: center; }}
    </style>
</head>
<body>
    <h1>🍊 Orange Nethack ⚡</h1>
    <p class="pot">Current Pot: <span>{pot_balance:,} sats</span></p>

    <h2>How to Play</h2>
    <ol>
        <li>Pay the ante of <strong>{settings.ante_sats} sats</strong></li>
        <li>Receive SSH credentials</li>
        <li>SSH in and play Nethack</li>
        <li><strong>Ascend and win the entire pot!</strong></li>
    </ol>

    <h2>API Endpoints</h2>
    <pre>
# Start a new game session
POST /api/play
  Request: {{"lightning_address": "you@getalby.com"}}  # optional
  Response: {{"session_id": 1, "payment_request": "lnbc...", ...}}

# Set payout address (if not set during play)
POST /api/play/{{session_id}}/address
  Request: {{"lightning_address": "you@getalby.com"}}

# Check session status and get credentials
GET /api/session/{{session_id}}
  Response: {{"status": "active", "username": "...", "password": "...", ...}}

# Check current pot
GET /api/pot

# View stats and leaderboard
GET /api/stats
    </pre>

    <h2>Quick Start</h2>
    <pre>
# 1. Create session and get invoice
curl -X POST {request.base_url}api/play \\
  -H "Content-Type: application/json" \\
  -d '{{"lightning_address": "you@getalby.com"}}'

# 2. Pay the invoice with your Lightning wallet

# 3. Get your credentials
curl {request.base_url}api/session/YOUR_SESSION_ID

# 4. SSH in and play!
ssh USERNAME@{request.base_url.hostname}
    </pre>

    <p class="center">
        <a href="/api/stats" class="btn">View Leaderboard</a>
    </p>

    <hr>
    <p style="text-align: center; color: #666;">
        Stack sats. Ascend. Win the pot.
    </p>
</body>
</html>
"""


@router.post("/api/play", response_model=InvoiceResponse)
async def create_play_session(request: Request, body: PlayRequest | None = None):
    settings = get_settings()
    db = get_db()
    lnbits = get_lnbits_client()

    # Check if we have too many active sessions
    active_count = await db.count_active_sessions()
    if active_count >= settings.max_active_sessions:
        raise HTTPException(status_code=503, detail="Server is full, please try again later")

    # Generate credentials
    username = generate_username()
    password = generate_password()

    # Create invoice
    webhook_url = str(request.base_url).rstrip("/") + "/api/webhook/payment"
    try:
        invoice = await lnbits.create_invoice(
            amount_sats=settings.ante_sats,
            memo=f"Orange Nethack ante - {username}",
            webhook_url=webhook_url,
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to create Lightning invoice: {str(e)}"
        )

    # Create session in database
    session_id = await db.create_session(
        username=username,
        password=password,
        payment_hash=invoice.payment_hash,
        ante_sats=settings.ante_sats,
    )

    # Set lightning address if provided
    if body and body.lightning_address:
        await db.set_lightning_address(session_id, body.lightning_address)

    return InvoiceResponse(
        session_id=session_id,
        payment_request=invoice.payment_request,
        payment_hash=invoice.payment_hash,
        amount_sats=invoice.amount_sats,
        expires_at=invoice.expires_at,
    )


@router.post("/api/play/{session_id}/address")
async def set_payout_address(session_id: int, body: SetAddressRequest):
    db = get_db()

    session = await db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session["status"] == "ended":
        raise HTTPException(status_code=400, detail="Session has ended")

    await db.set_lightning_address(session_id, body.lightning_address)
    return {"status": "ok", "lightning_address": body.lightning_address}


@router.get("/api/session/{session_id}", response_model=SessionResponse)
async def get_session(session_id: int, request: Request):
    db = get_db()
    lnbits = get_lnbits_client()

    session = await db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # If pending, check if payment has been received
    if session["status"] == "pending":
        is_paid = await lnbits.check_payment(session["payment_hash"])
        if is_paid:
            # Payment received - this shouldn't normally happen as webhook should catch it
            # But handle it gracefully
            await db.update_session_status(session_id, "active")
            await db.add_to_pot(session["ante_sats"])
            session["status"] = "active"

    # Only return credentials if session is active
    response = SessionResponse(
        id=session["id"],
        status=SessionStatus(session["status"]),
        ante_sats=session["ante_sats"],
        lightning_address=session["lightning_address"],
        created_at=datetime.fromisoformat(session["created_at"]),
    )

    if session["status"] in ("active", "playing"):
        response.username = session["username"]
        response.password = session["password"]
        hostname = request.base_url.hostname or "localhost"
        response.ssh_command = f"ssh {session['username']}@{hostname}"

    return response


@router.get("/api/pot", response_model=PotResponse)
async def get_pot():
    settings = get_settings()
    db = get_db()
    balance = await db.get_pot_balance()

    return PotResponse(
        balance_sats=balance,
        ante_sats=settings.ante_sats,
    )


@router.get("/api/stats", response_model=StatsResponse)
async def get_stats():
    db = get_db()

    pot_balance = await db.get_pot_balance()
    stats = await db.get_stats()
    recent_games = await db.get_recent_games(limit=10)
    leaderboard = await db.get_leaderboard(limit=10)
    ascensions = await db.get_ascensions()

    def to_game_result(g: dict) -> GameResult:
        return GameResult(
            id=g["id"],
            username=g["username"],
            death_reason=g["death_reason"],
            score=g["score"] or 0,
            turns=g["turns"] or 0,
            ascended=bool(g["ascended"]),
            payout_sats=g["payout_sats"],
            ended_at=datetime.fromisoformat(g["ended_at"]) if g["ended_at"] else datetime.utcnow(),
        )

    return StatsResponse(
        pot_balance=pot_balance,
        total_games=stats.get("total_games") or 0,
        total_ascensions=stats.get("total_ascensions") or 0,
        high_score=stats.get("high_score"),
        avg_score=stats.get("avg_score"),
        recent_games=[to_game_result(g) for g in recent_games],
        leaderboard=[to_game_result(g) for g in leaderboard],
        ascensions=[to_game_result(g) for g in ascensions],
    )


@router.get("/api/health", response_model=HealthResponse)
async def health_check():
    settings = get_settings()
    db = get_db()

    pot_balance = await db.get_pot_balance()
    active_sessions = await db.count_active_sessions()

    return HealthResponse(
        status="ok",
        pot_balance=pot_balance,
        active_sessions=active_sessions,
        mock_mode=settings.mock_lightning,
    )
