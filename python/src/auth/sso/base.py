from abc import ABC, abstractmethod

from authlib.integrations.starlette_client import (  # pyright: ignore[reportMissingTypeStubs]
    OAuth,
)
from starlette.config import Config
from starlette.requests import Request

config = Config()
oauth = OAuth(config=config)  # type: ignore[no-untyped-call]


class OAuthProvider(ABC):
    @property
    @abstractmethod
    def provider(self) -> str: ...

    @property
    @abstractmethod
    def redirect_uri(self) -> str: ...

    @abstractmethod
    async def login(self, request: Request): ...

    @abstractmethod
    async def callback(self, request: Request): ...
