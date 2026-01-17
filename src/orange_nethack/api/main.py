import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from orange_nethack.config import get_settings
from orange_nethack.database import init_db
from orange_nethack.api.routes import router
from orange_nethack.api.webhooks import webhook_router


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(webhook_router, prefix="/api/webhook")


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
