from datetime import datetime

from sqlmodel import Field, SQLModel


class OAuthUser(SQLModel, table=True):
    at_hash: str
    aud: str
    azp: str
    email: str
    email_verified: bool
    exp: datetime
    family_name: str
    given_name: str
    iat: datetime
    iss: str
    name: str
    nonce: str
    picture: str
    sub: str = Field(primary_key=True)
    logged_in: bool = True
