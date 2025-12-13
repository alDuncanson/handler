"""Input panel component for composing and sending messages."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.events import Enter, Leave
from textual.widgets import Button, Input

from a2a_handler.common import get_logger

logger = get_logger(__name__)


class InputRow(Horizontal):
    """Input row that shows button on hover."""

    def on_enter(self, event: Enter) -> None:
        self.query_one("#send-btn", Button).display = True

    def on_leave(self, event: Leave) -> None:
        self.query_one("#send-btn", Button).display = False


class InputPanel(Container):
    """Panel for message input."""

    ALLOW_MAXIMIZE = False

    def compose(self) -> ComposeResult:
        with InputRow(id="input-row"):
            yield Input(placeholder="Type your message...", id="message-input")
            yield Button("SEND", id="send-btn")

    def on_mount(self) -> None:
        btn = self.query_one("#send-btn", Button)
        btn.can_focus = False
        btn.display = False
        logger.debug("Input panel mounted")

    def get_message(self) -> str:
        """Get and clear the current message input."""
        message_input = self.query_one("#message-input", Input)
        message_text = message_input.value.strip()
        message_input.value = ""
        return message_text

    def focus_input(self) -> None:
        """Focus the message input field."""
        self.query_one("#message-input", Input).focus()
