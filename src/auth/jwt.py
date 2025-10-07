from __future__ import annotations

import enum
from datetime import datetime, timedelta, timezone
from typing import Annotated, cast, final

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from src.auth.models import Claims
from src.auth.secrets import ALGORITHM, SECRET_KEY


class TokenType(enum.StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


@final
class JWT:
    security = HTTPBearer()

    def __init__(self, key: str, algorithm: str):
        self._key = key
        self._algorithm = algorithm

    def _create(self, sub: str, typ: str, minutes_to_expire: int = 15) -> str:
        claims: Claims = {
            "sub": sub,
            "exp": datetime.now(tz=timezone.utc) + timedelta(minutes=minutes_to_expire),
            "typ": typ,
        }
        encoded_jwt = jwt.encode(
            claims=dict(claims),
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
        return self._create(sub, TokenType.ACCESS, minutes_to_expire)

    def create_refresh_token(self, sub: str, days_to_expire: int = 30) -> str:
        return self._create(sub, TokenType.REFRESH, days_to_expire * 24 * 60)

    def validate_access_token(
        self, credentials: HTTPAuthorizationCredentials
    ) -> Claims:
        return self._validate(credentials.credentials, TokenType.ACCESS)

    def validate_refresh_token(self, token: str) -> Claims:
        return self._validate(token, TokenType.REFRESH)


def get_jwt_manager():
    yield JWT(SECRET_KEY, ALGORITHM)


JwtManager = Annotated[JWT, Depends(get_jwt_manager)]
