"""Unified Rich logging configuration for Handler packages."""

import logging
from typing import Literal

from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

HANDLER_THEME = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "error": "red bold",
        "success": "green",
        "dim": "dim",
        "highlight": "bold magenta",
        "agent": "bold blue",
        "url": "underline cyan",
    }
)

console = Console(theme=HANDLER_THEME)


def setup_logging(
    level: LogLevel = "INFO",
    show_path: bool = True,
    show_time: bool = True,
    rich_tracebacks: bool = True,
    suppress_libs: list[str] | None = None,
) -> None:
    """Configure unified Rich logging for Handler.

    Call this once at application entry points (CLI main, server startup).

    Args:
        level: Logging level
        show_path: Show file path in log output
        show_time: Show timestamp in log output
        rich_tracebacks: Use Rich for exception tracebacks
        suppress_libs: Libraries to suppress in tracebacks
    """
    suppress = suppress_libs or []

    handler = RichHandler(
        console=console,
        show_time=show_time,
        show_path=show_path,
        rich_tracebacks=rich_tracebacks,
        tracebacks_show_locals=False,
        tracebacks_suppress=[*suppress],
        markup=True,
        log_time_format="[%X]",
    )

    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[handler],
        force=True,
    )

    for lib in ["httpx", "httpcore", "uvicorn.access"]:
        logging.getLogger(lib).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger for a module.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
