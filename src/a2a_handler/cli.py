"""Handler CLI - A2A protocol client.

Command structure based on A2A protocol method mapping:
- message send/stream: Send messages to agents
- task get/cancel/resubscribe: Manage tasks
- task notification set/get/list/delete: Push notification configs
- card get/validate: Agent card operations
- server agent/push: Run local servers
- session list/show/get/clear: Manage saved sessions
"""

import asyncio
import logging
from typing import Optional

logging.getLogger().setLevel(logging.WARNING)

import httpx
import rich_click as click
from a2a.client.errors import (
    A2AClientError,
    A2AClientHTTPError,
    A2AClientTimeoutError,
)

from a2a_handler import __version__
from a2a_handler.common import (
    format_field_name,
    format_value,
    get_logger,
    get_output_context,
    setup_logging,
)
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
        {"name": "Notification Commands", "commands": ["set", "get", "list", "delete"]},
    ],
    "handler card": [
        {"name": "Card Commands", "commands": ["get", "validate"]},
    ],
    "handler server": [
        {"name": "Server Commands", "commands": ["agent", "push"]},
    ],
    "handler session": [
        {"name": "Session Commands", "commands": ["list", "show", "get", "clear"]},
    ],
}


TIMEOUT = 120
log = get_logger(__name__)


def build_http_client(timeout: int = TIMEOUT) -> httpx.AsyncClient:
    """Build an HTTP client with the specified timeout."""
    return httpx.AsyncClient(timeout=timeout)


def _handle_client_error(e: Exception, agent_url: str, ctx: object) -> None:
    """Handle A2A client errors with appropriate messages."""
    from a2a_handler.common.output import OutputContext

    out = ctx if isinstance(ctx, OutputContext) else None

    msg = ""
    if isinstance(e, A2AClientTimeoutError):
        log.error("Request to %s timed out", agent_url)
        msg = "Request timed out"
    elif isinstance(e, A2AClientHTTPError):
        log.error("A2A client error: %s", e)
        msg = (
            f"Connection failed: Is the server running at {agent_url}?"
            if "connection" in str(e).lower()
            else str(e)
        )
    elif isinstance(e, A2AClientError):
        log.error("A2A client error: %s", e)
        msg = str(e)
    elif isinstance(e, httpx.ConnectError):
        log.error("Connection refused to %s", agent_url)
        msg = f"Connection refused: Is the server running at {agent_url}?"
    elif isinstance(e, httpx.TimeoutException):
        log.error("Request to %s timed out", agent_url)
        msg = "Request timed out"
    elif isinstance(e, httpx.HTTPStatusError):
        log.error("HTTP error %d from %s", e.response.status_code, agent_url)
        msg = f"HTTP {e.response.status_code} - {e.response.text}"
    else:
        log.exception("Failed request to %s", agent_url)
        msg = str(e)

    if out:
        out.out_error(msg)
    else:
        click.echo(f"Error: {msg}", err=True)


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
    """Send a message to an A2A agent.

    Send `TEXT` to the agent at `AGENT_URL` and display the response.

    Examples:

        handler message send http://localhost:8000 "Hello, agent!"

        handler message send http://localhost:8000 "Continue our chat" --continue

        handler message send http://localhost:8000 "Stream this" --stream
    """
    log.info("Sending message to %s", agent_url)

    if use_session and not context_id:
        session = get_session(agent_url)
        if session.context_id:
            context_id = session.context_id
            log.info("Using saved context: %s", context_id)

    mode = get_mode(ctx, output)

    async def do_send() -> None:
        with get_output_context(mode) as out:
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
                        out.out_dim(f"Sending to {agent_url}...")

                    if stream:
                        await _stream_message(
                            service, text, context_id, task_id, agent_url, out, output
                        )
                    else:
                        result = await service.send(text, context_id, task_id)
                        update_session(agent_url, result.context_id, result.task_id)
                        _format_send_result(result, out, output)

            except Exception as e:
                _handle_client_error(e, agent_url, out)
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
    """Stream a message response from an A2A agent.

    Send `TEXT` to `AGENT_URL` and stream the response in real-time.

    Examples:

        handler message stream http://localhost:8000 "Tell me a story"
    """
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
    out: object,
    output: str,
) -> None:
    """Stream a message and handle events."""
    from a2a_handler.common.output import OutputContext

    out_ctx = out if isinstance(out, OutputContext) else None
    collected_text: list[str] = []
    last_context_id: str | None = None
    last_task_id: str | None = None
    last_state = None

    async for event in service.stream(text, context_id, task_id):
        last_context_id = event.context_id or last_context_id
        last_task_id = event.task_id or last_task_id
        last_state = event.state or last_state

        if output == "json":
            event_data = {
                "type": event.event_type,
                "context_id": event.context_id,
                "task_id": event.task_id,
                "state": event.state.value if event.state else None,
                "text": event.text,
            }
            if out_ctx:
                out_ctx.out_json(event_data)
        else:
            if event.text and event.text not in collected_text:
                if out_ctx:
                    out_ctx.out_line(event.text)
                collected_text.append(event.text)

    update_session(agent_url, last_context_id, last_task_id)

    if output != "json" and out_ctx:
        out_ctx.out_blank()
        if last_context_id:
            out_ctx.out_field("Context ID", last_context_id, dim_value=True)
        if last_task_id:
            out_ctx.out_field("Task ID", last_task_id, dim_value=True)
        if last_state:
            out_ctx.out_state("State", last_state.value)


