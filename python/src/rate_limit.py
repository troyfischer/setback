from __future__ import annotations

import time
from typing import cast

from fastapi import HTTPException, Request
from redis import Redis
from redis.exceptions import RedisError

from src.logging import new_logger

log = new_logger("rate-limit")


def get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()

    client = request.client
    if client is None or not client.host:
        return "unknown"
    return client.host


def _enforce_limit(
    redis_client: Redis,
    key: str,
    *,
    limit: int,
    window_seconds: int,
) -> None:
    bucket = int(time.time() // window_seconds)
    window_key = f"rate-limit:{key}:{bucket}"

    try:
        count = cast(int, redis_client.incr(window_key))
        if count == 1:
            redis_client.expire(window_key, window_seconds)
    except RedisError:
        log.exception("rate limit backend unavailable", key=key)
        return

    if count > limit:
        raise HTTPException(429, "rate limit exceeded")


def enforce_limit(
    redis_client: Redis,
    *,
    key: str,
    limit: int,
    window_seconds: int,
) -> None:
    _enforce_limit(
        redis_client,
        key,
        limit=limit,
        window_seconds=window_seconds,
    )
