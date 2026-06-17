"""Logging configuration using structlog.

Both structlog-native loggers and foreign stdlib loggers (e.g. uvicorn) are routed
through a single structlog ``ProcessorFormatter`` for consistent output.
"""

import logging

import structlog

from app.config import get_settings

_UVICORN_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")


class _SuppressHealthCheck(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        """Drop uvicorn access-log records for /health liveness probes."""
        return " /health " not in record.getMessage()


def configure_logging() -> None:
    """Configure structlog and the stdlib root logger to share one output pipeline.

    The level is read from settings; uvicorn loggers propagate to the root handler and
    /health access-log lines are dropped so liveness probes don't flood the logs.
    """
    numeric_level = getattr(logging, get_settings().log_level.upper(), logging.INFO)

    shared_processors: list[structlog.types.Processor] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    structlog.configure(
        processors=[*shared_processors, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        logger_factory=structlog.stdlib.LoggerFactory(),
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.dev.ConsoleRenderer(),
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(numeric_level)

    logging.getLogger("aiosmtplib").setLevel(logging.WARNING)

    for name in _UVICORN_LOGGERS:
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True

    access_logger = logging.getLogger("uvicorn.access")
    access_logger.filters.clear()
    access_logger.addFilter(_SuppressHealthCheck())
