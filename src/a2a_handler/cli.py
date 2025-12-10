"""Command-line interface for the Handler A2A protocol client.

Provides commands for interacting with A2A agents:
- message send/stream: Send messages to agents
- task get/cancel/resubscribe: Manage tasks
- task notification set: Configure push notifications
- card get/validate: Agent card operations
- server agent/push: Run local servers
- session list/show/clear: Manage saved sessions
"""

import asyncio
import logging
from typing import Any, Optional

logging.getLogger().setLevel(logging.WARNING)

import httpx
import rich_click as click
from a2a.client.errors import (
    A2AClientError,
    A2AClientHTTPError,
    A2AClientTimeoutError,
)
from a2a.types import AgentCard

from a2a_handler import __version__
from a2a_handler.common import (
    format_field_name,
    format_value,
    get_logger,
    get_output_context,
    setup_logging,
)
from a2a_handler.common.output import Output
from a2a_handler.server import run_server
from a2a_handler.service import A2AService, SendResult, TaskResult
from a2a_handler.session import (
    clear_session,
    get_session,
    get_session_store,
    update_session,
)
from a2a_handler.tui import HandlerTUI
from a2a_handler.validation import (
    ValidationResult,
    validate_agent_card_from_file,
    validate_agent_card_from_url,
)
from a2a_handler.webhook import run_webhook_server

# rich_click configuration
click.rich_click.USE_RICH_MARKUP = True
click.rich_click.USE_MARKDOWN = True
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
click.rich_click.STYLE_HELPTEXT = ""
click.rich_click.STYLE_OPTION = "cyan"
click.rich_click.STYLE_ARGUMENT = "cyan"
click.rich_click.STYLE_COMMAND = "green"
click.rich_click.STYLE_SWITCH = "bold green"

click.rich_click.OPTION_GROUPS = {
    "handler": [
        {"name": "Global Options", "options": ["--verbose", "--debug", "--help"]},
        {"name": "Output Options", "options": ["--raw"]},
    ],
    "handler message send": [
        {
            "name": "Message Options",
            "options": ["--stream", "--continue", "--context-id", "--task-id"],
        },
        {
            "name": "Push Notification Options",
            "options": ["--push-url", "--push-token"],
        },
        {"name": "Output Options", "options": ["--output", "--help"]},
    ],
    "handler message stream": [
        {
            "name": "Conversation Options",
            "options": ["--continue", "--context-id", "--task-id"],
        },
        {
            "name": "Push Notification Options",
            "options": ["--push-url", "--push-token"],
        },
        {"name": "Output Options", "options": ["--output", "--help"]},
    ],
    "handler task get": [
        {"name": "Query Options", "options": ["--history-length"]},
        {"name": "Output Options", "options": ["--output", "--help"]},
    ],
    "handler task notification set": [
        {"name": "Notification Options", "options": ["--url", "--token"]},
        {"name": "Output Options", "options": ["--output", "--help"]},
    ],
    "handler card get": [
        {"name": "Card Options", "options": ["--authenticated"]},
        {"name": "Output Options", "options": ["--output", "--help"]},
    ],
    "handler server agent": [
        {"name": "Server Options", "options": ["--host", "--port", "--help"]},
    ],
    "handler server push": [
        {"name": "Server Options", "options": ["--host", "--port", "--help"]},
    ],
    "handler session clear": [
        {"name": "Clear Options", "options": ["--all", "--help"]},
    ],
}

click.rich_click.COMMAND_GROUPS = {
    "handler": [
        {"name": "Agent Communication", "commands": ["message", "task"]},
        {"name": "Agent Discovery", "commands": ["card"]},
        {"name": "Interfaces", "commands": ["tui", "server"]},
        {"name": "Utilities", "commands": ["session", "version"]},
    ],
    "handler message": [
        {"name": "Message Commands", "commands": ["send", "stream"]},
    ],
    "handler task": [
        {"name": "Task Commands", "commands": ["get", "cancel", "resubscribe"]},
        {"name": "Push Notifications", "commands": ["notification"]},
    ],
    "handler task notification": [
        {"name": "Notification Commands", "commands": ["set"]},
    ],
    "handler card": [
        {"name": "Card Commands", "commands": ["get", "validate"]},
    ],
    "handler server": [
        {"name": "Server Commands", "commands": ["agent", "push"]},
    ],
    "handler session": [
        {"name": "Session Commands", "commands": ["list", "show", "clear"]},
    ],
}


