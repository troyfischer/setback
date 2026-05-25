# mypy: disable-error-code="no-any-return"

import logging as std_logging
import os

import structlog
from structlog.typing import FilteringBoundLogger


def _parse_log_level(raw_level: str | None) -> int:
    if not raw_level:
        return std_logging.INFO

    level_name = raw_level.strip().upper()
    level = std_logging.getLevelNamesMapping().get(level_name)
    if isinstance(level, int):
        return level
    return std_logging.INFO


def _configure_logging() -> None:
    level = _parse_log_level(os.getenv("LOG_LEVEL"))
    std_logging.basicConfig(format="%(message)s", level=level)
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )


_configure_logging()


def new_logger(*args, **kwargs) -> FilteringBoundLogger:  # pyright: ignore[reportMissingParameterType,reportUnknownParameterType]
    return structlog.get_logger(*args, **kwargs)  # pyright: ignore[reportAny] # type: ignore
