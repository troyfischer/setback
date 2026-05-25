from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials

from src.auth.jwt import JWT, JwtManager, get_jwt_manager
from src.auth.models import AccessClaims
from src.auth.providers.models import OAuthUser
from src.db import DBSession


async def validate_access_token(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(JWT.security)],
    jwt: Annotated[JwtManager, Depends(get_jwt_manager)],
) -> AccessClaims:
    """
    Authentication check on the provided credentials
    """

    claims = jwt.validate_access_token(credentials)
    request.state.claims = claims
    return claims


async def get_current_user(
    request: Request,
    claims: Annotated[AccessClaims, Depends(validate_access_token)],
    db: DBSession,
) -> OAuthUser:
    user = db.get(OAuthUser, claims["sub"])
    if not user:
        raise HTTPException(401, "unknown user")

    request.state.user = user
    return user
