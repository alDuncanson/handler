"""Contact panel component for managing agent connections."""

from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.events import Enter, Leave
from textual.widgets import Button, Input, Link, Static, TabbedContent, TabPane, Tabs

from a2a_handler.common import get_logger

logger = get_logger(__name__)

REPORT_BUG_URL = "https://github.com/alDuncanson/Handler/issues"
SPONSOR_URL = "https://github.com/sponsors/alDuncanson"
DISCUSS_URL = "https://github.com/alDuncanson/Handler/discussions"


class UrlRow(Horizontal):
    """URL input row that shows button on hover or when input is focused."""

    def on_enter(self, event: Enter) -> None:
        self.query_one("#connect-btn", Button).display = True

    def on_leave(self, event: Leave) -> None:
        if not self.query_one("#agent-url", Input).has_focus:
            self.query_one("#connect-btn", Button).display = False

    def on_descendant_focus(self) -> None:
        self.query_one("#connect-btn", Button).display = True

    def on_descendant_blur(self) -> None:
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
        Binding("b", "open_bug_report", "Report Bug", show=False),
        Binding("s", "open_sponsor", "Sponsor", show=False),
        Binding("d", "open_discuss", "Discuss", show=False),
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
                        Button("CONNECT", id="connect-btn"),
                        id="url-row",
                    ),
                    id="server-content",
                )
            with TabPane("Help", id="help-tab"):
                yield Vertical(
                    Static(id="version-info"),
                    Static("[dim]b[/dim] Report a bug:", classes="link-label"),
                    Link(REPORT_BUG_URL, url=REPORT_BUG_URL, id="report-bug-link"),
                    Static("[dim]s[/dim] Sponsor or donate:", classes="link-label"),
                    Link(SPONSOR_URL, url=SPONSOR_URL, id="sponsor-link"),
                    Static("[dim]d[/dim] Start a discussion:", classes="link-label"),
                    Link(DISCUSS_URL, url=DISCUSS_URL, id="discuss-link"),
                    id="help-content",
                )

    def on_mount(self) -> None:
        for widget in self.query("TabbedContent, Tabs, Tab, TabPane"):
            widget.can_focus = False
        self.query_one("#agent-url", Input).can_focus = False
        btn = self.query_one("#connect-btn", Button)
        btn.can_focus = False
        btn.display = False
        for link in self.query(Link):
            link.can_focus = False
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

    def _is_help_tab_active(self) -> bool:
        """Check if the Help tab is currently active."""
        try:
            tabs = self.query_one("#contact-tabs", TabbedContent)
            return tabs.active == "help-tab"
        except Exception:
            return False

    def action_open_bug_report(self) -> None:
        """Open the bug report URL."""
        if not self._is_help_tab_active():
            return
        import webbrowser

        webbrowser.open(REPORT_BUG_URL)

    def action_open_sponsor(self) -> None:
        """Open the sponsor URL."""
        if not self._is_help_tab_active():
            return
        import webbrowser

        webbrowser.open(SPONSOR_URL)

    def action_open_discuss(self) -> None:
        """Open the discuss URL."""
        if not self._is_help_tab_active():
            return
        import webbrowser

        webbrowser.open(DISCUSS_URL)

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
