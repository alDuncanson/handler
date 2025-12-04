import logging
import uuid
from typing import Any

import httpx
from a2a.types import AgentCard
from handler_client import (
    build_http_client,
    fetch_agent_card,
    send_message_to_agent,
)
from handler_common import __version__
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.logging import TextualHandler
from textual.widgets import Button, Input

from a2a_handler.components import (
    AgentCardPanel,
    ContactPanel,
    Footer,
    InputPanel,
    MessagesPanel,
)

logging.basicConfig(
    level="NOTSET",
    handlers=[TextualHandler()],
)
logger = logging.getLogger(__name__)


class HandlerTUI(App[Any]):
    """Handler - A2A Agent Management Interface."""

    CSS_PATH = "tui.tcss"

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("ctrl+c", "clear_chat", "Clear", show=True),
        Binding("ctrl+p", "command_palette", "Palette", show=True),
    ]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.agent_card: AgentCard | None = None
        self.http_client: httpx.AsyncClient | None = None
        self.context_id: str | None = None
        self.agent_url: str | None = None

    def compose(self) -> ComposeResult:
        with Container(id="root-container"):
            with Vertical(id="left-pane"):
                yield ContactPanel(id="contact-container", classes="panel")
                yield AgentCardPanel(id="agent-card-container", classes="panel")

            with Vertical(id="right-pane"):
                yield MessagesPanel(id="messages-container", classes="panel")
                yield InputPanel(id="input-container", classes="panel")

        yield Footer(id="footer")

    async def on_mount(self) -> None:
        logger.info("TUI application starting")
        self.http_client = build_http_client()
        self.theme = "gruvbox"

        root = self.query_one("#root-container", Container)
        root.border_title = f"Handler v{__version__} [red]●[/red] Disconnected"

        messages = self.query_one("#messages-container", MessagesPanel)
        messages.add_system_message("Welcome! Connect to an agent to start chatting.")

    def watch_theme(self, theme: str) -> None:
        """Called when the app theme changes."""
        logger.debug("Theme changed to: %s", theme)
        self.query_one("#agent-card-container", AgentCardPanel).refresh_theme()

    @on(Button.Pressed, "#footer-quit")
    async def action_quit_app(self) -> None:
        await self.action_quit()

    @on(Button.Pressed, "#footer-clear")
    async def action_clear_chat_footer(self) -> None:
        await self.action_clear_chat()

    @on(Button.Pressed, "#footer-palette")
    def action_open_command_palette(self) -> None:
        self.action_command_palette()

    async def _connect(self, agent_url: str) -> AgentCard:
        if not self.http_client:
            raise RuntimeError("HTTP client not initialized")

        logger.info("Connecting to agent at %s", agent_url)
        return await fetch_agent_card(agent_url, self.http_client)

    def _update_ui_connected(self, card: AgentCard) -> None:
        root = self.query_one("#root-container", Container)
        root.border_title = (
            f"Handler v{__version__} [green]●[/green] Connected: {card.name}"
        )

        self.query_one("#agent-card-container", AgentCardPanel).update_card(card)
        self.query_one("#contact-container", ContactPanel).set_connected(True)
        self.query_one("#messages-container", MessagesPanel).update_message_count()

    def _update_ui_disconnected(self) -> None:
        root = self.query_one("#root-container", Container)
        root.border_title = f"Handler v{__version__} [red]●[/red] Disconnected"

        self.query_one("#agent-card-container", AgentCardPanel).update_card(None)
        self.query_one("#contact-container", ContactPanel).set_connected(False)

    @on(Button.Pressed, "#connect-btn")
    async def connect_to_agent(self) -> None:
        contact = self.query_one("#contact-container", ContactPanel)
        agent_url = contact.get_url()

        if not agent_url:
            logger.warning("Connect attempted with empty URL")
            messages = self.query_one("#messages-container", MessagesPanel)
            messages.add_system_message("✗ Please enter an agent URL")
            return

        messages = self.query_one("#messages-container", MessagesPanel)
        messages.add_system_message(f"Connecting to {agent_url}...")

        try:
            card = await self._connect(agent_url)

            self.agent_card = card
            self.agent_url = agent_url
            self.context_id = str(uuid.uuid4())

            logger.info("Successfully connected to %s", card.name)

            self._update_ui_connected(card)
            messages.add_system_message(f"✓ Connected to {card.name}")
            self.query_one("#agent-card-container", AgentCardPanel).focus()

        except Exception as e:
            logger.error("Connection failed: %s", e, exc_info=True)
            messages.add_system_message(f"✗ Connection failed: {str(e)}")

    @on(Button.Pressed, "#disconnect-btn")
    def disconnect_from_agent(self) -> None:
        logger.info("Disconnecting from %s", self.agent_url)
        self.agent_card = None
        self.agent_url = None

        messages = self.query_one("#messages-container", MessagesPanel)
        messages.add_system_message("Disconnected")

        self._update_ui_disconnected()

    @on(Input.Submitted, "#message-input")
    async def send_on_enter(self) -> None:
        if self.agent_url:
            await self._send_message()
        else:
            messages = self.query_one("#messages-container", MessagesPanel)
            messages.add_system_message("✗ Not connected to an agent")

    @on(Button.Pressed, "#send-btn")
    async def send_button_pressed(self) -> None:
        if self.agent_url:
            await self._send_message()
        else:
            messages = self.query_one("#messages-container", MessagesPanel)
            messages.add_system_message("✗ Not connected to an agent")

    async def _handle_agent_response(self, response_data: dict[str, Any]) -> str:
        if not response_data:
            return "Error: No result in response"

        texts = []
        if "parts" in response_data:
            texts.extend(p.get("text", "") for p in response_data["parts"])

        for artifact in response_data.get("artifacts", []):
            texts.extend(p.get("text", "") for p in artifact.get("parts", []))

        return "\n".join(t for t in texts if t) or "No text in response"

    async def _send_message(self) -> None:
        if not self.agent_url or not self.http_client:
            logger.warning("Attempted to send message without connection")
            messages = self.query_one("#messages-container", MessagesPanel)
            messages.add_system_message("✗ Not connected to an agent")
            return

        input_panel = self.query_one("#input-container", InputPanel)
        message_text = input_panel.get_message()

        if not message_text:
            return

        messages = self.query_one("#messages-container", MessagesPanel)
        messages.add_message("user", message_text)

        try:
            logger.info("Sending message: %s", message_text[:50])

            response_data = await send_message_to_agent(
                self.agent_url,
                message_text,
                self.http_client,
                context_id=self.context_id,
            )

            response_text = await self._handle_agent_response(response_data)
            messages.add_message("agent", response_text)

        except Exception as e:
            logger.error("Error sending message: %s", e, exc_info=True)
            messages.add_system_message(f"✗ Error: {str(e)}")

    async def action_clear_chat(self) -> None:
        messages = self.query_one("#messages-container", MessagesPanel)
        await messages.clear()

    async def on_unmount(self) -> None:
        logger.info("Shutting down TUI application")
        if self.http_client:
            await self.http_client.aclose()


def main() -> None:
    """Entry point for the TUI application."""
    app = HandlerTUI()
    app.run()


if __name__ == "__main__":
    main()
