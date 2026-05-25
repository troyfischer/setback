from typing import final, override

from pydantic_settings import BaseSettings
from starlette.requests import Request

from src.auth.models import Credentials
from src.auth.sso.base import OAuthProvider, oauth
from src.auth.sso.models import OAuthUser


class GoogleOIDCSettings(BaseSettings):
    base_url: str = "http://localhost"
    google_client_id: str | None = None
    google_client_secret: str | None = None

    @property
    def credentials(self) -> Credentials:
        if not self.google_client_id or not self.google_client_secret:
            raise RuntimeError("Google OIDC is not configured")
        return Credentials(
            client_id=self.google_client_id,
            client_secret=self.google_client_secret,
        )


@final
class GoogleOIDC(OAuthProvider):
    def __init__(self) -> None:
        self.settings = GoogleOIDCSettings()
        creds = self.settings.credentials

        self.client = oauth.register(
            name="google",
            client_id=creds.client_id,
            client_secret=creds.client_secret,
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )

    @property
    @override
    def redirect_uri(self) -> str:
        return f"{self.settings.base_url}/api/auth/google/callback"

    @property
    @override
    def provider(self) -> str:
        return "google"

    @override
    async def login(self, request: Request) -> object:
        return await self.client.authorize_redirect(request, self.redirect_uri)

    @override
    async def callback(self, request: Request) -> OAuthUser:
        token = await self.client.authorize_access_token(request)

        return OAuthUser.model_validate(token["userinfo"])
