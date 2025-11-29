import json
import logging
import uuid
from datetime import datetime
from typing import Any, Optional

import httpx
from a2a.types import AgentCard
from handler_client import (
    build_http_client,
    fetch_agent_card,
    send_message_to_agent,
)
from rich.syntax import Syntax
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.logging import TextualHandler
from textual.widgets import Button, Input, Label, Static, TabbedContent, TabPane, Tabs

TEXTUAL_TO_SYNTAX_THEME: dict[str, str] = {
    "gruvbox": "gruvbox-dark",
    "nord": "nord",
    "tokyo-night": "monokai",
    "textual-dark": "monokai",
    "textual-light": "default",
    "solarized-light": "solarized-light",
    "dracula": "dracula",
    "catppuccin-mocha": "monokai",
    "monokai": "monokai",
}

logging.basicConfig(
    level="NOTSET",
    handlers=[TextualHandler()],
)
logger = logging.getLogger(__name__)


class Message(Vertical):
    """A single message in the chat."""

    def __init__(
        self,
        role: str,
        content: str,
        timestamp: datetime | None = None,
        **kwargs: Any,
    ):
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


class ChatPanel(VerticalScroll):
    """Main chat display area."""

    def on_mount(self) -> None:
        self.can_focus = False

    def check_scrollability(self) -> None:
        if self.virtual_size.height > self.size.height:
            self.can_focus = True
        else:
            self.can_focus = False

    def on_resize(self) -> None:
        self.check_scrollability()

    def add_message(self, role: str, content: str) -> None:
        logger.debug("Adding %s message: %s", role, content[:50])
        message = Message(role, content)
        self.mount(message)
        self.scroll_end(animate=False)
        self.call_after_refresh(self.check_scrollability)

    def add_system_message(self, content: str) -> None:
        logger.info("System message: %s", content)
        self.add_message("system", content)


class CustomFooter(Container):
    """Custom footer with shortcut buttons."""

    def compose(self) -> ComposeResult:
        with Horizontal(classes="footer-buttons"):
            yield Button("Ctrl+Q Quit", id="footer-quit")
            yield Button("Ctrl+C Clear", id="footer-clear")
            yield Button("Ctrl+P Palette", id="footer-palette")


