"""Simple output formatting system for CLI.

Provides styled console output with ANSI colors.
"""

from __future__ import annotations

import json as json_module
import sys
from typing import Any, TextIO

TERMINAL_STATES = {"completed", "failed", "canceled", "rejected"}
SUCCESS_STATES = {"completed"}
ERROR_STATES = {"failed", "rejected"}
WARNING_STATES = {"canceled"}

# Basic ANSI color codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"


def _supports_color(stream: TextIO) -> bool:
    """Check if the stream supports ANSI colors."""
    if not hasattr(stream, "isatty"):
        return False
    if not stream.isatty():
        return False
    return True


class Output:
    """Manages styled console output.

    Provides a unified interface for outputting text, fields, JSON, and
    markdown with automatic color formatting when supported.
    """

    def __init__(self) -> None:
        self._use_color = _supports_color(sys.stdout)

    def _style(self, text: str, *codes: str) -> str:
        """Apply ANSI codes if color is enabled."""
        if not self._use_color or not codes:
            return text
        return "".join(codes) + text + RESET

    def _print(self, text: str) -> None:
        """Print text to stdout."""
        print(text)

    def line(self, text: str, style: str | None = None) -> None:
        """Print a line of text with optional style."""
        if style and self._use_color:
            code = {
                "green": GREEN,
                "red": RED,
                "yellow": YELLOW,
                "cyan": CYAN,
                "dim": DIM,
                "bold": BOLD,
            }.get(style, "")
            text = self._style(text, code)
        self._print(text)

    def field(
        self,
        name: str,
        value: Any,
        dim_value: bool = False,
        value_style: str | None = None,
    ) -> None:
        """Print a field as 'Name: value' with formatting."""
        value_str = str(value) if value is not None else "none"
        name_part = self._style(f"{name}:", BOLD) if self._use_color else f"{name}:"

        if self._use_color:
            if value_style:
                code = {"green": GREEN, "red": RED, "cyan": CYAN}.get(value_style, "")
                value_part = self._style(value_str, code)
            elif dim_value:
                value_part = self._style(value_str, DIM)
            else:
                value_part = value_str
        else:
            value_part = value_str

        self._print(f"{name_part} {value_part}")

    def header(self, text: str) -> None:
        """Print a section header."""
        styled = self._style(text, BOLD) if self._use_color else text
        self._print(f"\n{styled}")

    def subheader(self, text: str) -> None:
        """Print a subheader (less prominent than header)."""
        styled = self._style(text, BOLD, CYAN) if self._use_color else text
        self._print(styled)

    def blank(self) -> None:
        """Print a blank line."""
        self._print("")

    def state(self, name: str, state: str) -> None:
        """Print a state field with appropriate coloring."""
        lower = state.lower()
        if lower in SUCCESS_STATES:
            style = "green"
        elif lower in ERROR_STATES:
            style = "red"
        elif lower in WARNING_STATES:
            style = "yellow"
        else:
            style = "cyan"

        name_part = self._style(f"{name}:", BOLD) if self._use_color else f"{name}:"
        code = {"green": GREEN, "red": RED, "yellow": YELLOW, "cyan": CYAN}.get(
            style, ""
        )
        value_part = self._style(state, code) if self._use_color else state
        self._print(f"{name_part} {value_part}")

    def success(self, text: str) -> None:
        """Print a success message."""
        self.line(text, "green")

    def error(self, text: str) -> None:
        """Print an error message."""
        styled = self._style(text, RED, BOLD) if self._use_color else text
        self._print(styled)

    def warning(self, text: str) -> None:
        """Print a warning message."""
        self.line(text, "yellow")

    def dim(self, text: str) -> None:
        """Print dimmed/muted text."""
        self.line(text, "dim")

    def json(self, data: Any) -> None:
        """Print JSON data."""
        json_str = json_module.dumps(data, indent=2, default=str)
        self._print(json_str)

    def markdown(self, text: str) -> None:
        """Print markdown content (as plain text)."""
        self._print(text)

    def list_item(self, text: str, bullet: str = "•") -> None:
        """Print a list item with bullet."""
        self._print(f"  {bullet} {text}")
