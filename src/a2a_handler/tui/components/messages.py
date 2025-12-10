"""Messages panel component for displaying chat history."""

from datetime import datetime
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical, VerticalScroll
from textual.widgets import Static

from a2a_handler.common import get_logger

logger = get_logger(__name__)


class Message(Vertical):
    """A single message in the chat."""

    def __init__(
        self,
        role: str,
        content: str,
        timestamp: datetime | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.role = role
        self.text = content
        self.timestamp = timestamp or datetime.now()

    def compose(self) -> ComposeResult:
        formatted_time = self.timestamp.strftime("%H:%M:%S")

        if self.role == "system":
            yield Static(f"[dim]{formatted_time}[/dim] [italic]{self.text}[/italic]")
        else:
            role_color = "#88c0d0" if self.role == "agent" else "#bf616a"
            yield Static(f"[dim]{formatted_time}[/dim] [{role_color}]{self.text}[/]")


class ChatScrollContainer(VerticalScroll):
    """Scrollable chat area."""

    can_focus = False


class MessagesPanel(Container):
    """Panel for displaying chat messages."""

    BINDINGS = [
        Binding("j", "scroll_down", "Scroll Down", show=False),
        Binding("k", "scroll_up", "Scroll Up", show=False),
        Binding("down", "scroll_down", "Scroll Down", show=False),
        Binding("up", "scroll_up", "Scroll Up", show=False),
    ]

    can_focus = True

    def compose(self) -> ComposeResult:
        yield ChatScrollContainer(id="chat")

    def on_mount(self) -> None:
        self.border_title = "MESSAGES"
        logger.debug("Messages panel mounted")

    def _get_chat_container(self) -> ChatScrollContainer:
        return self.query_one("#chat", ChatScrollContainer)

    def add_message(self, role: str, content: str) -> None:
        logger.debug("Adding %s message: %s", role, content[:50])
        chat_container = self._get_chat_container()
        message_widget = Message(role, content)
        chat_container.mount(message_widget)
        chat_container.scroll_end(animate=False)

    def add_system_message(self, content: str) -> None:
        logger.info("System message: %s", content)
        self.add_message("system", content)

    def update_message_count(self) -> None:
        chat_container = self._get_chat_container()
        message_count = len(chat_container.children)
        self.border_subtitle = f"{message_count} MESSAGES"

    async def clear(self) -> None:
        logger.info("Clearing chat messages")
        chat_container = self._get_chat_container()
        await chat_container.remove_children()
        self.add_system_message("Chat cleared")

    def action_scroll_down(self) -> None:
        self._get_chat_container().scroll_down()

    def action_scroll_up(self) -> None:
        self._get_chat_container().scroll_up()