TIMEOUT = 120
log = get_logger(__name__)


def build_http_client(timeout: int = TIMEOUT) -> httpx.AsyncClient:
    """Build an HTTP client with the specified timeout."""
    return httpx.AsyncClient(timeout=timeout)


def _handle_client_error(e: Exception, agent_url: str, context: object) -> None:
    """Handle A2A client errors with appropriate messages."""
    output = context if isinstance(context, Output) else None

    message = ""
    if isinstance(e, A2AClientTimeoutError):
        log.error("Request to %s timed out", agent_url)
        message = "Request timed out"
    elif isinstance(e, A2AClientHTTPError):
        log.error("A2A client error: %s", e)
        message = (
            f"Connection failed: Is the server running at {agent_url}?"
            if "connection" in str(e).lower()
            else str(e)
        )
    elif isinstance(e, A2AClientError):
        log.error("A2A client error: %s", e)
        message = str(e)
    elif isinstance(e, httpx.ConnectError):
        log.error("Connection refused to %s", agent_url)
        message = f"Connection refused: Is the server running at {agent_url}?"
    elif isinstance(e, httpx.TimeoutException):
        log.error("Request to %s timed out", agent_url)
        message = "Request timed out"
    elif isinstance(e, httpx.HTTPStatusError):
        log.error("HTTP error %d from %s", e.response.status_code, agent_url)
        message = f"HTTP {e.response.status_code} - {e.response.text}"
    else:
        log.exception("Failed request to %s", agent_url)
        message = str(e)

    if output:
        output.error(message)
    else:
        click.echo(f"Error: {message}", err=True)


# ============================================================================
# Main CLI Group
# ============================================================================


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.option("--debug", "-d", is_flag=True, help="Enable debug logging")
@click.option("--raw", "-r", is_flag=True, help="Output raw text without formatting")
@click.pass_context
def cli(ctx: click.Context, verbose: bool, debug: bool, raw: bool) -> None:
    """Handler - A2A protocol client CLI."""
    ctx.ensure_object(dict)
    ctx.obj["raw"] = raw

    if debug:
        setup_logging(level="DEBUG")
    elif verbose:
        setup_logging(level="INFO")
    else:
        setup_logging(level="ERROR")


def get_mode(ctx: click.Context, output: str) -> str:
    """Get output mode from context and output option."""
    if output == "json":
        return "json"
    if ctx.obj.get("raw"):
        return "raw"
    return "text"


# ============================================================================
# Message Commands
# ============================================================================


@cli.group()
def message() -> None:
    """Send messages to A2A agents."""
    pass


@message.command("send")
@click.argument("agent_url")
@click.argument("text")
@click.option("--stream", "-s", is_flag=True, help="Stream responses in real-time")
@click.option("--context-id", help="Context ID for conversation continuity")
@click.option("--task-id", help="Task ID to continue")
@click.option(
    "--continue", "-C", "use_session", is_flag=True, help="Continue from saved session"
)
@click.option("--push-url", help="Webhook URL for push notifications")
@click.option("--push-token", help="Authentication token for push notifications")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["json", "text"]),
    default="text",
    help="Output format",
)
@click.pass_context
def message_send(
    ctx: click.Context,
    agent_url: str,
    text: str,
    stream: bool,
    context_id: Optional[str],
    task_id: Optional[str],
    use_session: bool,
    push_url: Optional[str],
    push_token: Optional[str],
    output: str,
) -> None:
    """Send a message to an agent and receive a response."""
    log.info("Sending message to %s", agent_url)

    if use_session and not context_id:
        session = get_session(agent_url)
        if session.context_id:
            context_id = session.context_id
            log.info("Using saved context: %s", context_id)

    mode = get_mode(ctx, output)

    async def do_send() -> None:
        with get_output_context(mode) as output:
            try:
                async with build_http_client() as http_client:
                    service = A2AService(
                        http_client,
                        agent_url,
                        enable_streaming=stream,
                        push_notification_url=push_url,
                        push_notification_token=push_token,
                    )

                    if mode != "json":
                        output.dim(f"Sending to {agent_url}...")

                    if stream:
                        await _stream_message(
                            service, text, context_id, task_id, agent_url, output
                        )
                    else:
                        result = await service.send(text, context_id, task_id)
                        update_session(agent_url, result.context_id, result.task_id)
                        _format_send_result(result, output)

            except Exception as e:
                _handle_client_error(e, agent_url, output)
                raise click.Abort()

    asyncio.run(do_send())


