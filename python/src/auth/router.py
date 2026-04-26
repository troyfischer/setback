import json
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
from starlette.requests import Request

from src.auth.jwt import JwtManager
from src.auth.models import Token
from src.auth.sso import GoogleOAuth
from src.auth.sso.models import OAuthUser
from src.auth.utils import get_current_user
from src.db import DBSession
from src.request import RequestContext

router = APIRouter(prefix="/auth")

_handlers = {h.provider: h for h in [GoogleOAuth()]}


def _get_handler(provider: str) -> GoogleOAuth:
    handler = _handlers.get(provider)
    if handler is None:
        raise HTTPException(404, f"Unknown OAuth provider: {provider}")
    return handler


@router.get("/{provider}/login")
async def oauth_login(provider: str, request: Request):
    return await _get_handler(provider).login(request)


# TODO: move this elsewhere
# return html snippet instead of raw json


class HTMLTemplate:
    html_template = """
<html>
    <script>
    const payload = {{ access_token: {} }};
    const targetOrigin = {};
    if (window.opener) {{
        window.opener.postMessage(payload, targetOrigin);
    }}
    window.close();
    </script>
    <p>You can close this window.</p>
</html>"""

    def __init__(self, access_token: str, client_origin: str):
        self._access_token = access_token
        self._client_origin = client_origin

    def __str__(self):
        return self.html_template.format(
            *(map(json.dumps, (self._access_token, self._client_origin)))
        )


@router.get("/{provider}/callback")
async def oauth_callback(
    ctx: RequestContext,
    provider: str,
    request: Request,
    response: Response,
    db: DBSession,
    jwt: JwtManager,
):
    sso_user = await _get_handler(provider).callback(request)
    settings = ctx.settings

    merged = db.merge(sso_user)
    db.commit()

    # create tokens
    access_token = jwt.create_access_token(merged.sub)
    refresh_token = jwt.create_refresh_token(merged.sub)

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=30 * 24 * 60 * 60,  # 30 days in seconds
        httponly=True,  # Can't be accessed by JavaScript
        secure=True,  # HTTPS only (set False for localhost dev)
        samesite="lax",  # CSRF protection
    )
    return HTMLResponse(
        content=str(HTMLTemplate(access_token, settings.client_origin)),
        headers={
            "Cache-Control": "no-store",
            "X-Frame-Options": "DENY",
        },
    )


@router.get("/refresh")
async def refresh(request: Request, db: DBSession, jwt: JwtManager):
    rt = request.cookies.get("refresh_token")
    claims = jwt.validate_refresh_token(rt or "")

    user = db.get(OAuthUser, claims["sub"])
    if not user:
        raise HTTPException(401, "User not found")
    elif not user.logged_in:
        # TODO: this adds a level of additional complication but it just seems
        # like a security risk without it?
        raise HTTPException(401, "User logged out")

    token = jwt.create_access_token(user.sub)
    return Token(access_token=token)


@router.get("/logout")
async def logout(user: Annotated[OAuthUser, Depends(get_current_user)], db: DBSession):
    user.logged_in = False
    _ = db.merge(user)
    db.commit()

    return user.name + " logged out"


@router.get("/me")
async def me(user: Annotated[OAuthUser, Depends(get_current_user)]) -> OAuthUser:
    return user


@router.post("/token")
async def dev_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DBSession,
    jwt: JwtManager,
):
    token = jwt.create_access_token(form_data.username)
    user = OAuthUser(
        at_hash="test",
        aud="test",
        azp="test",
        email="test",
        email_verified=True,
        exp=datetime.now(),
        family_name="test",
        given_name="test",
        iat=datetime.now(),
        iss="test",
        nonce="test",
        picture="test",
        sub=form_data.username,
        name="test",
    )
    _ = db.merge(user)
    db.commit()

    return Token(access_token=token)
