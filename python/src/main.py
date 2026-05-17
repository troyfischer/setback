from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import redis
import redis.asyncio as redis_async
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine, event, text
from sqlalchemy.engine import Connection
from sqlmodel import SQLModel, create_engine
from starlette.middleware.sessions import SessionMiddleware

import src.auth.routes
import src.game.routes
from src.config import Settings
from src.game.exceptions import InvalidGameStateException, invalid_game_state_handler
from src.game.manager import GameManager
from src.game.sse import ConnectionManager, RedisSubscriber


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = Settings()
    app.state.settings = settings

    # relational db
    engine: Engine = create_engine(
        settings.database_url,
        connect_args={},
        pool_pre_ping=True,
    )

    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(conn: Connection, _: object) -> None:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    SQLModel.metadata.create_all(engine)
    app.state.db_engine = engine

    # game management
    sync_redis = redis.from_url(settings.redis_url)  # type: ignore[no-untyped-call]  # pyright: ignore[reportUnknownMemberType]
    gm = GameManager(sync_redis, engine)
    app.state.gm = gm

    # websocket connection management
    cm = ConnectionManager()
    app.state.cm = cm

    # redis subscriber for pub/sub
    async_redis = redis_async.from_url(settings.redis_url)  # type: ignore[no-untyped-call]  # pyright: ignore[reportUnknownMemberType]
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
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_headers=["*"],
    allow_methods=["*"],
)
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)
app.include_router(src.auth.routes.router)
app.include_router(src.game.routes.router)

app.add_exception_handler(InvalidGameStateException, invalid_game_state_handler)


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring and testing."""
    return {"status": "healthy"}
