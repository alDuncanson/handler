"""Messages panel component for displaying chat history."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.widgets import Static, TabbedContent, TabPane, Tabs

from a2a_handler.common import get_logger
from a2a_handler.tui.components.auth import AuthPanel
from a2a_handler.tui.components.logs import LogsPanel

if TYPE_CHECKING:
    from a2a_handler.auth import AuthCredentials
    from a2a_handler.service import SendResult

logger = get_logger(__name__)


class Message(Static):
    """A single message in the chat."""

    def __init__(
        self,
        role: str,
        content: str,
        timestamp: datetime | None = None,
        **kwargs: Any,
    ) -> None:
        formatted_time = (timestamp or datetime.now()).strftime("%H:%M:%S")
        super().__init__(f"{formatted_time} {content}", **kwargs)
        self.add_class(f"message-{role}")


class AgentMessage(Static):
    """An agent message with A2A protocol metadata."""

    def __init__(
        self,
        send_result: SendResult,
        timestamp: datetime | None = None,
        **kwargs: Any,
    ) -> None:
        formatted_time = (timestamp or datetime.now()).strftime("%H:%M:%S")
        content = send_result.text or "(no text in response)"
        super().__init__(f"{formatted_time} {content}", **kwargs)


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
        logger.debug("Messages panel mounted")

    def _get_chat_container(self) -> ChatScrollContainer:
        return self.query_one("#chat", ChatScrollContainer)

    def add_message(self, role: str, content: str) -> None:
        logger.debug("Adding %s message: %s", role, content[:50])
        chat_container = self._get_chat_container()
        message_widget = Message(role, content)
        chat_container.mount(message_widget)
        chat_container.scroll_end(animate=False)

    def add_agent_message(self, send_result: SendResult) -> None:
        logger.debug(
            "Adding agent message - task_id=%s, state=%s, text_len=%d",
            send_result.task_id,
            send_result.state,
            len(send_result.text) if send_result.text else 0,
        )
        chat_container = self._get_chat_container()
        message_widget = AgentMessage(send_result)
        chat_container.mount(message_widget)
        chat_container.scroll_end(animate=False)

    def add_system_message(self, content: str) -> None:
        logger.info("System message: %s", content)
        self.add_message("system", content)

    def update_message_count(self) -> None:
        pass

    async def clear(self) -> None:
        logger.info("Clearing chat messages")
        chat_container = self._get_chat_container()
        await chat_container.remove_children()
        self.add_system_message("Chat cleared")

    def action_scroll_down(self) -> None:
        self._get_chat_container().scroll_down()

    def action_scroll_up(self) -> None:
        self._get_chat_container().scroll_up()


class TabbedMessagesPanel(Container):
    """Panel with tabs for Messages and Logs."""

    BINDINGS = [
        Binding("h", "previous_tab", "← Tab", show=True, key_display="h/←"),
        Binding("l", "next_tab", "→ Tab", show=True, key_display="l/→"),
        Binding("left", "previous_tab", "Previous Tab", show=False),
        Binding("right", "next_tab", "Next Tab", show=False),
        Binding("j", "scroll_down", "↓ Scroll", show=True, key_display="j/↓"),
        Binding("k", "scroll_up", "↑ Scroll", show=True, key_display="k/↑"),
        Binding("down", "scroll_down", "Scroll Down", show=False),
        Binding("up", "scroll_up", "Scroll Up", show=False),
        Binding("ctrl+h", "scroll_left", "← Scroll", show=True),
        Binding("ctrl+l", "scroll_right", "→ Scroll", show=True),
        Binding("ctrl+left", "scroll_left", "Scroll Left", show=False),
        Binding("ctrl+right", "scroll_right", "Scroll Right", show=False),
        Binding("ctrl+d", "scroll_half_down", "½ Page ↓", show=True),
        Binding("ctrl+u", "scroll_half_up", "½ Page ↑", show=True),
    ]

    can_focus = True

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Show/hide actions based on active tab context."""
        active = self._get_active_tab_id()
        if action in ("scroll_down", "scroll_up", "scroll_half_down", "scroll_half_up"):
            return active in ("messages-tab", "logs-tab")
        if action in ("scroll_left", "scroll_right"):
            return active == "logs-tab"
        return True

    def compose(self) -> ComposeResult:
        with TabbedContent(id="messages-tabs"):
            with TabPane("Messages", id="messages-tab"):
                yield ChatScrollContainer(id="chat")
            with TabPane("Auth", id="auth-tab"):
                yield AuthPanel(id="auth-panel")
            with TabPane("Logs", id="logs-tab"):
                yield LogsPanel(id="logs-panel")

    def on_mount(self) -> None:
        for widget in self.query("TabbedContent, Tabs, Tab, TabPane"):
            widget.can_focus = False
        logger.debug("Tabbed messages panel mounted")

    @on(TabbedContent.TabActivated)
    def _on_tab_activated(self) -> None:
        """Refresh bindings when switching tabs."""
        self.refresh_bindings()

    def _get_chat_container(self) -> ChatScrollContainer:
        return self.query_one("#chat", ChatScrollContainer)

    def _get_logs_panel(self) -> LogsPanel:
        return self.query_one("#logs-panel", LogsPanel)

    def _get_auth_panel(self) -> AuthPanel:
        return self.query_one("#auth-panel", AuthPanel)

    def add_message(self, role: str, content: str) -> None:
        logger.debug("Adding %s message: %s", role, content[:50])
        chat_container = self._get_chat_container()
        message_widget = Message(role, content)
        chat_container.mount(message_widget)
        chat_container.scroll_end(animate=False)

    def add_agent_message(self, send_result: SendResult) -> None:
        logger.debug(
            "Adding agent message - task_id=%s, state=%s, text_len=%d",
            send_result.task_id,
            send_result.state,
            len(send_result.text) if send_result.text else 0,
        )
        chat_container = self._get_chat_container()
        message_widget = AgentMessage(send_result)
        chat_container.mount(message_widget)
        chat_container.scroll_end(animate=False)

    def add_system_message(self, content: str) -> None:
        logger.info("System message: %s", content)
        self.add_message("system", content)

    def add_log(self, line: str) -> None:
        """Add a log line to the logs panel."""
        logs_panel = self._get_logs_panel()
        logs_panel.add_log(line)

    def load_logs(self, lines: list[str]) -> None:
        """Load multiple log lines at once."""
        logs_panel = self._get_logs_panel()
        logs_panel.load_logs(lines)

    def update_message_count(self) -> None:
        pass

    async def clear(self) -> None:
        logger.info("Clearing chat messages")
        chat_container = self._get_chat_container()
        await chat_container.remove_children()
        self.add_system_message("Chat cleared")

    async def clear_logs(self) -> None:
        """Clear the logs panel."""
        logs_panel = self._get_logs_panel()
        logs_panel.clear()

    def get_auth_credentials(self) -> "AuthCredentials | None":
        """Get configured authentication credentials from the auth panel."""
        auth_panel = self._get_auth_panel()
        return auth_panel.get_credentials()

    def _get_active_tab_id(self) -> str:
        tabbed_content = self.query_one("#messages-tabs", TabbedContent)
        return tabbed_content.active

    def action_previous_tab(self) -> None:
        """Switch to the previous tab."""
        try:
            tabs_widget = self.query_one("#messages-tabs Tabs", Tabs)
            tabs_widget.action_previous_tab()
        except Exception:
            pass

    def action_next_tab(self) -> None:
        """Switch to the next tab."""
        try:
            tabs_widget = self.query_one("#messages-tabs Tabs", Tabs)
            tabs_widget.action_next_tab()
        except Exception:
            pass

    def action_scroll_down(self) -> None:
        active = self._get_active_tab_id()
        if active == "messages-tab":
            self._get_chat_container().scroll_down()
        elif active == "logs-tab":
            self._get_logs_panel().scroll_down()

    def action_scroll_up(self) -> None:
        active = self._get_active_tab_id()
        if active == "messages-tab":
            self._get_chat_container().scroll_up()
        elif active == "logs-tab":
            self._get_logs_panel().scroll_up()

    def action_scroll_left(self) -> None:
        active = self._get_active_tab_id()
        if active == "logs-tab":
            self._get_logs_panel().scroll_left()

    def action_scroll_right(self) -> None:
        active = self._get_active_tab_id()
        if active == "logs-tab":
            self._get_logs_panel().scroll_right()

    def action_scroll_half_down(self) -> None:
        active = self._get_active_tab_id()
        if active == "messages-tab":
            container = self._get_chat_container()
            container.scroll_relative(y=container.size.height // 2)
        elif active == "logs-tab":
            panel = self._get_logs_panel()
            panel.scroll_relative(y=panel.size.height // 2)

    def action_scroll_half_up(self) -> None:
        active = self._get_active_tab_id()
        if active == "messages-tab":
            container = self._get_chat_container()
            container.scroll_relative(y=-(container.size.height // 2))
        elif active == "logs-tab":
            panel = self._get_logs_panel()
            panel.scroll_relative(y=-(panel.size.height // 2))