class HandlerTUI(App[Any]):
    """Handler - A2A Agent Management Interface."""

    CSS_PATH = "tui.tcss"

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("ctrl+c", "clear_chat", "Clear", show=True),
        Binding("ctrl+p", "command_palette", "Palette", show=True),
        Binding("h", "prev_tab", "Prev Tab", show=False),
        Binding("l", "next_tab", "Next Tab", show=False),
        Binding("j", "scroll_down", "Scroll Down", show=False),
        Binding("k", "scroll_up", "Scroll Up", show=False),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.agent_card: Optional[AgentCard] = None
        self.http_client: Optional[httpx.AsyncClient] = None
        self.context_id: Optional[str] = None
        self.agent_url: Optional[str] = None

    def _get_syntax_theme(self) -> str:
        """Get the Rich Syntax theme name for the current app theme."""
        return TEXTUAL_TO_SYNTAX_THEME.get(self.theme or "", "monokai")

    def _refresh_agent_raw(self) -> None:
        """Refresh the raw agent card display with current syntax theme."""
        if self.agent_card is None:
            return
        agent_raw = self.query_one("#agent-raw", Static)
        json_str = json.dumps(self.agent_card.model_dump(), indent=2, default=str)
        agent_raw.update(Syntax(json_str, "json", theme=self._get_syntax_theme()))

    def watch_theme(self, theme: str) -> None:
        """Called when the app theme changes."""
        logger.debug("Theme changed to: %s", theme)
        self._refresh_agent_raw()

    def compose(self) -> ComposeResult:
        """Compose the application layout."""
        with Container(id="root-container"):
            with Vertical(id="left-pane"):
                with Container(id="contact-container", classes="panel"):
                    yield Label("ENDPOINT", classes="section-label")
                    yield Input(
                        placeholder="http://localhost:8000",
                        value="http://localhost:8000",
                        id="agent-url",
                    )
                    with Horizontal(classes="contact-buttons"):
                        yield Button("CONNECT", id="connect-btn")
                        yield Button(
                            "DISCONNECT",
                            id="disconnect-btn",
                            disabled=True,
                        )

                with Container(id="agent-card-container", classes="panel"):
                    with TabbedContent(id="agent-card-tabs"):
                        with TabPane("Pretty", id="pretty-tab"):
                            yield Static("Not connected", id="agent-info")
                        with TabPane("Raw", id="raw-tab"):
                            yield VerticalScroll(
                                Static("", id="agent-raw"), id="raw-scroll"
                            )

            with Vertical(id="right-pane"):
                with Container(id="conversation-container", classes="panel"):
                    yield ChatPanel(id="chat")

                with Container(id="input-container", classes="panel"):
                    with Horizontal(id="input-row"):
                        yield Input(
                            placeholder="Type your message...", id="message-input"
                        )
                        yield Button("SEND", id="send-btn")

        yield CustomFooter(id="footer")

    async def on_mount(self) -> None:
        """Initialize the app on mount."""
        logger.info("TUI application starting")
        self.http_client = build_http_client()
        self.theme = "gruvbox"

        root = self.query_one("#root-container", Container)
        root.border_title = "Handler 0.1.0 [red]●[/red] Disconnected"

        conn = self.query_one("#contact-container", Container)
        conn.border_title = "CONTACT"

        card = self.query_one("#agent-card-container", Container)
        card.border_title = "AGENT CARD"
        card.border_subtitle = "READY"

        conv = self.query_one("#conversation-container", Container)
        conv.border_title = "CONVERSATION"

        inp = self.query_one("#input-container", Container)
        inp.border_title = "INPUT"
        inp.border_subtitle = "PRESS ENTER TO SEND"

        footer = self.query_one("#footer", CustomFooter)
        footer.border_title = "COMMANDS"

        chat = self.query_one("#chat", ChatPanel)
        chat.add_system_message("Welcome! Connect to an agent to start chatting.")

    @on(Button.Pressed, "#footer-quit")
    async def action_quit_app(self) -> None:
        await self.action_quit()

    @on(Button.Pressed, "#footer-clear")
    async def action_clear_chat_footer(self) -> None:
        await self.action_clear_chat()

    @on(Button.Pressed, "#footer-palette")
    def action_open_command_palette(self) -> None:
        """Open the command palette."""
        self.action_command_palette()

    async def _connect(self, agent_url: str) -> AgentCard:
        if not self.http_client:
            raise RuntimeError("HTTP client not initialized")

        logger.info("Connecting to agent at %s", agent_url)
        return await fetch_agent_card(agent_url, self.http_client)

    def _update_ui_connected(self, card: AgentCard) -> None:
        """Update UI to reflect connected state."""
        root = self.query_one("#root-container", Container)
        root.border_title = f"Handler 0.1.0 [green]●[/green] Connected: {card.name}"

        info_text = f"[bold visible]{card.name.upper()}[/]\n"
        info_text += f"[dim]{card.description}[/]\n\n"

        info_text += "[bold]CAPABILITIES[/]\n"
        if card.skills:
            for skill in card.skills[:4]:
                info_text += f"• {skill.name}\n"
        else:
            info_text += "• None listed\n"

        agent_info = self.query_one("#agent-info", Static)
        agent_info.update(info_text)

        agent_raw = self.query_one("#agent-raw", Static)
        json_str = json.dumps(card.model_dump(), indent=2, default=str)
        agent_raw.update(Syntax(json_str, "json", theme=self._get_syntax_theme()))

        self.query_one("#agent-card-container", Container).border_subtitle = "ACTIVE"
        self.query_one(
            "#conversation-container", Container
        ).border_subtitle = f"{len(self.query_one('#chat').children)} MESSAGES"

        self.query_one("#connect-btn", Button).disabled = True
        self.query_one("#disconnect-btn", Button).disabled = False

    def _update_ui_disconnected(self) -> None:
        """Update UI to reflect disconnected state."""
        root = self.query_one("#root-container", Container)
        root.border_title = "Handler 0.1.0 [red]●[/red] Disconnected"

        agent_info = self.query_one("#agent-info", Static)
        agent_info.update("Not connected")

        agent_raw = self.query_one("#agent-raw", Static)
        agent_raw.update("")

        self.query_one("#agent-card-container", Container).border_subtitle = "READY"

        self.query_one("#connect-btn", Button).disabled = False
        self.query_one("#disconnect-btn", Button).disabled = True

    @on(Button.Pressed, "#connect-btn")
    async def connect_to_agent(self) -> None:
        """Handle the connect button press event."""
        url_input = self.query_one("#agent-url", Input)
        agent_url = url_input.value.strip()

        if not agent_url:
            logger.warning("Connect attempted with empty URL")
            chat = self.query_one("#chat", ChatPanel)
            chat.add_system_message("✗ Please enter an agent URL")
            return

        chat = self.query_one("#chat", ChatPanel)
        chat.add_system_message(f"Connecting to {agent_url}...")

        try:
            card = await self._connect(agent_url)

            self.agent_card = card
            self.agent_url = agent_url
            self.context_id = str(uuid.uuid4())

            logger.info("Successfully connected to %s", card.name)

            self._update_ui_connected(card)
            chat.add_system_message(f"✓ Connected to {card.name}")

        except Exception as e:
            logger.error("Connection failed: %s", e, exc_info=True)
            chat.add_system_message(f"✗ Connection failed: {str(e)}")

    @on(Button.Pressed, "#disconnect-btn")
    def disconnect_from_agent(self) -> None:
        """Handle the disconnect button press event."""
        logger.info("Disconnecting from %s", self.agent_url)
        self.agent_card = None
        self.agent_url = None

        chat = self.query_one("#chat", ChatPanel)
        chat.add_system_message("Disconnected")

        self._update_ui_disconnected()

    @on(Input.Submitted, "#message-input")
    async def send_on_enter(self) -> None:
        """Handle the Enter key press in message input."""
        if self.agent_url:
            await self._send_message()
        else:
            chat = self.query_one("#chat", ChatPanel)
            chat.add_system_message("✗ Not connected to an agent")

    @on(Button.Pressed, "#send-btn")
    async def send_button_pressed(self) -> None:
        """Handle the send button press."""
        if self.agent_url:
            await self._send_message()
        else:
            chat = self.query_one("#chat", ChatPanel)
            chat.add_system_message("✗ Not connected to an agent")

    async def _handle_agent_response(self, response_data: dict[str, Any]) -> str:
        """Handle and format the agent's response.

        Args:
            response_data: The response data from the agent

        Returns:
            Formatted response text
        """
        if not response_data:
            return "Error: No result in response"

        texts = []
        if "parts" in response_data:
            texts.extend(p.get("text", "") for p in response_data["parts"])

        for artifact in response_data.get("artifacts", []):
            texts.extend(p.get("text", "") for p in artifact.get("parts", []))

        return "\n".join(t for t in texts if t) or "No text in response"

    async def _send_message(self) -> None:
        """Internal method to send a message to the agent."""
        if not self.agent_url or not self.http_client:
            logger.warning("Attempted to send message without connection")
            chat = self.query_one("#chat", ChatPanel)
            chat.add_system_message("✗ Not connected to an agent")
            return

        message_input = self.query_one("#message-input", Input)
        message_text = message_input.value.strip()

        if not message_text:
            return

        message_input.value = ""

        chat = self.query_one("#chat", ChatPanel)
        chat.add_message("user", message_text)

        try:
            logger.info("Sending message: %s", message_text[:50])

            response_data = await send_message_to_agent(
                self.agent_url,
                message_text,
                self.http_client,
                context_id=self.context_id,
            )

            response_text = await self._handle_agent_response(response_data)
            chat.add_message("agent", response_text)

        except Exception as e:
            logger.error("Error sending message: %s", e, exc_info=True)
            chat.add_system_message(f"✗ Error: {str(e)}")

    async def action_clear_chat(self) -> None:
        """Clear the chat history."""
        logger.info("Clearing chat")
        chat = self.query_one("#chat", ChatPanel)
        await chat.remove_children()
        chat.add_system_message("Chat cleared")

    def action_prev_tab(self) -> None:
        """Switch to the previous tab in TabbedContent."""
        try:
            tabs = self.query_one("#agent-card-tabs Tabs", Tabs)
            tabs.action_previous_tab()
        except Exception:
            pass

    def action_next_tab(self) -> None:
        """Switch to the next tab in TabbedContent."""
        try:
            tabs = self.query_one("#agent-card-tabs Tabs", Tabs)
            tabs.action_next_tab()
        except Exception:
            pass

    def action_scroll_down(self) -> None:
        """Scroll down in the focused scrollable area."""
        focused = self.focused
        if focused is None:
            return
        for widget in [focused, *focused.ancestors]:
            if isinstance(widget, VerticalScroll):
                widget.scroll_down()
                return

    def action_scroll_up(self) -> None:
        """Scroll up in the focused scrollable area."""
        focused = self.focused
        if focused is None:
            return
        for widget in [focused, *focused.ancestors]:
            if isinstance(widget, VerticalScroll):
                widget.scroll_up()
                return

    async def on_unmount(self) -> None:
        """Cleanup when app closes."""
        logger.info("Shutting down TUI application")
        if self.http_client:
            await self.http_client.aclose()


def main() -> None:
    """Entry point for the TUI application."""
    app = HandlerTUI()
    app.run()


if __name__ == "__main__":
    main()