def _format_send_result(result: SendResult, out: object, output: str) -> None:
    """Format and display a send result."""
    from a2a_handler.common.output import OutputContext

    out_ctx = out if isinstance(out, OutputContext) else None
    if not out_ctx:
        return

    if output == "json":
        out_ctx.out_json(result.raw)
        return

    out_ctx.out_blank()
    if result.context_id:
        out_ctx.out_field("Context ID", result.context_id, dim_value=True)
    if result.task_id:
        out_ctx.out_field("Task ID", result.task_id, dim_value=True)
    if result.state:
        out_ctx.out_state("State", result.state.value)

    out_ctx.out_blank()
    if result.text:
        out_ctx.out_markdown(result.text)
    else:
        out_ctx.out_dim("No text content in response")


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
    """Get the current state of a task.

    Retrieve `TASK_ID` from the agent at `AGENT_URL`.

    Examples:

        handler task get http://localhost:8000 abc123
    """
    log.info("Getting task %s from %s", task_id, agent_url)
    mode = get_mode(ctx, output)

    async def do_get() -> None:
        with get_output_context(mode) as out:
            try:
                async with build_http_client() as http_client:
                    service = A2AService(http_client, agent_url)
                    result = await service.get_task(task_id, history_length)
                    _format_task_result(result, out, output)
            except Exception as e:
                _handle_client_error(e, agent_url, out)
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
    """Cancel a running task.

    Cancel `TASK_ID` on the agent at `AGENT_URL`.

    Examples:

        handler task cancel http://localhost:8000 abc123
    """
    log.info("Canceling task %s at %s", task_id, agent_url)
    mode = get_mode(ctx, output)

    async def do_cancel() -> None:
        with get_output_context(mode) as out:
            try:
                async with build_http_client() as http_client:
                    service = A2AService(http_client, agent_url)

                    if mode != "json":
                        out.out_dim(f"Canceling task {task_id}...")

                    result = await service.cancel_task(task_id)
                    _format_task_result(result, out, output)

                    if mode != "json":
                        out.out_success("Task canceled")

            except Exception as e:
                _handle_client_error(e, agent_url, out)
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
    """Resubscribe to a task's event stream.

    Resume streaming `TASK_ID` from `AGENT_URL` after disconnecting.

    Examples:

        handler task resubscribe http://localhost:8000 abc123
    """
    log.info("Resubscribing to task %s at %s", task_id, agent_url)
    mode = get_mode(ctx, output)

    async def do_resubscribe() -> None:
        with get_output_context(mode) as out:
            try:
                async with build_http_client() as http_client:
                    service = A2AService(http_client, agent_url)

                    if mode != "json":
                        out.out_dim(f"Resubscribing to task {task_id}...")

                    async for event in service.resubscribe(task_id):
                        if output == "json":
                            out.out_json(
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
                                out.out_state(
                                    "Status",
                                    event.state.value if event.state else "unknown",
                                )
                            elif event.text:
                                out.out_line(event.text)

            except Exception as e:
                _handle_client_error(e, agent_url, out)
                raise click.Abort()

    asyncio.run(do_resubscribe())


def _format_task_result(result: TaskResult, out: object, output: str) -> None:
    """Format and display a task result."""
    from a2a_handler.common.output import OutputContext

    out_ctx = out if isinstance(out, OutputContext) else None
    if not out_ctx:
        return

    if output == "json":
        out_ctx.out_json(result.raw)
        return

    out_ctx.out_blank()
    out_ctx.out_field("Task ID", result.task_id, dim_value=True)
    out_ctx.out_state("State", result.state.value)
    if result.context_id:
        out_ctx.out_field("Context ID", result.context_id, dim_value=True)

    if result.text:
        out_ctx.out_blank()
        out_ctx.out_markdown(result.text)


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
    """Set a push notification webhook for a task.

    Configure `TASK_ID` on `AGENT_URL` to send status updates to a webhook.

    Examples:

        handler task notification set http://localhost:8000 abc123 --url http://localhost:9000/webhook
    """
    log.info("Setting push config for task %s at %s", task_id, agent_url)
    mode = get_mode(ctx, output)

    async def do_set() -> None:
        with get_output_context(mode) as out:
            try:
                async with build_http_client() as http_client:
                    service = A2AService(http_client, agent_url)

                    if mode != "json":
                        out.out_dim(
                            f"Setting notification config for task {task_id}..."
                        )

                    config = await service.set_push_config(task_id, url, token)

                    if output == "json":
                        out.out_json(config.model_dump())
                    else:
                        out.out_success("Push notification config set")
                        out.out_field("Task ID", config.task_id)
                        if config.push_notification_config:
                            pnc = config.push_notification_config
                            out.out_field("URL", pnc.url)
                            if pnc.token:
                                out.out_field("Token", f"{pnc.token[:20]}...")
                            if pnc.id:
                                out.out_field("Config ID", pnc.id)

            except Exception as e:
                _handle_client_error(e, agent_url, out)
                raise click.Abort()

    asyncio.run(do_set())


@task_notification.command("get")
@click.argument("agent_url")
@click.argument("task_id")
@click.argument("config_id")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["json", "text"]),
    default="text",
    help="Output format",
)
@click.pass_context
def notification_get(
    ctx: click.Context,
    agent_url: str,
    task_id: str,
    config_id: str,
    output: str,
) -> None:
    """Get a push notification config by ID.

    Retrieve `CONFIG_ID` for `TASK_ID` from `AGENT_URL`.

    Examples:

        handler task notification get http://localhost:8000 abc123 config456
    """
    log.info("Getting push config %s for task %s at %s", config_id, task_id, agent_url)
    mode = get_mode(ctx, output)

    async def do_get() -> None:
        with get_output_context(mode) as out:
            try:
                async with build_http_client() as http_client:
                    service = A2AService(http_client, agent_url)
                    config = await service.get_push_config(task_id, config_id)

                    if output == "json":
                        out.out_json(config.model_dump())
                    else:
                        out.out_header("Push Notification Config")
                        out.out_field("Task ID", config.task_id)
                        if config.push_notification_config:
                            pnc = config.push_notification_config
                            out.out_field("URL", pnc.url)
                            if pnc.token:
                                out.out_field("Token", f"{pnc.token[:20]}...")
                            if pnc.id:
                                out.out_field("Config ID", pnc.id)

            except Exception as e:
                _handle_client_error(e, agent_url, out)
                raise click.Abort()

    asyncio.run(do_get())


