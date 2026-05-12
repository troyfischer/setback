from fastapi import Request
from fastapi.responses import JSONResponse


class InvalidGameStateException(Exception):
    pass


class InvalidPhaseException(InvalidGameStateException):
    pass


class InvalidTurnException(InvalidGameStateException):
    pass


class InvalidCardException(InvalidGameStateException):
    pass


async def invalid_game_state_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=400, content={"detail": str(exc)})
