import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from .config import settings


def add_severity_level(_logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """add severity field for cloud logging compatibility"""
    if method_name == "warning":
        event_dict["severity"] = "WARNING"
    else:
        event_dict["severity"] = method_name.upper()
    return event_dict


def configure_logging() -> None:
    """configure structlog with JSON or console output"""

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        add_severity_level,
    ]

    if settings.log_format == "json":
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.log_level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """get configured logger instance"""
    return structlog.get_logger(name)
