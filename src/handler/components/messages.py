import logging
from datetime import datetime
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical, VerticalScroll
from textual.widgets import Static

logger = logging.getLogger(__name__)


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
        time_str = self.timestamp.strftime("%H:%M:%S")

        if self.role == "system":
            yield Static(f"[dim]{time_str}[/dim] [italic]{self.text}[/italic]")
        else:
            role_color = "#88c0d0" if self.role == "agent" else "#bf616a"
            yield Static(f"[dim]{time_str}[/dim] [{role_color}]{self.text}[/]")


class ChatScroll(VerticalScroll):
    """Scrollable chat area with localized bindings."""

    BINDINGS = [
        Binding("j", "scroll_down", "Scroll Down", show=False),
        Binding("k", "scroll_up", "Scroll Up", show=False),
        Binding("down", "scroll_down", "Scroll Down", show=False),
        Binding("up", "scroll_up", "Scroll Up", show=False),
    ]

    def on_mount(self) -> None:
        self.can_focus = False

    def check_scrollability(self) -> None:
        if self.virtual_size.height > self.size.height:
            self.can_focus = True
        else:
            self.can_focus = False

    def on_resize(self) -> None:
        self.check_scrollability()

    def action_scroll_down(self) -> None:
        self.scroll_down()

    def action_scroll_up(self) -> None:
        self.scroll_up()


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
        yield ChatScroll(id="chat")

    def on_mount(self) -> None:
        self.border_title = "MESSAGES"

    def _get_chat(self) -> ChatScroll:
        return self.query_one("#chat", ChatScroll)

    def add_message(self, role: str, content: str) -> None:
        logger.debug("Adding %s message: %s", role, content[:50])
        chat = self._get_chat()
        message = Message(role, content)
        chat.mount(message)
        chat.scroll_end(animate=False)
        chat.call_after_refresh(chat.check_scrollability)

    def add_system_message(self, content: str) -> None:
        logger.info("System message: %s", content)
        self.add_message("system", content)

    def update_message_count(self) -> None:
        chat = self._get_chat()
        self.border_subtitle = f"{len(chat.children)} MESSAGES"

    async def clear(self) -> None:
        logger.info("Clearing chat")
        chat = self._get_chat()
        await chat.remove_children()
        self.add_system_message("Chat cleared")

    def action_scroll_down(self) -> None:
        self._get_chat().scroll_down()

    def action_scroll_up(self) -> None:
        self._get_chat().scroll_up()
