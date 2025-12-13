"""Common utilities for the Handler package.

Provides logging, formatting, and output utilities shared across modules.
"""

from .config import (
    get_theme,
    save_theme,
)
from .formatting import (
    format_field_name,
    format_value,
)
from .logging import (
    LogLevel,
    LogRecord,
    TUILogHandler,
    get_logger,
    get_tui_log_handler,
    install_tui_log_handler,
    setup_logging,
)
from .output import Output

__all__ = [
    "LogLevel",
    "LogRecord",
    "Output",
    "TUILogHandler",
    "format_field_name",
    "format_value",
    "get_logger",
    "get_theme",
    "get_tui_log_handler",
    "install_tui_log_handler",
    "save_theme",
    "setup_logging",
]
