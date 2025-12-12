"""Agent card panel component for displaying agent metadata and capabilities."""

import json
import re
from typing import Any

from a2a.types import AgentCard
from rich.syntax import Syntax
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.widgets import Static, TabbedContent, TabPane, Tabs

from a2a_handler.common import get_logger

logger = get_logger(__name__)

TEXTUAL_TO_SYNTAX_THEME_MAP: dict[str, str] = {
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
        Binding("h", "previous_tab", "Previous Tab", show=False),
        Binding("l", "next_tab", "Next Tab", show=False),
        Binding("left", "previous_tab", "Previous Tab", show=False),
        Binding("right", "next_tab", "Next Tab", show=False),
        Binding("j", "scroll_down", "Scroll Down", show=False),
        Binding("k", "scroll_up", "Scroll Up", show=False),
        Binding("down", "scroll_down", "Scroll Down", show=False),
        Binding("up", "scroll_up", "Scroll Up", show=False),
    ]

    can_focus = True

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._current_agent_card: AgentCard | None = None

    def compose(self) -> ComposeResult:
        yield Static("Connect to an A2A server", id="placeholder")
        with TabbedContent(id="agent-card-tabs"):
            with TabPane("Pretty", id="pretty-tab"):
                yield VerticalScroll(
                    Static("", id="agent-pretty"),
                    id="pretty-scroll",
                )
            with TabPane("Raw", id="raw-tab"):
                yield VerticalScroll(
                    Static("", id="agent-raw"),
                    id="raw-scroll",
                )

    def on_mount(self) -> None:
        for widget in self.query("TabbedContent, Tabs, Tab, TabPane, VerticalScroll"):
            widget.can_focus = False
        self._show_placeholder()
        logger.debug("Agent card panel mounted")

    def _show_placeholder(self) -> None:
        """Show the hatch placeholder, hide the tabbed content."""
        placeholder = self.query_one("#placeholder", Static)
        tabbed_content = self.query_one("#agent-card-tabs", TabbedContent)
        placeholder.display = True
        tabbed_content.display = False

    def _show_tabs(self) -> None:
        """Show the tabbed content, hide the placeholder."""
        placeholder = self.query_one("#placeholder", Static)
        tabbed_content = self.query_one("#agent-card-tabs", TabbedContent)
        placeholder.display = False
        tabbed_content.display = True

    def _get_syntax_theme_for_current_app_theme(self) -> str:
        """Get the Rich Syntax theme name for the current app theme."""
        current_theme = self.app.theme or ""
        return TEXTUAL_TO_SYNTAX_THEME_MAP.get(current_theme, "monokai")

    def _convert_key_to_sentence_case(self, key: str) -> str:
        """Convert a camelCase or snake_case key to sentence case."""
        spaced_key = re.sub(r"([a-z])([A-Z])", r"\1 \2", key)
        return spaced_key.replace("_", " ").capitalize()

    def _is_value_empty(self, value: Any) -> bool:
        """Check if a value is truly empty, including nested structures."""
        if value is None:
            return True
        if isinstance(value, (str, list, dict)) and not value:
            return True
        if isinstance(value, dict):
            return all(
                self._is_value_empty(nested_value) for nested_value in value.values()
            )
        if isinstance(value, list):
            return all(self._is_value_empty(item) for item in value)
        return False

    def _format_nested_value(self, value: Any, indentation_level: int = 0) -> str:
        """Format a nested value for display with proper indentation."""
        indentation_prefix = "  " * indentation_level

        if isinstance(value, dict):
            formatted_lines = []
            for key, nested_value in value.items():
                if self._is_value_empty(nested_value):
                    continue
                formatted_key = self._convert_key_to_sentence_case(key)
                if isinstance(nested_value, (list, dict)):
                    formatted_lines.append(
                        f"{indentation_prefix}[bold]{formatted_key}[/]"
                    )
                    formatted_lines.append(
                        self._format_nested_value(nested_value, indentation_level + 1)
                    )
                else:
                    formatted_lines.append(
                        f"{indentation_prefix}[bold]{formatted_key}:[/] {nested_value}"
                    )
            return "\n".join(formatted_lines)

        if isinstance(value, list):
            formatted_lines = []
            for item in value:
                if self._is_value_empty(item):
                    continue
                if isinstance(item, dict):
                    formatted_lines.append(
                        self._format_nested_value(item, indentation_level)
                    )
                else:
                    formatted_lines.append(f"{indentation_prefix}• {item}")
            return "\n".join(formatted_lines)

        return f"{indentation_prefix}{value}"

    def _build_pretty_view_content(self, agent_card: AgentCard) -> str:
        """Build the pretty view with all non-empty fields formatted nicely."""
        card_data = agent_card.model_dump()
        formatted_lines = []

        for field_name, field_value in card_data.items():
            if self._is_value_empty(field_value):
                continue
            formatted_key = self._convert_key_to_sentence_case(field_name)
            if isinstance(field_value, (list, dict)):
                formatted_lines.append(f"[bold]{formatted_key}[/]")
                formatted_lines.append(
                    self._format_nested_value(field_value, indentation_level=1)
                )
            else:
                formatted_lines.append(f"[bold]{formatted_key}:[/] {field_value}")

        return "\n".join(formatted_lines)

    def update_card(self, agent_card: AgentCard | None) -> None:
        """Update the displayed agent card."""
        self._current_agent_card = agent_card

        pretty_view_widget = self.query_one("#agent-pretty", Static)
        raw_view_widget = self.query_one("#agent-raw", Static)

        if agent_card is None:
            logger.debug("Clearing agent card display")
            pretty_view_widget.update("")
            raw_view_widget.update("")
            self._show_placeholder()
        else:
            logger.info("Displaying agent card for: %s", agent_card.name)
            pretty_view_widget.update(self._build_pretty_view_content(agent_card))

            json_content = json.dumps(agent_card.model_dump(), indent=2, default=str)
            syntax_theme = self._get_syntax_theme_for_current_app_theme()
            raw_view_widget.update(Syntax(json_content, "json", theme=syntax_theme))
            self._show_tabs()

    def refresh_theme(self) -> None:
        """Refresh the raw view syntax highlighting for theme changes."""
        if self._current_agent_card is None:
            return

        logger.debug("Refreshing syntax theme for agent card raw view")
        json_content = json.dumps(
            self._current_agent_card.model_dump(), indent=2, default=str
        )
        syntax_theme = self._get_syntax_theme_for_current_app_theme()
        self.query_one("#agent-raw", Static).update(
            Syntax(json_content, "json", theme=syntax_theme)
        )

    def _get_currently_active_scroll_container(self) -> VerticalScroll | None:
        """Get the currently visible scroll container."""
        tabbed_content = self.query_one("#agent-card-tabs", TabbedContent)
        active_tab_id = tabbed_content.active

        scroll_container_map = {
            "pretty-tab": "#pretty-scroll",
            "raw-tab": "#raw-scroll",
        }

        scroll_container_id = scroll_container_map.get(active_tab_id)
        if scroll_container_id:
            return self.query_one(scroll_container_id, VerticalScroll)
        return None

    def action_previous_tab(self) -> None:
        """Switch to the previous tab."""
        try:
            tabs_widget = self.query_one("#agent-card-tabs Tabs", Tabs)
            tabs_widget.action_previous_tab()
        except Exception:
            pass

    def action_next_tab(self) -> None:
        """Switch to the next tab."""
        try:
            tabs_widget = self.query_one("#agent-card-tabs Tabs", Tabs)
            tabs_widget.action_next_tab()
        except Exception:
            pass

    def action_scroll_down(self) -> None:
        """Scroll down in the active tab's scroll container."""
        scroll_container = self._get_currently_active_scroll_container()
        if scroll_container:
            scroll_container.scroll_down()

    def action_scroll_up(self) -> None:
        """Scroll up in the active tab's scroll container."""
        scroll_container = self._get_currently_active_scroll_container()
        if scroll_container:
            scroll_container.scroll_up()