@message.command("stream")
@click.argument("agent_url")
@click.argument("text")
@click.option("--context-id", help="Context ID for conversation continuity")
@click.option("--task-id", help="Task ID to continue")
@click.option(
    "--continue", "-C", "use_session", is_flag=True, help="Continue from saved session"
)
@click.option("--push-url", help="Webhook URL for push notifications")
@click.option("--push-token", help="Authentication token for push notifications")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["json", "text"]),
    default="text",
    help="Output format",
)
@click.pass_context
def message_stream(
    ctx: click.Context,
    agent_url: str,
    text: str,
    context_id: Optional[str],
    task_id: Optional[str],
    use_session: bool,
    push_url: Optional[str],
    push_token: Optional[str],
    output: str,
) -> None:
    """Send a message and stream the response in real-time."""
    ctx.invoke(
        message_send,
        agent_url=agent_url,
        text=text,
        stream=True,
        context_id=context_id,
        task_id=task_id,
        use_session=use_session,
        push_url=push_url,
        push_token=push_token,
        output=output,
    )


async def _stream_message(
    service: A2AService,
    text: str,
    context_id: Optional[str],
    task_id: Optional[str],
    agent_url: str,
    output: Output,
) -> None:
    """Stream a message and handle events."""
    collected_text: list[str] = []
    last_context_id: str | None = None
    last_task_id: str | None = None
    last_state = None

    is_json = output.mode.value == "json"

    async for event in service.stream(text, context_id, task_id):
        last_context_id = event.context_id or last_context_id
        last_task_id = event.task_id or last_task_id
        last_state = event.state or last_state

        if is_json:
            event_data = {
                "type": event.event_type,
                "context_id": event.context_id,
                "task_id": event.task_id,
                "state": event.state.value if event.state else None,
                "text": event.text,
            }
            output.json(event_data)
        else:
            if event.text and event.text not in collected_text:
                output.line(event.text)
                collected_text.append(event.text)

    update_session(agent_url, last_context_id, last_task_id)

    if not is_json:
        output.blank()
        if last_context_id:
            output.field("Context ID", last_context_id, dim_value=True)
        if last_task_id:
            output.field("Task ID", last_task_id, dim_value=True)
        if last_state:
            output.state("State", last_state.value)


def _format_send_result(result: SendResult, output: Output) -> None:
    """Format and display a send result."""
    if output.mode.value == "json":
        output.json(result.raw)
        return

    output.blank()
    if result.context_id:
        output.field("Context ID", result.context_id, dim_value=True)
    if result.task_id:
        output.field("Task ID", result.task_id, dim_value=True)
    if result.state:
        output.state("State", result.state.value)

    output.blank()
    if result.text:
        output.markdown(result.text)
    else:
        output.dim("No text content in response")


# ============================================================================
# Task Commands
# ============================================================================


@cli.group()
def task() -> None:
    """Manage A2A tasks."""
    pass


