class InvalidGameStateException(Exception):
    pass


class InvalidPhaseException(InvalidGameStateException):
    pass


class InvalidTurnException(InvalidGameStateException):
    pass


class InvalidCardException(InvalidGameStateException):
    pass
