"""Output formatting system with mode-aware styling.

Provides a unified output interface supporting raw, text, and JSON modes.
"""

from __future__ import annotations

import json as json_module
import re
from contextlib import contextmanager
from enum import Enum
from typing import Any, Generator

from rich.console import Console
from rich.markdown import Markdown

from .logging import console


TERMINAL_STATES = {"completed", "failed", "canceled", "rejected"}
SUCCESS_STATES = {"completed"}
ERROR_STATES = {"failed", "rejected"}
WARNING_STATES = {"canceled"}


class OutputMode(Enum):
    """Output mode for CLI commands."""

    RAW = "raw"
    TEXT = "text"
    JSON = "json"


def _strip_markup(text: str) -> str:
    """Strip Rich markup for raw output."""
    return re.sub(r"\[/?[^\]]+\]", "", text)


class Output:
    """Manages output mode and styling.

    Provides a unified interface for outputting text, fields, JSON, and
    markdown with automatic mode-aware formatting.
    """

    def __init__(self, mode: OutputMode) -> None:
        """Initialize output context.

        Args:
            mode: Output mode (raw, text, or json)
        """
        self.mode = mode
        self._raw_console = Console(highlight=False, markup=False)

    def _print(self, text: str, style: str | None = None) -> None:
        """Internal print method that respects mode."""
        if self.mode == OutputMode.RAW:
            self._raw_console.print(_strip_markup(text))
        elif self.mode == OutputMode.TEXT and style:
            console.print(text, style=style)
        else:
            console.print(text, markup=self.mode == OutputMode.TEXT)

    def line(self, text: str, style: str | None = None) -> None:
        """Print a line of text with optional style."""
        self._print(text, style)

    def field(
        self,
        name: str,
        value: Any,
        dim_value: bool = False,
        value_style: str | None = None,
    ) -> None:
        """Print a field as 'Name: value' with formatting."""
        value_str = str(value) if value is not None else "none"

        if self.mode == OutputMode.TEXT:
            if value_style:
                console.print(f"[bold]{name}:[/bold] [{value_style}]{value_str}[/]")
            elif dim_value:
                console.print(f"[bold]{name}:[/bold] [dim]{value_str}[/dim]")
            else:
                console.print(f"[bold]{name}:[/bold] {value_str}")
        else:
            self._raw_console.print(f"{name}: {_strip_markup(value_str)}")

    def header(self, text: str) -> None:
        """Print a section header."""
        if self.mode == OutputMode.TEXT:
            console.print(f"\n[bold]{text}[/bold]")
        else:
            self._raw_console.print(f"\n{text}")

    def subheader(self, text: str) -> None:
        """Print a subheader (less prominent than header)."""
        if self.mode == OutputMode.TEXT:
            console.print(f"[bold cyan]{text}[/bold cyan]")
        else:
            self._raw_console.print(text)

    def blank(self) -> None:
        """Print a blank line."""
        if self.mode == OutputMode.TEXT:
            console.print()
        else:
            self._raw_console.print()

    def state(self, name: str, state: str) -> None:
        """Print a state field with appropriate coloring."""
        if self.mode == OutputMode.TEXT:
            lower = state.lower()
            if lower in SUCCESS_STATES:
                style = "green"
            elif lower in ERROR_STATES:
                style = "red"
            elif lower in WARNING_STATES:
                style = "yellow"
            elif lower in TERMINAL_STATES:
                style = "bold"
            else:
                style = "cyan"
            console.print(f"[bold]{name}:[/bold] [{style}]{state}[/{style}]")
        else:
            self._raw_console.print(f"{name}: {state}")

    def success(self, text: str) -> None:
        """Print a success message."""
        self._print(text, "green")

    def error(self, text: str) -> None:
        """Print an error message."""
        self._print(text, "red bold")

    def warning(self, text: str) -> None:
        """Print a warning message."""
        self._print(text, "yellow")

    def dim(self, text: str) -> None:
        """Print dimmed/muted text."""
        self._print(text, "dim")

    def json(self, data: Any) -> None:
        """Print JSON data."""
        json_str = json_module.dumps(data, indent=2, default=str)
        self._raw_console.print(json_str)

    def markdown(self, text: str) -> None:
        """Print markdown content."""
        if self.mode == OutputMode.TEXT:
            console.print(Markdown(text))
        else:
            self._raw_console.print(text)

    def list_item(self, text: str, bullet: str = "•") -> None:
        """Print a list item with bullet."""
        if self.mode == OutputMode.TEXT:
            console.print(f"  [dim]{bullet}[/dim] {text}")
        else:
            self._raw_console.print(f"  {bullet} {_strip_markup(text)}")


_current_context: Output | None = None


@contextmanager
def get_output_context(
    mode: OutputMode | str,
) -> Generator[Output, None, None]:
    global _current_context

    if isinstance(mode, str):
        mode = OutputMode(mode)

    context = Output(mode)
    _current_context = context
    try:
        yield context
    finally:
        _current_context = None
