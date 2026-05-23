from typing import Annotated

from fastapi import Depends, Request

from src.auth.sso.models import OAuthUser
from src.auth.utils import get_current_user
from src.rate_limit import enforce_limit, get_client_ip
from src.request import RequestContext


async def game_join_rate_limit(
    ctx: RequestContext,
    request: Request,
    user: Annotated[OAuthUser, Depends(get_current_user)],
) -> None:
    settings = ctx.settings
    enforce_limit(
        ctx.rate_limiter,
        key=f"game-join:user:{user.sub}:ip:{get_client_ip(request)}",
        limit=settings.game_join_rate_limit,
        window_seconds=settings.game_join_rate_window_seconds,
    )


async def subscribe_token_rate_limit(
    ctx: RequestContext,
    request: Request,
    user: Annotated[OAuthUser, Depends(get_current_user)],
) -> None:
    settings = ctx.settings
    enforce_limit(
        ctx.rate_limiter,
        key=f"game-subscribe-token:user:{user.sub}:ip:{get_client_ip(request)}",
        limit=settings.game_subscribe_token_rate_limit,
        window_seconds=settings.game_subscribe_token_rate_window_seconds,
    )


GameJoinRateLimit = Annotated[None, Depends(game_join_rate_limit)]
SubscribeTokenRateLimit = Annotated[None, Depends(subscribe_token_rate_limit)]
