from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from starlette.requests import Request

from src.auth.cookies import set_refresh_cookie
from src.auth.jwt import JwtManager
from src.auth.limits import auth_dev_token_rate_limit
from src.auth.models import RefreshToken, Token
from src.auth.sso.models import OAuthUser
from src.db import DBSession

router = APIRouter(prefix="/auth", tags=["auth-dev"])


def _persist_refresh_session(
    db: DBSession,
    sub: str,
    refresh_token: str,
    jwt: JwtManager,
) -> None:
    claims = jwt.validate_refresh_token(refresh_token)
    jti = claims.get("jti")
    if not isinstance(jti, str):
        raise RuntimeError("refresh token missing jti")

    db.merge(RefreshToken(sub=sub, token=jti))


@router.post("/dev-token", dependencies=[Depends(auth_dev_token_rate_limit)])
async def dev_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    request: Request,
    db: DBSession,
    jwt: JwtManager,
):
    access_token = jwt.create_access_token(form_data.username)
    refresh_token = jwt.create_refresh_token(form_data.username)
    user = OAuthUser(
        at_hash="test",
        aud="test",
        azp="test",
        email="test@email.com",
        email_verified=True,
        exp=datetime.now(),
        family_name=form_data.username,
        given_name=form_data.username,
        iat=datetime.now(),
        iss="test",
        nonce="test",
        picture="test",
        sub=form_data.username,
        name=form_data.username,
    )
    _ = db.merge(user)
    _persist_refresh_session(db, user.sub, refresh_token, jwt)
    db.commit()

    response = JSONResponse(
        content=Token(access_token=access_token).model_dump(),
        headers={"Cache-Control": "no-store"},
    )
    set_refresh_cookie(response, request, refresh_token)
    return response
