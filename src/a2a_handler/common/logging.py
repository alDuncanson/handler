"""Simple logging configuration for Handler.

Provides basic console logging with optional TUI log capture.
"""

import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


@dataclass
class LogRecord:
    """A single log record for TUI display."""

    timestamp: datetime
    level: str
    name: str
    message: str


class TUILogHandler(logging.Handler):
    """Logging handler that captures records for TUI display.

    Stores formatted log lines and notifies a callback when new records arrive.
    """

    def __init__(
        self,
        max_records: int = 1000,
        callback: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__()
        self.max_records = max_records
        self.lines: list[str] = []
        self.callback = callback

    def set_callback(self, callback: Callable[[str], None] | None) -> None:
        """Set or update the callback for new log lines."""
        self.callback = callback

    def emit(self, record: logging.LogRecord) -> None:
        """Handle a log record."""
        try:
            timestamp = datetime.fromtimestamp(record.created)
            time_str = timestamp.strftime("%H:%M:%S.%f")[:-3]
            short_name = record.name.split(".")[-1]
            message = self.format(record)

            line = f"{time_str} {record.levelname:>5} {short_name}: {message}"
            self.lines.append(line)

            if len(self.lines) > self.max_records:
                self.lines = self.lines[-self.max_records :]

            if self.callback:
                self.callback(line)

        except Exception:
            self.handleError(record)

    def get_lines(self) -> list[str]:
        """Get all stored log lines."""
        return list(self.lines)

    def clear(self) -> None:
        """Clear all stored lines."""
        self.lines.clear()


_tui_handler: TUILogHandler | None = None


def get_tui_log_handler() -> TUILogHandler:
    """Get or create the singleton TUI log handler."""
    global _tui_handler
    if _tui_handler is None:
        _tui_handler = TUILogHandler()
        _tui_handler.setFormatter(logging.Formatter("%(message)s"))
    return _tui_handler


def install_tui_log_handler(level: int = logging.DEBUG) -> TUILogHandler:
    """Install the TUI log handler on the root logger.

    Args:
        level: Minimum log level to capture

    Returns:
        The installed handler
    """
    handler = get_tui_log_handler()
    handler.setLevel(level)

    root_logger = logging.getLogger()

    if handler not in root_logger.handlers:
        root_logger.addHandler(handler)

    root_logger.setLevel(min(root_logger.level or level, level))

    return handler


def setup_logging(
    level: LogLevel = "INFO",
    show_time: bool = True,
) -> None:
    """Configure simple console logging for CLI.

    Args:
        level: Logging level
        show_time: Show timestamp in log output
    """
    format_str = "%(levelname)s: %(message)s"
    if show_time:
        format_str = "[%(asctime)s] " + format_str

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(format_str, datefmt="%H:%M:%S"))

    logging.basicConfig(
        level=level,
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
