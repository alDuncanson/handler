"""Logs panel component using Textual's built-in Log widget."""

from __future__ import annotations

from textual.widgets import Log


class LogsPanel(Log):
    """Panel for displaying application logs using Textual's Log widget.

    This is a thin wrapper around Textual's Log widget that provides
    raw, unformatted log output with auto-scroll.
    """

    can_focus = False

    def __init__(self, **kwargs) -> None:
        super().__init__(
            max_lines=1000,
            auto_scroll=True,
            **kwargs,
        )

    def scroll_left(self) -> None:
        """Scroll the log view left."""
        self.scroll_relative(x=-4)

    def scroll_right(self) -> None:
        """Scroll the log view right."""
        self.scroll_relative(x=4)

    def add_log(self, line: str) -> None:
        """Add a log line to the display."""
        self.write_line(line)
        self.scroll_end(animate=False)

    def load_logs(self, lines: list[str]) -> None:
        """Load multiple log lines at once."""
        self.write_lines(lines)
        self.scroll_end(animate=False)
