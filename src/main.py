from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

import src.auth.router
import src.game.router
from src.db import create_db_and_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(
    title="Your App Name",
    description="A FastAPI app with JWT authentication",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(SessionMiddleware, secret_key="your-super-secret-key")
app.include_router(src.auth.router.router)
app.include_router(src.game.router.router)
