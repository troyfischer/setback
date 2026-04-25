# mypy: disable-error-code="no-any-return"

import structlog
from structlog.typing import FilteringBoundLogger


def new_logger(*args, **kwargs) -> FilteringBoundLogger:  # pyright: ignore[reportMissingParameterType,reportUnknownParameterType]
    return structlog.get_logger(*args, **kwargs)  # pyright: ignore[reportAny] # type: ignore
