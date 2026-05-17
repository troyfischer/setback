from __future__ import annotations

import enum
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, cast, final

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt  # type: ignore[import-untyped]

from src.auth.models import Claims
from src.auth.secrets import ALGORITHM, SECRET_KEY


class TokenType(enum.StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"
    SSE = "sse"


@final
class JWT:
    security = HTTPBearer()

    def __init__(self, key: str, algorithm: str):
        self._key = key
        self._algorithm = algorithm

    def _create(
        self,
        sub: str,
        typ: str,
        *,
        expires_in: timedelta,
        extra_claims: dict[str, object] | None = None,
    ) -> str:
        claims: dict[str, object] = {
            "sub": sub,
            "exp": datetime.now(tz=UTC) + expires_in,
            "typ": typ,
        }
        if extra_claims:
            claims.update(extra_claims)

        encoded_jwt: str = jwt.encode(
            claims=claims,
            key=self._key,
            algorithm=self._algorithm,
        )
        return encoded_jwt

    def _validate(self, credentials: str, typ: str) -> Claims:
        exc = HTTPException(401, f"Invalid {typ} token")
        try:
            claims: Claims = cast(
                Claims,
                cast(
                    object,
                    jwt.decode(
                        credentials,
                        self._key,
                        algorithms=[self._algorithm],
                        options={"verify_aud": False},
                    ),
                ),
            )
            if claims["typ"] != typ:
                raise exc
            return claims
        except JWTError as e:
            raise exc from e
        except KeyError as e:
            raise exc from e

    def create_access_token(self, sub: str, minutes_to_expire: int = 15) -> str:
        return self._create(
            sub,
            TokenType.ACCESS,
            expires_in=timedelta(minutes=minutes_to_expire),
        )

    def create_refresh_token(self, sub: str, days_to_expire: int = 30) -> str:
        return self._create(
            sub,
            TokenType.REFRESH,
            expires_in=timedelta(days=days_to_expire),
        )

    def create_sse_token(
        self,
        sub: str,
        game_id: str,
        audience: str,
        seconds_to_expire: int = 60,
    ) -> str:
        return self._create(
            sub,
            TokenType.SSE,
            expires_in=timedelta(seconds=seconds_to_expire),
            extra_claims={
                "game_id": game_id,
                "aud": audience,
                "jti": secrets.token_urlsafe(8),
            },
        )

    def validate_access_token(
        self, credentials: HTTPAuthorizationCredentials
    ) -> Claims:
        return self._validate(credentials.credentials, TokenType.ACCESS)

    def validate_refresh_token(self, token: str) -> Claims:
        return self._validate(token, TokenType.REFRESH)

    def validate_sse_token(
        self,
        token: str,
        *,
        expected_game_id: str,
        expected_audience: str,
    ) -> Claims:
        claims = self._validate(token, TokenType.SSE)
        exc = HTTPException(401, "Invalid sse token")

        game_id = claims.get("game_id")
        audience = claims.get("aud")

        if not isinstance(game_id, str) or game_id != expected_game_id:
            raise exc
        if not isinstance(audience, str) or audience != expected_audience:
            raise exc
        return claims


def get_jwt_manager():
    yield JWT(SECRET_KEY, ALGORITHM)


JwtManager = Annotated[JWT, Depends(get_jwt_manager)]
