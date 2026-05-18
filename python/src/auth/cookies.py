from fastapi.responses import Response
from starlette.requests import Request

_LOCAL_DEV_HOSTS = {"localhost", "127.0.0.1"}


def refresh_cookie_secure(request: Request) -> bool:
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    if forwarded_proto:
        scheme = forwarded_proto.split(",", 1)[0].strip()
    else:
        scheme = request.url.scheme

    host = request.url.hostname or ""
    if scheme != "https":
        return False
    return host not in _LOCAL_DEV_HOSTS


def set_refresh_cookie(response: Response, request: Request, refresh_token: str) -> None:
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=30 * 24 * 60 * 60,
        httponly=True,
        secure=refresh_cookie_secure(request),
        samesite="lax",
    )


def clear_refresh_cookie(response: Response, request: Request) -> None:
    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=refresh_cookie_secure(request),
        samesite="lax",
    )
