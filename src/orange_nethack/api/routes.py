import logging
import secrets
import string
from datetime import datetime
from fastapi import APIRouter, Header, HTTPException, Request

from orange_nethack.api.limiter import limiter
from orange_nethack.api.webhooks import confirm_payment
from orange_nethack.config import get_settings
from orange_nethack.database import get_db
from orange_nethack.lightning.strike import get_lightning_client
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

logger = logging.getLogger(__name__)
router = APIRouter()


def generate_username() -> str:
    settings = get_settings()
    suffix = "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8))
    return f"{settings.nethack_user_prefix}{suffix}"


def generate_password() -> str:
    return secrets.token_urlsafe(16)




@router.post("/api/play", response_model=InvoiceResponse)
@limiter.limit("5/minute")  # V7 security fix: Rate limit session creation
async def create_play_session(request: Request, body: PlayRequest):
    settings = get_settings()
    db = get_db()
    lightning = get_lightning_client()

    # Check if we have too many active sessions
    active_count = await db.count_active_sessions()
    if active_count >= settings.max_active_sessions:
        raise HTTPException(status_code=503, detail="Server is full, please try again later")

    # Generate credentials
    username = generate_username()
    password = generate_password()
    access_token = secrets.token_urlsafe(24)

    # Create invoice
    webhook_url = str(request.base_url).rstrip("/") + "/api/webhook/payment"
    try:
        invoice = await lightning.create_invoice(
            amount_sats=settings.ante_sats,
            memo=f"Orange Nethack ante - {username}",
            webhook_url=webhook_url,
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to create Lightning invoice: {str(e)}"
        )

    # Create session in database with lightning address and optional email
    session_id = await db.create_session(
        username=username,
        password=password,
        payment_hash=invoice.payment_hash,
        ante_sats=settings.ante_sats,
        email=body.email,
        access_token=access_token,
    )

    # Set lightning address (now required)
    await db.set_lightning_address(session_id, body.lightning_address)

    return InvoiceResponse(
        session_id=session_id,
        access_token=access_token,
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
@limiter.limit("30/minute")  # V7 security fix: Rate limit payment status polling
async def get_session(
    session_id: int,
    request: Request,
    authorization: str | None = Header(None),
    token: str | None = None,  # Query param - deprecated, for backward compatibility
):
    # V8 security fix: Support Authorization header, deprecate query param
    access_token = None
    if authorization and authorization.startswith("Bearer "):
        access_token = authorization[7:]  # Remove "Bearer " prefix
    elif token:
        access_token = token
        logger.warning(
            f"Token in URL query param (session {session_id}) - "
            "use Authorization header instead"
        )

    db = get_db()
    lightning = get_lightning_client()

    session = await db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # If pending, check if payment has been received
    if session["status"] == "pending":
        is_paid = await lightning.check_payment(session["payment_hash"])
        if is_paid:
            # Payment received - use confirm_payment to create user and send email
            hostname = request.base_url.hostname or "localhost"
            result = await confirm_payment(session_id=session_id, hostname=hostname)
            if result.success:
                session["status"] = "active"

    # Require valid token for credential access
    if session["status"] in ("active", "playing"):
        # V6 security fix: Use constant-time comparison to prevent timing attacks
        if not secrets.compare_digest(
            access_token or "",
            session.get("access_token") or ""
        ):
            raise HTTPException(status_code=403, detail="Invalid or missing access token")

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
@limiter.limit("60/minute")  # V7 security fix: Rate limit stats queries
async def get_stats(request: Request):
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
            role=g.get("role"),
            race=g.get("race"),
            gender=g.get("gender"),
            align=g.get("align"),
            deathlev=g.get("deathlev"),
            hp=g.get("hp"),
            maxhp=g.get("maxhp"),
            conduct=g.get("conduct"),
            achieve=g.get("achieve"),
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