@task.command("get")
@click.argument("agent_url")
@click.argument("task_id")
@click.option(
    "--history-length", "-n", type=int, help="Number of history messages to include"
)
@click.option(
    "--output",
    "-o",
    type=click.Choice(["json", "text"]),
    default="text",
    help="Output format",
)
@click.pass_context
def task_get(
    ctx: click.Context,
    agent_url: str,
    task_id: str,
    history_length: Optional[int],
    output: str,
) -> None:
    """Retrieve the current status of a task."""
    log.info("Getting task %s from %s", task_id, agent_url)
    mode = get_mode(ctx, output)

    async def do_get() -> None:
        with get_output_context(mode) as output:
            try:
                async with build_http_client() as http_client:
                    service = A2AService(http_client, agent_url)
                    result = await service.get_task(task_id, history_length)
                    _format_task_result(result, output)
            except Exception as e:
                _handle_client_error(e, agent_url, output)
                raise click.Abort()

    asyncio.run(do_get())


@task.command("cancel")
@click.argument("agent_url")
@click.argument("task_id")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["json", "text"]),
    default="text",
    help="Output format",
)
@click.pass_context
def task_cancel(ctx: click.Context, agent_url: str, task_id: str, output: str) -> None:
    """Request cancellation of a task."""
    log.info("Canceling task %s at %s", task_id, agent_url)
    mode = get_mode(ctx, output)

    async def do_cancel() -> None:
        with get_output_context(mode) as output:
            try:
                async with build_http_client() as http_client:
                    service = A2AService(http_client, agent_url)

                    if mode != "json":
                        output.dim(f"Canceling task {task_id}...")

                    result = await service.cancel_task(task_id)
                    _format_task_result(result, output)

                    if mode != "json":
                        output.success("Task canceled")

            except Exception as e:
                _handle_client_error(e, agent_url, output)
                raise click.Abort()

    asyncio.run(do_cancel())


@task.command("resubscribe")
@click.argument("agent_url")
@click.argument("task_id")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["json", "text"]),
    default="text",
    help="Output format",
)
@click.pass_context
def task_resubscribe(
    ctx: click.Context, agent_url: str, task_id: str, output: str
) -> None:
    """Resubscribe to a task's SSE stream after disconnection."""
    log.info("Resubscribing to task %s at %s", task_id, agent_url)
    mode = get_mode(ctx, output)

    async def do_resubscribe() -> None:
        with get_output_context(mode) as output:
            try:
                async with build_http_client() as http_client:
                    service = A2AService(http_client, agent_url)
                    is_json = output.mode.value == "json"

                    if not is_json:
                        output.dim(f"Resubscribing to task {task_id}...")

                    async for event in service.resubscribe(task_id):
                        if is_json:
                            output.json(
                                {
                                    "type": event.event_type,
                                    "context_id": event.context_id,
                                    "task_id": event.task_id,
                                    "state": event.state.value if event.state else None,
                                    "text": event.text,
                                }
                            )
                        else:
                            if event.event_type == "status":
                                output.state(
                                    "Status",
                                    event.state.value if event.state else "unknown",
                                )
                            elif event.text:
                                output.line(event.text)

            except Exception as e:
                _handle_client_error(e, agent_url, output)
                raise click.Abort()

    asyncio.run(do_resubscribe())


def _format_task_result(result: TaskResult, output: Output) -> None:
    """Format and display a task result."""
    if output.mode.value == "json":
        output.json(result.raw)
        return

    output.blank()
    output.field("Task ID", result.task_id, dim_value=True)
    output.state("State", result.state.value)
    if result.context_id:
        output.field("Context ID", result.context_id, dim_value=True)

    if result.text:
        output.blank()
        output.markdown(result.text)


# ============================================================================
# Task Notification Commands
# ============================================================================


@task.group("notification")
def task_notification() -> None:
    """Manage push notification configurations for tasks."""
    pass


