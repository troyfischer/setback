import json
import os
from typing import final, override

from starlette.requests import Request

from src.auth.models import Credentials
from src.auth.sso.base import OAuthProvider, oauth
from src.auth.sso.models import SSOUser


@final
class GoogleOAuth(OAuthProvider):
    def __init__(self):
        creds = self.load_creds()

        self.client = oauth.register(
            name="google",
            client_id=creds.client_id,
            client_secret=creds.client_secret,
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )

    @staticmethod
    def load_creds() -> Credentials:
        path = os.path.join(
            os.getcwd(),
            "resources",
            "secrets",
            "client_secret_876549504601-2tf3amdgcj86ub91fh0iidqq7fdva8t2.apps.googleusercontent.com.json",
        )
        with open(path) as fp:
            content = json.load(fp)

        creds = Credentials.model_validate(content["web"])
        return creds

    @property
    @override
    def redirect_uri(self) -> str:
        return "http://localhost:8000/auth/google/callback"

    @property
    @override
    def provider(self) -> str:
        return "google"

    @override
    async def login(self, request: Request):
        return await self.client.authorize_redirect(request, self.redirect_uri)

    @override
    async def callback(self, request: Request):
        token = await self.client.authorize_access_token(request)

        return SSOUser.model_validate(token["userinfo"])
