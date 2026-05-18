import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from starlette.requests import Request

from src.auth.cookies import clear_refresh_cookie, set_refresh_cookie
from src.auth.jwt import JwtManager
from src.auth.models import AuthOptions, RefreshToken, Token
from src.auth.sso import GoogleOAuth
from src.auth.sso.models import OAuthUser
from src.auth.utils import get_current_user
from src.db import DBSession
from src.request import RequestContext

router = APIRouter(prefix="/auth")

_handlers = {h.provider: h for h in [GoogleOAuth()]}  # type: ignore[no-untyped-call]


def _get_handler(provider: str) -> GoogleOAuth:
    handler = _handlers.get(provider)
    if handler is None:
        raise HTTPException(404, f"Unknown OAuth provider: {provider}")
    return handler


def _persist_refresh_session(db: DBSession, sub: str, refresh_token: str, jwt: JwtManager) -> None:
    claims = jwt.validate_refresh_token(refresh_token)
    jti = claims.get("jti")
    if not isinstance(jti, str):
        raise HTTPException(500, "refresh token missing jti")

    db.merge(RefreshToken(sub=sub, token=jti))


def _issue_tokens(
    db: DBSession,
    jwt: JwtManager,
    sub: str,
) -> tuple[str, str]:
    access_token = jwt.create_access_token(sub)
    refresh_token = jwt.create_refresh_token(sub)
    _persist_refresh_session(db, sub, refresh_token, jwt)
    return access_token, refresh_token


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


@router.get("/options")
async def auth_options(ctx: RequestContext) -> AuthOptions:
    return AuthOptions(
        dev_auth_enabled=ctx.settings.dev_auth_enabled,
        oauth_providers=sorted(_handlers),
    )


@router.get("/{provider}/callback")
async def oauth_callback(
    ctx: RequestContext,
    provider: str,
    request: Request,
    db: DBSession,
    jwt: JwtManager,
):
    sso_user = await _get_handler(provider).callback(request)
    settings = ctx.settings

    merged = db.merge(sso_user)

    # create tokens
    access_token, refresh_token = _issue_tokens(db, jwt, merged.sub)
    db.commit()

    response = HTMLResponse(
        content=str(HTMLTemplate(access_token, settings.client_origin)),
        headers={
            "Cache-Control": "no-store",
            "X-Frame-Options": "DENY",
        },
    )
    set_refresh_cookie(response, request, refresh_token)
    return response


@router.get("/refresh")
async def refresh(request: Request, db: DBSession, jwt: JwtManager):
    rt = request.cookies.get("refresh_token")
    claims = jwt.validate_refresh_token(rt or "")
    jti = claims.get("jti")
    if not isinstance(jti, str):
        raise HTTPException(401, "Invalid refresh token")

    user = db.get(OAuthUser, claims["sub"])
    session = db.get(RefreshToken, claims["sub"])
    if not user:
        raise HTTPException(401, "User not found")
    elif not session or session.token != jti:
        raise HTTPException(401, "User logged out")

    access_token, refresh_token = _issue_tokens(db, jwt, user.sub)
    db.commit()

    response = JSONResponse(
        content=Token(access_token=access_token).model_dump(),
        headers={"Cache-Control": "no-store"},
    )
    set_refresh_cookie(response, request, refresh_token)
    return response


@router.get("/logout")
async def logout(
    request: Request,
    user: Annotated[OAuthUser, Depends(get_current_user)],
    db: DBSession,
):
    user.logged_in = False
    _ = db.merge(user)
    session = db.get(RefreshToken, user.sub)
    if session:
        db.delete(session)
    db.commit()

    response = PlainTextResponse(user.name + " logged out")
    clear_refresh_cookie(response, request)
    return response


@router.get("/me")
async def me(user: Annotated[OAuthUser, Depends(get_current_user)]) -> OAuthUser:
    return user
