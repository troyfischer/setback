from typing import Annotated

from fastapi import Depends, Request

from src.rate_limit import enforce_limit, get_client_ip
from src.request import RequestContext


async def auth_login_rate_limit(ctx: RequestContext, request: Request) -> None:
    settings = ctx.settings
    enforce_limit(
        ctx.rate_limiter,
        key=f"auth-login:ip:{get_client_ip(request)}",
        limit=settings.auth_login_rate_limit,
        window_seconds=settings.auth_login_rate_window_seconds,
    )


async def auth_callback_rate_limit(ctx: RequestContext, request: Request) -> None:
    settings = ctx.settings
    enforce_limit(
        ctx.rate_limiter,
        key=f"auth-callback:ip:{get_client_ip(request)}",
        limit=settings.auth_callback_rate_limit,
        window_seconds=settings.auth_callback_rate_window_seconds,
    )


async def auth_refresh_rate_limit(ctx: RequestContext, request: Request) -> None:
    settings = ctx.settings
    enforce_limit(
        ctx.rate_limiter,
        key=f"auth-refresh:ip:{get_client_ip(request)}",
        limit=settings.auth_refresh_rate_limit,
        window_seconds=settings.auth_refresh_rate_window_seconds,
    )


async def auth_dev_token_rate_limit(ctx: RequestContext, request: Request) -> None:
    settings = ctx.settings
    enforce_limit(
        ctx.rate_limiter,
        key=f"auth-dev-token:ip:{get_client_ip(request)}",
        limit=settings.auth_dev_token_rate_limit,
        window_seconds=settings.auth_dev_token_rate_window_seconds,
    )


AuthLoginRateLimit = Annotated[None, Depends(auth_login_rate_limit)]
AuthCallbackRateLimit = Annotated[None, Depends(auth_callback_rate_limit)]
AuthRefreshRateLimit = Annotated[None, Depends(auth_refresh_rate_limit)]
AuthDevTokenRateLimit = Annotated[None, Depends(auth_dev_token_rate_limit)]
