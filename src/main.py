from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import redis
import redis.asyncio as redis_async
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic_settings import BaseSettings
from sqlalchemy import Engine
from sqlmodel import SQLModel, create_engine
from starlette.middleware.sessions import SessionMiddleware

import src.auth.router
import src.game.router
from src.game.manager import GameManager
from src.game.sse import ConnectionManager, RedisSubscriber


class Settings(BaseSettings):
    database_url: str = "sqlite:///database.db"
    redis_url: str = "redis://localhost:6379"
    session_secret: str = "your-super-secret-key"
    cors_origins: list[str] = [
        "http://localhost",
        "http://localhost:3000",
        "http://localhost:8081",
        "http://localhost:19006",
        "http://127.0.0.1",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8081",
        "http://127.0.0.1:19006",
    ]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = Settings()
    app.state.settings = settings

    # relational db
    engine: Engine = create_engine(settings.database_url, connect_args={})
    SQLModel.metadata.create_all(engine)
    app.state.db_engine = engine

    # game management
    sync_redis = redis.from_url(settings.redis_url)  # pyright: ignore[reportUnknownMemberType]
    gm = GameManager(sync_redis, engine)
    app.state.gm = gm

    # websocket connection management
    cm = ConnectionManager()
    app.state.cm = cm

    # redis subscriber for pub/sub
    async_redis = redis_async.from_url(settings.redis_url)  # pyright: ignore[reportUnknownMemberType]
    subscriber = RedisSubscriber(async_redis, cm)
    await subscriber.start()

    yield

    # cleanup on shutdown
    await subscriber.stop()


app = FastAPI(
    title="Setback",
    description="An application hosting the card game called setback",
    version="0.1.0",
    lifespan=lifespan,
)

# Session middleware will use settings after lifespan startup
# For now, use a temporary key that will be replaced
settings = Settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_headers=["*"],
    allow_methods=["*"],
)
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)
app.include_router(src.auth.router.router)
app.include_router(src.game.router.router)


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring and testing."""
    return {"status": "healthy"}

