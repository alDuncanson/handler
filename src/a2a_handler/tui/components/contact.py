"""Contact panel component for managing agent connections."""

from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.events import Enter, Leave
from textual.widgets import Button, Input, Static, TabbedContent, TabPane, Tabs

from a2a_handler.common import get_logger

logger = get_logger(__name__)

ISSUES_URL = "https://github.com/alDuncanson/handler/issues"


class UrlRow(Horizontal):
    """URL input row that shows button on hover."""

    def on_enter(self, event: Enter) -> None:
        self.query_one("#connect-btn", Button).display = True

    def on_leave(self, event: Leave) -> None:
        self.query_one("#connect-btn", Button).display = False


class ContactPanel(Container):
    """Contact panel for connecting to an agent endpoint."""

    ALLOW_MAXIMIZE = False

    BINDINGS = [
        Binding("h", "previous_tab", "Previous Tab", show=False),
        Binding("l", "next_tab", "Next Tab", show=False),
        Binding("left", "previous_tab", "Previous Tab", show=False),
        Binding("right", "next_tab", "Next Tab", show=False),
        Binding("enter", "focus_input", "Focus Input", show=False),
    ]

    can_focus = True

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._version: str = "0.0.0"

    def compose(self) -> ComposeResult:
        with TabbedContent(id="contact-tabs"):
            with TabPane("Server", id="server-tab"):
                yield Vertical(
                    UrlRow(
                        Input(
                            placeholder="http://localhost:8000",
                            value="http://localhost:8000",
                            id="agent-url",
                        ),
                        Button("SEND", id="connect-btn"),
                        id="url-row",
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
        self.query_one("#agent-url", Input).can_focus = False
        btn = self.query_one("#connect-btn", Button)
        btn.can_focus = False
        btn.display = False
        self._update_version_display()
        logger.debug("Contact panel mounted")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle enter key in the URL input to connect."""
        connect_btn = self.query_one("#connect-btn", Button)
        self.post_message(Button.Pressed(connect_btn))

    def action_focus_input(self) -> None:
        """Focus the URL input field."""
        url_input = self.query_one("#agent-url", Input)
        url_input.can_focus = True
        url_input.focus()

    def on_descendant_blur(self) -> None:
        """Disable focus on input when it loses focus."""
        url_input = self.query_one("#agent-url", Input)
        url_input.can_focus = False

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
            version_widget.update(f"Handler v{self._version}")
        except Exception:
            pass

    def get_url(self) -> str:
        """Get the current agent URL from the input field."""
        url_input = self.query_one("#agent-url", Input)
        return url_input.value.strip()
