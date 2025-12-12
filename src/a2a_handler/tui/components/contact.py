"""Contact panel component for managing agent connections."""

from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Input, Static, TabbedContent, TabPane, Tabs

from a2a_handler.common import get_logger

logger = get_logger(__name__)

ISSUES_URL = "https://github.com/alDuncanson/handler/issues"


class ContactPanel(Container):
    """Contact panel for connecting to an agent endpoint."""

    ALLOW_MAXIMIZE = False

    BINDINGS = [
        Binding("h", "previous_tab", "Previous Tab", show=False),
        Binding("l", "next_tab", "Next Tab", show=False),
        Binding("left", "previous_tab", "Previous Tab", show=False),
        Binding("right", "next_tab", "Next Tab", show=False),
    ]

    can_focus = True

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._version: str = "0.0.0"
        self._connected_agent: str | None = None

    def compose(self) -> ComposeResult:
        with TabbedContent(id="contact-tabs"):
            with TabPane("Server", id="server-tab"):
                yield Vertical(
                    Input(
                        placeholder="http://localhost:8000",
                        value="http://localhost:8000",
                        id="agent-url",
                    ),
                    Horizontal(
                        Button("CONNECT", id="connect-btn"),
                        Button("DISCONNECT", id="disconnect-btn", disabled=True),
                        classes="contact-buttons",
                    ),
                    id="server-content",
                )
            with TabPane("About", id="about-tab"):
                yield Vertical(
                    Static(id="version-info"),
                    Static(f"[@click=open_issues]{ISSUES_URL}[/]", id="issues-link"),
                    id="about-content",
                )

    def on_mount(self) -> None:
        for widget in self.query("TabbedContent, Tabs, Tab, TabPane"):
            widget.can_focus = False
        self.query_one("#connect-btn", Button).can_focus = False
        self.query_one("#disconnect-btn", Button).can_focus = False
        self._update_version_display()
        logger.debug("Contact panel mounted")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle enter key in the URL input to connect/disconnect."""
        connect_btn = self.query_one("#connect-btn", Button)
        disconnect_btn = self.query_one("#disconnect-btn", Button)

        if not connect_btn.disabled:
            self.post_message(Button.Pressed(connect_btn))
        elif not disconnect_btn.disabled:
            self.post_message(Button.Pressed(disconnect_btn))

    def action_open_issues(self) -> None:
        """Open the issues URL in the browser."""
        import webbrowser

        webbrowser.open(ISSUES_URL)

    def action_previous_tab(self) -> None:
        """Switch to the previous tab."""
        try:
            tabs_widget = self.query_one("#contact-tabs Tabs", Tabs)
            tabs_widget.action_previous_tab()
        except Exception:
            pass

    def action_next_tab(self) -> None:
        """Switch to the next tab."""
        try:
            tabs_widget = self.query_one("#contact-tabs Tabs", Tabs)
            tabs_widget.action_next_tab()
        except Exception:
            pass

    def set_version(self, version: str) -> None:
        """Set the application version."""
        self._version = version
        self._update_version_display()

    def _update_version_display(self) -> None:
        """Update the version info display."""
        try:
            version_widget = self.query_one("#version-info", Static)
            if self._connected_agent:
                version_widget.update(
                    f"Handler v{self._version} [green]●[/] {self._connected_agent}"
                )
            else:
                version_widget.update(
                    f"Handler v{self._version} [red]●[/] Disconnected"
                )
        except Exception:
            pass

    def set_connected(self, is_connected: bool, agent_name: str | None = None) -> None:
        """Update button states based on connection status."""
        connect_button = self.query_one("#connect-btn", Button)
        disconnect_button = self.query_one("#disconnect-btn", Button)

        connect_button.disabled = is_connected
        disconnect_button.disabled = not is_connected

        self._connected_agent = agent_name if is_connected else None
        self._update_version_display()

        logger.debug("Connection state updated: connected=%s", is_connected)

    def get_url(self) -> str:
        """Get the current agent URL from the input field."""
        url_input = self.query_one("#agent-url", Input)
        return url_input.value.strip()