@task_notification.command("list")
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
def notification_list(
    ctx: click.Context,
    agent_url: str,
    task_id: str,
    output: str,
) -> None:
    """List all push notification configs for a task.

    List all configs for `TASK_ID` on `AGENT_URL`.

    Examples:

        handler task notification list http://localhost:8000 abc123
    """
    log.info("Listing push configs for task %s at %s", task_id, agent_url)
    mode = get_mode(ctx, output)

    async def do_list() -> None:
        with get_output_context(mode) as out:
            try:
                async with build_http_client() as http_client:
                    service = A2AService(http_client, agent_url)
                    configs = await service.list_push_configs(task_id)

                    if output == "json":
                        out.out_json([c.model_dump() for c in configs])
                    else:
                        if not configs:
                            out.out_dim("No push notification configs")
                            return

                        out.out_header(f"Push Notification Configs ({len(configs)})")
                        for config in configs:
                            out.out_blank()
                            out.out_field("Task ID", config.task_id)
                            if config.push_notification_config:
                                pnc = config.push_notification_config
                                out.out_field("URL", pnc.url)
                                if pnc.id:
                                    out.out_field("Config ID", pnc.id)

            except Exception as e:
                _handle_client_error(e, agent_url, out)
                raise click.Abort()

    asyncio.run(do_list())


