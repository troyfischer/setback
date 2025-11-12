from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials

from src.auth.jwt import JWT, JwtManager, get_jwt_manager
from src.auth.models import Claims
from src.auth.sso.models import SSOUser
from src.db import DBSession


async def validate_access_token(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(JWT.security)],
    jwt: Annotated[JwtManager, Depends(get_jwt_manager)],
) -> Claims:
    """
    Authentication check on the provided credentials
    """

    claims = jwt.validate_access_token(credentials)
    request.state.claims = claims
    return claims


async def get_current_user(
    request: Request,
    claims: Annotated[Claims, Depends(validate_access_token)],
    db: DBSession,
) -> SSOUser:
    user = db.get(SSOUser, claims["sub"])
    if not user:
        raise HTTPException(401, "unknown user")

    request.state.user = user
    return user
