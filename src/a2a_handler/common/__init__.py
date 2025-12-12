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
    HANDLER_THEME,
    LogLevel,
    console,
    get_logger,
    setup_logging,
)
from .output import (
    Output,
    OutputMode,
    get_output_context,
)

__all__ = [
    "HANDLER_THEME",
    "LogLevel",
    "Output",
    "OutputMode",
    "console",
    "format_field_name",
    "format_value",
    "get_logger",
    "get_output_context",
    "get_theme",
    "save_theme",
    "setup_logging",
]