@task_notification.command("delete")
@click.argument("agent_url")
@click.argument("task_id")
@click.argument("config_id")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["json", "text"]),
    default="text",
    help="Output format",
)
@click.pass_context
def notification_delete(
    ctx: click.Context,
    agent_url: str,
    task_id: str,
    config_id: str,
    output: str,
) -> None:
    """Delete a push notification config.

    Delete `CONFIG_ID` for `TASK_ID` on `AGENT_URL`.

    Examples:

        handler task notification delete http://localhost:8000 abc123 config456
    """
    log.info("Deleting push config %s for task %s at %s", config_id, task_id, agent_url)
    mode = get_mode(ctx, output)

    async def do_delete() -> None:
        with get_output_context(mode) as out:
            try:
                async with build_http_client() as http_client:
                    service = A2AService(http_client, agent_url)

                    if mode != "json":
                        out.out_dim(f"Deleting config {config_id}...")

                    await service.delete_push_config(task_id, config_id)

                    if output == "json":
                        out.out_json({"deleted": True, "config_id": config_id})
                    else:
                        out.out_success(f"Deleted config {config_id}")

            except Exception as e:
                _handle_client_error(e, agent_url, out)
                raise click.Abort()

    asyncio.run(do_delete())


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
    """Fetch and display an agent card.

    Retrieve the agent card from `AGENT_URL`.

    Examples:

        handler card get http://localhost:8000

        handler card get http://localhost:8000 --authenticated
    """
    log.info("Fetching agent card from %s", agent_url)
    mode = get_mode(ctx, output)

    async def do_get() -> None:
        with get_output_context(mode) as out:
            try:
                async with build_http_client() as http_client:
                    service = A2AService(http_client, agent_url)
                    card_data = await service.get_card()
                    log.info("Retrieved card for agent: %s", card_data.name)

                    if output == "json":
                        out.out_json(card_data.model_dump())
                    else:
                        _format_agent_card(card_data, out)

            except Exception as e:
                _handle_client_error(e, agent_url, out)
                raise click.Abort()

    asyncio.run(do_get())


def _format_agent_card(card_data: object, out: object) -> None:
    """Format and display an agent card."""
    from typing import Any

    from a2a.types import AgentCard

    from a2a_handler.common.output import OutputContext

    out_ctx = out if isinstance(out, OutputContext) else None
    if not out_ctx:
        return

    card_dict: dict[str, Any]
    if isinstance(card_data, AgentCard):
        card_dict = card_data.model_dump()
    else:
        card_dict = {}
    name = card_dict.pop("name", "Unknown Agent")
    description = card_dict.pop("description", "")

    out_ctx.out_header(name)
    if description:
        out_ctx.out_line(description)

    out_ctx.out_blank()
    for key, value in card_dict.items():
        if key.startswith("_"):
            continue
        formatted = format_value(value)
        if formatted:
            field_name = format_field_name(key)
            if "\n" in formatted:
                out_ctx.out_line(f"{field_name}:")
                out_ctx.out_line(formatted)
            else:
                out_ctx.out_field(field_name, formatted)


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
    """Validate an agent card from a URL or file path.

    Validate the agent card at `SOURCE` (URL or file path).

    Examples:

        handler card validate http://localhost:8000

        handler card validate ./my-agent-card.json
    """
    log.info("Validating agent card from %s", source)
    is_url = source.startswith(("http://", "https://"))
    mode = get_mode(ctx, output)

    async def do_validate() -> None:
        with get_output_context(mode) as out:
            if is_url:
                async with build_http_client() as http_client:
                    result = await validate_agent_card_from_url(source, http_client)
            else:
                result = validate_agent_card_from_file(source)

            _format_validation_result(result, out, output)

            if not result.valid:
                raise SystemExit(1)

    asyncio.run(do_validate())