@task_notification.command("set")
@click.argument("agent_url")
@click.argument("task_id")
@click.option("--url", "-u", required=True, help="Webhook URL to receive notifications")
@click.option("--token", "-t", help="Authentication token for the webhook")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["json", "text"]),
    default="text",
    help="Output format",
)
@click.pass_context
def notification_set(
    ctx: click.Context,
    agent_url: str,
    task_id: str,
    url: str,
    token: Optional[str],
    output: str,
) -> None:
    """Configure a push notification webhook for a task."""
    log.info("Setting push config for task %s at %s", task_id, agent_url)
    mode = get_mode(ctx, output)

    async def do_set() -> None:
        with get_output_context(mode) as output:
            try:
                async with build_http_client() as http_client:
                    service = A2AService(http_client, agent_url)
                    is_json = output.mode.value == "json"

                    if not is_json:
                        output.dim(f"Setting notification config for task {task_id}...")

                    config = await service.set_push_config(task_id, url, token)

                    if is_json:
                        output.json(config.model_dump())
                    else:
                        output.success("Push notification config set")
                        output.field("Task ID", config.task_id)
                        if config.push_notification_config:
                            pnc = config.push_notification_config
                            output.field("URL", pnc.url)
                            if pnc.token:
                                output.field("Token", f"{pnc.token[:20]}...")
                            if pnc.id:
                                output.field("Config ID", pnc.id)

            except Exception as e:
                _handle_client_error(e, agent_url, output)
                raise click.Abort()

    asyncio.run(do_set())


# ============================================================================
# Card Commands
# ============================================================================


@cli.group()
def card() -> None:
    """Agent card operations."""
    pass


@card.command("get")
@click.argument("agent_url")
@click.option(
    "--authenticated", "-a", is_flag=True, help="Request authenticated extended card"
)
@click.option(
    "--output",
    "-o",
    type=click.Choice(["json", "text"]),
    default="text",
    help="Output format",
)
@click.pass_context
def card_get(
    ctx: click.Context, agent_url: str, authenticated: bool, output: str
) -> None:
    """Retrieve an agent's card."""
    log.info("Fetching agent card from %s", agent_url)
    mode = get_mode(ctx, output)

    async def do_get() -> None:
        with get_output_context(mode) as output:
            try:
                async with build_http_client() as http_client:
                    service = A2AService(http_client, agent_url)
                    card_data = await service.get_card()
                    log.info("Retrieved card for agent: %s", card_data.name)

                    if output.mode.value == "json":
                        output.json(card_data.model_dump())
                    else:
                        _format_agent_card(card_data, output)

            except Exception as e:
                _handle_client_error(e, agent_url, output)
                raise click.Abort()

    asyncio.run(do_get())


def _format_agent_card(card_data: object, output: Output) -> None:
    """Format and display an agent card."""

    card_dict: dict[str, Any]
    if isinstance(card_data, AgentCard):
        card_dict = card_data.model_dump()
    else:
        card_dict = {}
    name = card_dict.pop("name", "Unknown Agent")
    description = card_dict.pop("description", "")

    output.header(name)
    if description:
        output.line(description)

    output.blank()
    for key, value in card_dict.items():
        if key.startswith("_"):
            continue
        formatted = format_value(value)
        if formatted:
            field_name = format_field_name(key)
            if "\n" in formatted:
                output.line(f"{field_name}:")
                output.line(formatted)
            else:
                output.field(field_name, formatted)


@card.command("validate")
@click.argument("source")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["json", "text"]),
    default="text",
    help="Output format",
)
@click.pass_context
def card_validate(ctx: click.Context, source: str, output: str) -> None:
    """Validate an agent card from URL or file."""
    log.info("Validating agent card from %s", source)
    is_url = source.startswith(("http://", "https://"))
    mode = get_mode(ctx, output)

    async def do_validate() -> None:
        with get_output_context(mode) as output:
            if is_url:
                async with build_http_client() as http_client:
                    result = await validate_agent_card_from_url(source, http_client)
            else:
                result = validate_agent_card_from_file(source)

            _format_validation_result(result, output)

            if not result.valid:
                raise SystemExit(1)

    asyncio.run(do_validate())


