from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

import src.auth.router
import src.game.router
from src.db import create_db_and_tables
from src.game.websocket import RedisSubscriber, connection_manager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    create_db_and_tables()

    # Start Redis subscriber for pub/sub
    redis_url = "redis://localhost:6379"
    subscriber = RedisSubscriber(redis_url, connection_manager)
    await subscriber.start()

    yield

    # Cleanup on shutdown
    await subscriber.stop()


app = FastAPI(
    title="Your App Name",
    description="A FastAPI app with JWT authentication",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(SessionMiddleware, secret_key="your-super-secret-key")
app.include_router(src.auth.router.router)
app.include_router(src.game.router.router)
