import logging

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Button, Input

logger = logging.getLogger(__name__)


class InputPanel(Container):
    """Panel for message input."""

    def compose(self) -> ComposeResult:
        with Horizontal(id="input-row"):
            yield Input(placeholder="Type your message...", id="message-input")
            yield Button("SEND", id="send-btn")

    def on_mount(self) -> None:
        self.border_title = "INPUT"
        self.border_subtitle = "PRESS ENTER TO SEND"

    def get_message(self) -> str:
        """Get and clear the current message input."""
        message_input = self.query_one("#message-input", Input)
        message = message_input.value.strip()
        message_input.value = ""
        return message

    def focus_input(self) -> None:
        """Focus the message input."""
        self.query_one("#message-input", Input).focus()
