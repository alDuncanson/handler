import json
import logging
import re
from typing import Any

from a2a.types import AgentCard
from rich.syntax import Syntax
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.widgets import Static, TabbedContent, TabPane, Tabs

logger = logging.getLogger(__name__)

TEXTUAL_TO_SYNTAX_THEME: dict[str, str] = {
    "gruvbox": "gruvbox-dark",
    "nord": "nord",
    "tokyo-night": "monokai",
    "textual-dark": "monokai",
    "textual-light": "default",
    "solarized-light": "solarized-light",
    "dracula": "dracula",
    "catppuccin-mocha": "monokai",
    "monokai": "monokai",
}


class AgentCardPanel(Container):
    """Panel displaying agent card information with tabs."""

    BINDINGS = [
        Binding("h", "prev_tab", "Prev Tab", show=False),
        Binding("l", "next_tab", "Next Tab", show=False),
        Binding("left", "prev_tab", "Prev Tab", show=False),
        Binding("right", "next_tab", "Next Tab", show=False),
        Binding("j", "scroll_down", "Scroll Down", show=False),
        Binding("k", "scroll_up", "Scroll Up", show=False),
        Binding("down", "scroll_down", "Scroll Down", show=False),
        Binding("up", "scroll_up", "Scroll Up", show=False),
    ]

    can_focus = True

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._agent_card: AgentCard | None = None

    def compose(self) -> ComposeResult:
        with TabbedContent(id="agent-card-tabs"):
            with TabPane("Short", id="short-tab"):
                yield VerticalScroll(
                    Static("Not connected", id="agent-short"),
                    id="short-scroll",
                )
            with TabPane("Long", id="long-tab"):
                yield VerticalScroll(
                    Static("", id="agent-long"),
                    id="long-scroll",
                )
            with TabPane("Raw", id="raw-tab"):
                yield VerticalScroll(
                    Static("", id="agent-raw"),
                    id="raw-scroll",
                )

    def on_mount(self) -> None:
        self.border_title = "AGENT CARD"
        self.border_subtitle = "READY"

    def _get_syntax_theme(self) -> str:
        """Get the Rich Syntax theme name for the current app theme."""
        return TEXTUAL_TO_SYNTAX_THEME.get(self.app.theme or "", "monokai")

    def _format_key(self, key: str) -> str:
        """Convert a key to sentence case."""
        spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", key)
        return spaced.replace("_", " ").capitalize()

    def _is_empty(self, value: Any) -> bool:
        """Check if a value is truly empty, including nested structures."""
        if value is None:
            return True
        if isinstance(value, (str, list, dict)) and not value:
            return True
        if isinstance(value, dict):
            return all(self._is_empty(v) for v in value.values())
        if isinstance(value, list):
            return all(self._is_empty(v) for v in value)
        return False

    def _format_value(self, value: Any, indent: int = 0) -> str:
        """Format a nested value for display."""
        prefix = "  " * indent
        if isinstance(value, dict):
            lines = []
            for k, v in value.items():
                if self._is_empty(v):
                    continue
                formatted_key = self._format_key(k)
                if isinstance(v, (list, dict)):
                    lines.append(f"{prefix}[bold]{formatted_key}[/]")
                    lines.append(self._format_value(v, indent + 1))
                else:
                    lines.append(f"{prefix}[bold]{formatted_key}:[/] {v}")
            return "\n".join(lines)
        if isinstance(value, list):
            lines = []
            for item in value:
                if self._is_empty(item):
                    continue
                if isinstance(item, dict):
                    lines.append(self._format_value(item, indent))
                else:
                    lines.append(f"{prefix}• {item}")
            return "\n".join(lines)
        return f"{prefix}{value}"

    def _build_short_view(self, card: AgentCard) -> str:
        """Build the short view with essential fields only."""
        card_dict = card.model_dump()
        lines = []

        short_fields = [
            "name",
            "description",
            "version",
            "url",
            "defaultInputModes",
            "defaultOutputModes",
        ]

        for key in short_fields:
            value = card_dict.get(key)
            if self._is_empty(value):
                continue
            formatted_key = self._format_key(key)
            if isinstance(value, (list, dict)):
                lines.append(f"[bold]{formatted_key}[/]")
                lines.append(self._format_value(value, indent=1))
            else:
                lines.append(f"[bold]{formatted_key}:[/] {value}")

        return "\n".join(lines)

    def _build_long_view(self, card: AgentCard) -> str:
        """Build the long view with all non-empty fields."""
        card_dict = card.model_dump()
        lines = []

        for key, value in card_dict.items():
            if self._is_empty(value):
                continue
            formatted_key = self._format_key(key)
            if isinstance(value, (list, dict)):
                lines.append(f"[bold]{formatted_key}[/]")
                lines.append(self._format_value(value, indent=1))
            else:
                lines.append(f"[bold]{formatted_key}:[/] {value}")

        return "\n".join(lines)

    def update_card(self, card: AgentCard | None) -> None:
        """Update the displayed agent card."""
        self._agent_card = card

        if card is None:
            self.query_one("#agent-short", Static).update("Not connected")
            self.query_one("#agent-long", Static).update("")
            self.query_one("#agent-raw", Static).update("")
            self.border_subtitle = "READY"
        else:
            self.query_one("#agent-short", Static).update(self._build_short_view(card))
            self.query_one("#agent-long", Static).update(self._build_long_view(card))

            json_str = json.dumps(card.model_dump(), indent=2, default=str)
            self.query_one("#agent-raw", Static).update(
                Syntax(json_str, "json", theme=self._get_syntax_theme())
            )
            self.border_subtitle = "ACTIVE"

    def refresh_theme(self) -> None:
        """Refresh the raw view syntax highlighting for theme changes."""
        if self._agent_card is None:
            return
        json_str = json.dumps(self._agent_card.model_dump(), indent=2, default=str)
        self.query_one("#agent-raw", Static).update(
            Syntax(json_str, "json", theme=self._get_syntax_theme())
        )

    def _get_active_scroll(self) -> VerticalScroll | None:
        """Get the currently visible scroll container."""
        tabs = self.query_one("#agent-card-tabs", TabbedContent)
        active_tab = tabs.active

        if active_tab == "short-tab":
            return self.query_one("#short-scroll", VerticalScroll)
        elif active_tab == "long-tab":
            return self.query_one("#long-scroll", VerticalScroll)
        elif active_tab == "raw-tab":
            return self.query_one("#raw-scroll", VerticalScroll)
        return None

    def action_prev_tab(self) -> None:
        """Switch to the previous tab."""
        try:
            tabs = self.query_one("#agent-card-tabs Tabs", Tabs)
            tabs.action_previous_tab()
        except Exception:
            pass

    def action_next_tab(self) -> None:
        """Switch to the next tab."""
        try:
            tabs = self.query_one("#agent-card-tabs Tabs", Tabs)
            tabs.action_next_tab()
        except Exception:
            pass

    def action_scroll_down(self) -> None:
        """Scroll down in the active tab's scroll container."""
        scroll = self._get_active_scroll()
        if scroll:
            scroll.scroll_down()

    def action_scroll_up(self) -> None:
        """Scroll up in the active tab's scroll container."""
        scroll = self._get_active_scroll()
        if scroll:
            scroll.scroll_up()
