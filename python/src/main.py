from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import redis
import redis.asyncio as redis_async
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine
from starlette.middleware.sessions import SessionMiddleware

import src.auth.dev_routes
import src.auth.routes
import src.game.routes
from src.config import AppEnv, Settings
from src.db import create_db_engine, create_schema
from src.game.exceptions import InvalidGameStateException, invalid_game_state_handler
from src.game.manager import GameManager
from src.game.sse import ConnectionManager, RedisSubscriber

API_PREFIX = "/api"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = app.state.settings
    app.state.settings = settings

    # relational db
    engine: Engine = create_db_engine(settings)
    if settings.should_auto_create_schema:
        create_schema(engine)
    app.state.db_engine = engine

    # game management
    sync_redis = redis.from_url(settings.redis_url)
    app.state.rate_limit_redis = sync_redis
    gm = GameManager(sync_redis, engine)
    app.state.gm = gm

    # websocket connection management
    cm = ConnectionManager(
        max_connections_per_game=settings.game_sse_connections_per_game_limit,
    )
    app.state.cm = cm

    # redis subscriber for pub/sub
    async_redis = redis_async.from_url(settings.redis_url)
    subscriber = RedisSubscriber(async_redis, cm)
    await subscriber.start()

    yield

    # cleanup on shutdown
    await subscriber.stop()
    sync_redis.close()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    settings.validate_runtime()

    app = FastAPI(
        title="Setback",
        description="An application hosting the card game called setback",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=True,
        allow_headers=["*"],
        allow_methods=["*"],
    )
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        https_only=settings.app_env == AppEnv.PROD,
    )
    app.include_router(src.auth.routes.router, prefix=API_PREFIX)
    if settings.dev_auth_enabled:
        app.include_router(src.auth.dev_routes.router, prefix=API_PREFIX)
    app.include_router(src.game.routes.router, prefix=API_PREFIX)

    app.add_exception_handler(InvalidGameStateException, invalid_game_state_handler)

    @app.get(f"{API_PREFIX}/health")
    async def health_check():
        """Health check endpoint for monitoring and testing."""
        return {"status": "healthy"}

    return app


app = create_app()
