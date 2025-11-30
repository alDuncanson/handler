import logging

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Button, Input, Label

logger = logging.getLogger(__name__)


class ContactPanel(Container):
    """Contact panel for connecting to an agent endpoint."""

    def compose(self) -> ComposeResult:
        yield Label("ENDPOINT", classes="section-label")
        yield Input(
            placeholder="http://localhost:8000",
            value="http://localhost:8000",
            id="agent-url",
        )
        with Horizontal(classes="contact-buttons"):
            yield Button("CONNECT", id="connect-btn")
            yield Button("DISCONNECT", id="disconnect-btn", disabled=True)

    def on_mount(self) -> None:
        self.border_title = "CONTACT"

    def set_connected(self, connected: bool) -> None:
        """Update button states based on connection status."""
        self.query_one("#connect-btn", Button).disabled = connected
        self.query_one("#disconnect-btn", Button).disabled = not connected

    def get_url(self) -> str:
        """Get the current agent URL."""
        return self.query_one("#agent-url", Input).value.strip()