def _format_validation_result(
    result: ValidationResult, out: object, output: str
) -> None:
    """Format and display validation result."""
    from a2a_handler.common.output import OutputContext

    out_ctx = out if isinstance(out, OutputContext) else None
    if not out_ctx:
        return

    if output == "json":
        out_ctx.out_json(
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
        out_ctx.out_success("Valid Agent Card")
        out_ctx.out_field("Agent", result.agent_name)
        out_ctx.out_field("Protocol Version", result.protocol_version)
        out_ctx.out_field("Source", result.source)
    else:
        out_ctx.out_error("Invalid Agent Card")
        out_ctx.out_field("Source", result.source)
        out_ctx.out_blank()
        out_ctx.out_line(f"Errors ({len(result.issues)}):")
        for issue in result.issues:
            out_ctx.out_list_item(f"{issue.field_name}: {issue.message}", bullet="✗")


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
    """Start the A2A agent server backed by Ollama.

    Examples:

        handler server agent

        handler server agent --port 9000
    """
    log.info("Starting A2A server on %s:%d", host, port)
    run_server(host, port)


@server.command("push")
@click.option("--host", default="127.0.0.1", help="Host to bind to", show_default=True)
@click.option("--port", default=9000, help="Port to bind to", show_default=True)
def server_push(host: str, port: int) -> None:
    """Start a local webhook server for push notifications.

    Receives and displays push notifications from A2A agents. Useful for testing.

    Examples:

        handler server push

        handler server push --port 9001
    """
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
    """List all saved sessions.

    Display all agents with saved session state.

    Examples:

        handler session list
    """
    mode = "raw" if ctx.obj.get("raw") else "text"

    with get_output_context(mode) as out:
        store = get_session_store()
        sessions = store.list_all()

        if not sessions:
            out.out_dim("No saved sessions")
            return

        out.out_header(f"Saved Sessions ({len(sessions)})")
        for s in sessions:
            out.out_blank()
            out.out_subheader(s.agent_url)
            if s.context_id:
                out.out_field("Context ID", s.context_id, dim_value=True)
            if s.task_id:
                out.out_field("Task ID", s.task_id, dim_value=True)


@session.command("show")
@click.argument("agent_url")
@click.pass_context
def session_show(ctx: click.Context, agent_url: str) -> None:
    """Show the saved session for an agent.

    Display the session for `AGENT_URL`.

    Examples:

        handler session show http://localhost:8000
    """
    mode = "raw" if ctx.obj.get("raw") else "text"

    with get_output_context(mode) as out:
        s = get_session(agent_url)
        out.out_header(f"Session for {agent_url}")
        out.out_field("Context ID", s.context_id or "none", dim_value=not s.context_id)
        out.out_field("Task ID", s.task_id or "none", dim_value=not s.task_id)


@session.command("get")
@click.argument("agent_url")
@click.pass_context
def session_get(ctx: click.Context, agent_url: str) -> None:
    """Get a specific session value.

    Retrieve the session for `AGENT_URL`.

    Examples:

        handler session get http://localhost:8000
    """
    ctx.invoke(session_show, agent_url=agent_url)


@session.command("clear")
@click.argument("agent_url", required=False)
@click.option("--all", "-a", "clear_all", is_flag=True, help="Clear all sessions")
@click.pass_context
def session_clear(
    ctx: click.Context, agent_url: Optional[str], clear_all: bool
) -> None:
    """Clear saved sessions.

    Clear the session for `AGENT_URL`, or use `--all` to clear all sessions.

    Examples:

        handler session clear http://localhost:8000

        handler session clear --all
    """
    mode = "raw" if ctx.obj.get("raw") else "text"

    with get_output_context(mode) as out:
        if clear_all:
            clear_session()
            out.out_success("Cleared all sessions")
        elif agent_url:
            clear_session(agent_url)
            out.out_success(f"Cleared session for {agent_url}")
        else:
            out.out_warning("Provide AGENT_URL or use --all to clear sessions")


# ============================================================================
# Utility Commands
# ============================================================================


@cli.command()
def version() -> None:
    """Display the current version.

    Examples:

        handler version
    """
    click.echo(__version__)


@cli.command()
def tui() -> None:
    """Launch the interactive TUI.

    Examples:

        handler tui
    """
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
