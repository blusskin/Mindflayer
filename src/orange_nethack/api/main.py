import logging
import uvicorn
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from orange_nethack.config import get_settings
from orange_nethack.database import init_db
from orange_nethack.api.limiter import limiter
from orange_nethack.api.routes import router
from orange_nethack.api.webhooks import webhook_router
from orange_nethack.api.terminal import terminal_router

# Configure logging for the API server
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Path to the frontend build directory
FRONTEND_DIR = Path(__file__).parent.parent.parent.parent / "web" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Orange Nethack",
    description="Bitcoin-themed Nethack server with Lightning payments",
    version="0.1.0",
    lifespan=lifespan,
)

# V7 security fix: Add rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# V3 security fix: Use explicit CORS origins instead of wildcard
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(router)
app.include_router(webhook_router, prefix="/api/webhook")
app.include_router(terminal_router, prefix="/api")

# Serve static frontend if built
if FRONTEND_DIR.exists():
    # Serve static assets
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

    # Catch-all route for SPA - must be after API routes
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve the SPA for all non-API routes."""
        # Check if it's a static file
        file_path = FRONTEND_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        # Otherwise serve index.html for SPA routing
        return FileResponse(FRONTEND_DIR / "index.html")


def run():
    settings = get_settings()
    uvicorn.run(
        "orange_nethack.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    run()
