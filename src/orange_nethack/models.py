from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class SessionStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    PLAYING = "playing"
    ENDED = "ended"


# Request models
class PlayRequest(BaseModel):
    lightning_address: str | None = Field(
        None, description="Lightning address for payout on ascension"
    )
    email: str | None = Field(
        None, description="Email for payment confirmation and game result notifications"
    )


class SetAddressRequest(BaseModel):
    lightning_address: str = Field(..., description="Lightning address for payout")


# Response models
class InvoiceResponse(BaseModel):
    session_id: int
    access_token: str = Field(..., description="Token for accessing session credentials")
    payment_request: str = Field(..., description="BOLT11 invoice to pay")
    payment_hash: str
    amount_sats: int
    expires_at: datetime | None = None


class SessionResponse(BaseModel):
    id: int
    status: SessionStatus
    username: str | None = None
    password: str | None = None  # Only returned when status is active
    ssh_command: str | None = None
    lightning_address: str | None = None
    ante_sats: int
    created_at: datetime


class PotResponse(BaseModel):
    balance_sats: int
    ante_sats: int


class GameResult(BaseModel):
    id: int
    username: str
    death_reason: str | None
    score: int
    turns: int
    ascended: bool
    payout_sats: int | None
    ended_at: datetime


class StatsResponse(BaseModel):
    pot_balance: int
    total_games: int
    total_ascensions: int
    high_score: int | None
    avg_score: float | None
    recent_games: list[GameResult]
    leaderboard: list[GameResult]
    ascensions: list[GameResult]


class HealthResponse(BaseModel):
    status: str
    pot_balance: int
    active_sessions: int
    mock_mode: bool = False


# Webhook models
class LNbitsWebhookPayload(BaseModel):
    payment_hash: str
    payment_request: str | None = None
    amount: int  # In millisatoshis
    memo: str | None = None
    time: int | None = None
    pending: bool = False


# xlogfile parsed entry
class XlogEntry(BaseModel):
    version: str | None = None
    points: int = 0
    deathdnum: int | None = None
    deathlev: int | None = None
    maxlvl: int | None = None
    hp: int | None = None
    maxhp: int | None = None
    deaths: int | None = None
    deathdate: str | None = None
    birthdate: str | None = None
    uid: int | None = None
    role: str | None = None
    race: str | None = None
    gender: str | None = None
    align: str | None = None
    name: str = ""
    death: str = ""
    conduct: str | None = None
    turns: int = 0
    achieve: str | None = None
    realtime: int | None = None
    starttime: int | None = None
    endtime: int | None = None
    gender0: str | None = None
    align0: str | None = None
    flags: str | None = None

    @property
    def ascended(self) -> bool:
        return "ascended" in self.death.lower()

    @property
    def score(self) -> int:
        return self.points
