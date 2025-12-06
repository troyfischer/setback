from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import redis
import redis.asyncio as redis_async
from fastapi import FastAPI
from pydantic_settings import BaseSettings
from sqlalchemy import Engine
from sqlmodel import SQLModel, create_engine
from starlette.middleware.sessions import SessionMiddleware

import src.auth.router
import src.game.router
from src.game.manager import GameManager
from src.game.websocket import ConnectionManager, RedisSubscriber


class Settings(BaseSettings):
    database_url: str = "sqlite:///database.db"
    redis_url: str = "redis://localhost:6379"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = Settings()

    # relational db
    connect_args = {}
    engine: Engine = create_engine(settings.database_url, connect_args=connect_args)
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
    description="A FastAPI app with JWT authentication",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(SessionMiddleware, secret_key="your-super-secret-key")
app.include_router(src.auth.router.router)
app.include_router(src.game.router.router)
