from datetime import datetime
from typing import NotRequired, TypedDict

from pydantic import BaseModel, ConfigDict
from sqlmodel import Field, SQLModel


class _BaseClaims(TypedDict):
    sub: str
    exp: datetime | None
    typ: str


class AccessClaims(_BaseClaims):
    """Standard login claims"""


class RefreshClaims(_BaseClaims):
    """Refresh token claims"""

    jti: str


class SSEClaims(_BaseClaims):
    game_id: str
    aud: NotRequired[str]
    jti: NotRequired[str]


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AuthOptions(BaseModel):
    dev_auth_enabled: bool
    oauth_providers: list[str]


class RefreshToken(SQLModel, table=True):
    sub: str = Field(primary_key=True, foreign_key="oauthuser.sub")
    token: str


class TokenData(BaseModel):
    username: str


class User(BaseModel):
    username: str
    email: str | None = None
    disabled: bool = False


class Credentials(BaseModel):
    client_id: str
    client_secret: str

    model_config = ConfigDict(extra="ignore")
