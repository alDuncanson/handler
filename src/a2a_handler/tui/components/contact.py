"""Contact panel component for agent connection management."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Button, Input, Label

from a2a_handler.common import get_logger

logger = get_logger(__name__)


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
        logger.debug("Contact panel mounted")

    def set_connected(self, is_connected: bool) -> None:
        """Update button states based on connection status."""
        connect_button = self.query_one("#connect-btn", Button)
        disconnect_button = self.query_one("#disconnect-btn", Button)

        connect_button.disabled = is_connected
        disconnect_button.disabled = not is_connected

        logger.debug("Connection state updated: connected=%s", is_connected)

    def get_url(self) -> str:
        """Get the current agent URL from the input field."""
        url_input = self.query_one("#agent-url", Input)
        return url_input.value.strip()
