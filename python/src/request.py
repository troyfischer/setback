from typing import Annotated, cast, final

from fastapi import Depends, Request
from fastapi.datastructures import State
from redis import Redis
from sqlalchemy import Engine

from src.config import Settings
from src.game.manager import GameManager
from src.game.sse import ConnectionManager


@final
class Context:
    """
    Cleaner access to common utilities attached to the state of the app on startup.
    """

    def __init__(self, request: Request):
        self._request = request

    @property
    def state(self) -> State:
        return cast(State, self._request.app.state)  # pyright: ignore[reportAny]

    @property
    def settings(self) -> Settings:
        return cast(Settings, self.state.settings)

    @property
    def gm(self) -> GameManager:
        """
        Access to the setback game manager.
        """
        return cast(GameManager, self.state.gm)

    @property
    def db(self) -> Engine:
        """
        Access to the database.
        """
        return cast(Engine, self.state.db_engine)

    @property
    def cm(self) -> ConnectionManager:
        """
        Access to the websocket connection manager.
        """
        return cast(ConnectionManager, self.state.cm)

    @property
    def rate_limiter(self) -> Redis:
        return cast(Redis, self.state.rate_limit_redis)


def request_context(request: Request):
    return Context(request)


RequestContext = Annotated[Context, Depends(request_context)]