def _format_validation_result(result: ValidationResult, output: Output) -> None:
    """Format and display validation result."""
    if output.mode.value == "json":
        output.json(
            {
                "valid": result.valid,
                "source": result.source,
                "sourceType": result.source_type.value,
                "agentName": result.agent_name,
                "protocolVersion": result.protocol_version,
                "issues": [
                    {"field": i.field_name, "message": i.message, "type": i.issue_type}
                    for i in result.issues
                ],
            }
        )
        return

    if result.valid:
        output.success("Valid Agent Card")
        output.field("Agent", result.agent_name)
        output.field("Protocol Version", result.protocol_version)
        output.field("Source", result.source)
    else:
        output.error("Invalid Agent Card")
        output.field("Source", result.source)
        output.blank()
        output.line(f"Errors ({len(result.issues)}):")
        for issue in result.issues:
            output.list_item(f"{issue.field_name}: {issue.message}", bullet="✗")


# ============================================================================
# Server Commands
# ============================================================================


@cli.group()
def server() -> None:
    """Run local servers."""
    pass


@server.command("agent")
@click.option("--host", default="0.0.0.0", help="Host to bind to", show_default=True)
@click.option("--port", default=8000, help="Port to bind to", show_default=True)
def server_agent(host: str, port: int) -> None:
    """Start a local A2A agent server."""
    log.info("Starting A2A server on %s:%d", host, port)
    run_server(host, port)


@server.command("push")
@click.option("--host", default="127.0.0.1", help="Host to bind to", show_default=True)
@click.option("--port", default=9000, help="Port to bind to", show_default=True)
def server_push(host: str, port: int) -> None:
    """Start a local webhook server for receiving push notifications."""
    log.info("Starting webhook server on %s:%d", host, port)
    run_webhook_server(host, port)


# ============================================================================
# Session Commands
# ============================================================================


@cli.group()
def session() -> None:
    """Manage saved session state."""
    pass


@session.command("list")
@click.pass_context
def session_list(ctx: click.Context) -> None:
    """List all saved sessions."""
    mode = "raw" if ctx.obj.get("raw") else "text"

    with get_output_context(mode) as output:
        store = get_session_store()
        sessions = store.list_all()

        if not sessions:
            output.dim("No saved sessions")
            return

        output.header(f"Saved Sessions ({len(sessions)})")
        for s in sessions:
            output.blank()
            output.subheader(s.agent_url)
            if s.context_id:
                output.field("Context ID", s.context_id, dim_value=True)
            if s.task_id:
                output.field("Task ID", s.task_id, dim_value=True)


@session.command("show")
@click.argument("agent_url")
@click.pass_context
def session_show(ctx: click.Context, agent_url: str) -> None:
    """Display session state for an agent."""
    mode = "raw" if ctx.obj.get("raw") else "text"

    with get_output_context(mode) as output:
        s = get_session(agent_url)
        output.header(f"Session for {agent_url}")
        output.field("Context ID", s.context_id or "none", dim_value=not s.context_id)
        output.field("Task ID", s.task_id or "none", dim_value=not s.task_id)


@session.command("clear")
@click.argument("agent_url", required=False)
@click.option("--all", "-a", "clear_all", is_flag=True, help="Clear all sessions")
@click.pass_context
def session_clear(
    ctx: click.Context, agent_url: Optional[str], clear_all: bool
) -> None:
    """Clear saved session state."""
    mode = "raw" if ctx.obj.get("raw") else "text"

    with get_output_context(mode) as output:
        if clear_all:
            clear_session()
            output.success("Cleared all sessions")
        elif agent_url:
            clear_session(agent_url)
            output.success(f"Cleared session for {agent_url}")
        else:
            output.warning("Provide AGENT_URL or use --all to clear sessions")


# ============================================================================
# Utility Commands
# ============================================================================


@cli.command()
def version() -> None:
    """Display the current version."""
    click.echo(__version__)


@cli.command()
def tui() -> None:
    """Launch the interactive terminal interface."""
    log.info("Launching TUI")
    logging.getLogger().handlers = []
    app = HandlerTUI()
    app.run()


# ============================================================================
# Entry Point
# ============================================================================


def main() -> None:
    """Main entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
