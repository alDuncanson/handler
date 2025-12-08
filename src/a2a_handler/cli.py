import asyncio
import json
import logging
from typing import Any, Optional

# Suppress noisy third-party debug logs during import
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
    console,
    get_logger,
    print_error,
    print_json,
    print_markdown,
    print_panel,
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
        {
            "name": "Global Options",
            "options": ["--verbose", "--debug", "--help"],
        },
    ],
    "handler send": [
        {
            "name": "Message Options",
            "options": ["--stream", "--continue", "--context-id", "--task-id"],
        },
        {
            "name": "Push Notification Options",
            "options": ["--push-url", "--push-token"],
        },
        {
            "name": "Output Options",
            "options": ["--output", "--help"],
        },
    ],
    "handler server": [
        {
            "name": "Server Options",
            "options": ["--host", "--port", "--help"],
        },
    ],
    "handler tasks get": [
        {
            "name": "Query Options",
            "options": ["--history-length", "--output", "--help"],
        },
    ],
}
click.rich_click.COMMAND_GROUPS = {
    "handler": [
        {
            "name": "Agent Commands",
            "commands": ["card", "send", "validate", "tasks", "push"],
        },
        {
            "name": "Interface Commands",
            "commands": ["tui", "server", "webhook"],
        },
        {
            "name": "Utility Commands",
            "commands": ["version", "session"],
        },
    ],
    "handler tasks": [
        {
            "name": "Task Commands",
            "commands": ["get", "cancel", "resubscribe"],
        },
    ],
    "handler push": [
        {
            "name": "Push Notification Commands",
            "commands": ["set", "get"],
        },
    ],
    "handler session": [
        {
            "name": "Session Commands",
            "commands": ["list", "show", "clear"],
        },
    ],
}

TIMEOUT = 120


def build_http_client(timeout: int = TIMEOUT) -> httpx.AsyncClient:
    """Build an HTTP client with the specified timeout."""
    return httpx.AsyncClient(timeout=timeout)


log = get_logger(__name__)


def _handle_client_error(e: Exception, agent_url: str) -> None:
    """Handle A2A client errors with appropriate messages."""
    if isinstance(e, A2AClientTimeoutError):
        log.error("Request to %s timed out", agent_url)
        print_error("Request timed out")
    elif isinstance(e, A2AClientHTTPError):
        log.error("A2A client error: %s", e)
        if "connection" in str(e).lower():
            print_error(f"Connection failed: Is the server running at {agent_url}?")
        else:
            print_error(str(e))
    elif isinstance(e, A2AClientError):
        log.error("A2A client error: %s", e)
        print_error(str(e))
    elif isinstance(e, httpx.ConnectError):
        log.error("Connection refused to %s", agent_url)
        print_error(f"Connection refused: Is the server running at {agent_url}?")
    elif isinstance(e, httpx.TimeoutException):
        log.error("Request to %s timed out", agent_url)
        print_error("Request timed out")
    elif isinstance(e, httpx.HTTPStatusError):
        log.error(
            "HTTP error %d from %s: %s",
            e.response.status_code,
            agent_url,
            e.response.text,
        )
        print_error(f"HTTP {e.response.status_code} - {e.response.text}")
    else:
        log.exception("Failed request to %s", agent_url)
        print_error(str(e))


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging output")
@click.option("--debug", "-d", is_flag=True, help="Enable debug logging output")
@click.pass_context
def cli(ctx, verbose: bool, debug: bool) -> None:
    """Handler A2A protocol client CLI."""
    ctx.ensure_object(dict)
    if debug:
        log.debug("Debug logging enabled")
        setup_logging(level="DEBUG")
    elif verbose:
        log.debug("Verbose logging enabled")
        setup_logging(level="INFO")
    else:
        setup_logging(level="WARNING")


def _format_field_name(name: str) -> str:
    """Convert snake_case or camelCase to Title Case."""
    import re

    name = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
    name = name.replace("_", " ")
    return name.title()


def _format_value(value: Any, indent: int = 0) -> str:
    """Recursively format a value for display, returning only truthy content."""
    prefix = "  " * indent

    if value is None or value == "" or value == [] or value == {}:
        return ""

    if isinstance(value, bool):
        return "✓" if value else "✗"

    if isinstance(value, str):
        return value

    if isinstance(value, int | float):
        return str(value)

    if isinstance(value, list):
        lines: list[str] = []
        for item in value:
            if hasattr(item, "model_dump"):
                item_dict: dict[str, Any] = item.model_dump()
                name = item_dict.get("name") or item_dict.get("id") or "Item"
                desc = item_dict.get("description") or ""
                if desc:
                    desc_prefix = "  " * (indent + 1)
                    lines.append(f"{prefix}  • [cyan]{name}[/cyan]")
                    lines.append(f"{desc_prefix}  {desc}")
                else:
                    lines.append(f"{prefix}  • [cyan]{name}[/cyan]")
            elif isinstance(item, dict):
                item_d: dict[str, Any] = item
                name = item_d.get("name") or item_d.get("id") or "Item"
                desc = item_d.get("description") or ""
                if desc:
                    desc_prefix = "  " * (indent + 1)
                    lines.append(f"{prefix}  • [cyan]{name}[/cyan]")
                    lines.append(f"{desc_prefix}  {desc}")
                else:
                    lines.append(f"{prefix}  • [cyan]{name}[/cyan]")
            else:
                formatted = _format_value(item, indent)
                if formatted:
                    lines.append(f"{prefix}  • {formatted}")
        return "\n" + "\n".join(lines) if lines else ""

    if hasattr(value, "model_dump"):
        value = value.model_dump()

    if isinstance(value, dict):
        dict_lines: list[str] = []
        for k, v in value.items():
            if isinstance(k, str) and k.startswith("_"):
                continue
            formatted = _format_value(v, indent + 1)
            if formatted:
                field_name = _format_field_name(str(k))
                if "\n" in formatted:
                    dict_lines.append(
                        f"{prefix}[bold]{field_name}:[/bold]\n{formatted}"
                    )
                else:
                    dict_lines.append(f"{prefix}[bold]{field_name}:[/bold] {formatted}")
        return "\n".join(dict_lines) if dict_lines else ""

    return str(value) if value else ""


def _format_send_result(result: SendResult, output: str) -> None:
    """Format and display a send result."""
    if output == "json":
        print_json(json.dumps(result.raw, indent=2))
        return

    content_parts = []

    if result.context_id:
        content_parts.append(f"[bold]Context ID:[/bold] [dim]{result.context_id}[/dim]")
    if result.task_id:
        content_parts.append(f"[bold]Task ID:[/bold] [dim]{result.task_id}[/dim]")
    if result.state:
        state_color = "green" if result.is_complete else "yellow"
        content_parts.append(
            f"[bold]State:[/bold] [{state_color}]{result.state.value}[/{state_color}]"
        )

    if content_parts:
        console.print("\n".join(content_parts))
        console.print()

    if result.text:
        print_markdown(result.text, title="Response")
    else:
        console.print("[dim]No text content in response[/dim]")


def _format_task_result(result: TaskResult, output: str) -> None:
    """Format and display a task result."""
    if output == "json":
        print_json(json.dumps(result.raw, indent=2))
        return

    state_color = "green" if result.state.value in ("completed",) else "yellow"
    if result.state.value in ("failed", "rejected", "canceled"):
        state_color = "red"

    content_parts = [
        f"[bold]Task ID:[/bold] [dim]{result.task_id}[/dim]",
        f"[bold]State:[/bold] [{state_color}]{result.state.value}[/{state_color}]",
    ]

    if result.context_id:
        content_parts.append(f"[bold]Context ID:[/bold] [dim]{result.context_id}[/dim]")

    title = f"[bold]Task {result.task_id[:8]}...[/bold]"
    print_panel("\n".join(content_parts), title=title)

    if result.text:
        console.print()
        print_markdown(result.text, title="Content")


@cli.command()
@click.argument("agent_url")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["json", "text"]),
    default="text",
    help="Output format",
)
def card(agent_url: str, output: str) -> None:
    """Fetch and display an agent card from AGENT_URL."""
    log.info("Fetching agent card from %s", agent_url)

    async def fetch() -> None:
        try:
            log.debug("Building HTTP client")
            async with build_http_client() as client:
                log.debug("Requesting agent card")
                service = A2AService(client, agent_url)
                card_data = await service.get_card()
                log.info("Retrieved card for agent: %s", card_data.name)

                if output == "json":
                    log.debug("Outputting card as JSON")
                    print_json(card_data.model_dump_json(indent=2))
                else:
                    log.debug("Outputting card as formatted text")
                    card_dict = card_data.model_dump()

                    name = card_dict.pop("name", "Unknown Agent")
                    description = card_dict.pop("description", "")

                    title = f"[bold green]{name}[/bold green] [dim]v{__version__}[/dim]"
                    content_parts = []

                    if description:
                        content_parts.append(f"[italic]{description}[/italic]")

                    for key, value in card_dict.items():
                        if key.startswith("_"):
                            continue
                        formatted = _format_value(value)
                        if formatted:
                            field_name = _format_field_name(key)
                            if "\n" in formatted:
                                content_parts.append(
                                    f"[bold]{field_name}:[/bold]\n{formatted}"
                                )
                            else:
                                content_parts.append(
                                    f"[bold]{field_name}:[/bold] {formatted}"
                                )

                    print_panel("\n\n".join(content_parts), title=title)

        except Exception as e:
            _handle_client_error(e, agent_url)
            raise click.Abort()

    asyncio.run(fetch())


def _format_validation_result(result: ValidationResult, output: str) -> None:
    """Format and print validation result."""
    if output == "json":
        output_data = {
            "valid": result.valid,
            "source": result.source,
            "sourceType": result.source_type.value,
            "agentName": result.agent_name,
            "protocolVersion": result.protocol_version,
            "issues": [
                {
                    "field": issue.field_name,
                    "message": issue.message,
                    "type": issue.issue_type,
                }
                for issue in result.issues
            ],
            "warnings": [
                {
                    "field": warning.field_name,
                    "message": warning.message,
                    "type": warning.issue_type,
                }
                for warning in result.warnings
            ],
        }
        print_json(json.dumps(output_data, indent=2))
        return

    if result.valid:
        title = "[bold green]✓ Valid Agent Card[/bold green]"
        content_parts = [
            f"[bold]Agent:[/bold] {result.agent_name}",
            f"[bold]Protocol Version:[/bold] {result.protocol_version}",
            f"[bold]Source:[/bold] {result.source}",
        ]

        if result.warnings:
            content_parts.append("")
            content_parts.append(
                f"[bold yellow]Warnings ({len(result.warnings)}):[/bold yellow]"
            )
            for warning in result.warnings:
                content_parts.append(
                    f"  [yellow]⚠[/yellow] {warning.field_name}: {warning.message}"
                )

        print_panel("\n".join(content_parts), title=title)
    else:
        title = "[bold red]✗ Invalid Agent Card[/bold red]"
        content_parts = [
            f"[bold]Source:[/bold] {result.source}",
            "",
            f"[bold red]Errors ({len(result.issues)}):[/bold red]",
        ]

        for issue in result.issues:
            content_parts.append(f"  [red]✗[/red] {issue.field_name}: {issue.message}")

        print_panel("\n".join(content_parts), title=title)


@cli.command()
@click.argument("source")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["json", "text"]),
    default="text",
    help="Output format",
)
def validate(source: str, output: str) -> None:
    """Validate an agent card from a URL or file path.

    SOURCE can be either:
    - A URL (e.g., http://localhost:8000)
    - A file path (e.g., ./agent-card.json)

    The command will automatically detect whether the source is a URL or file.
    """
    log.info("Validating agent card from %s", source)

    is_url = source.startswith(("http://", "https://"))

    async def do_validate() -> None:
        if is_url:
            log.debug("Detected URL source")
            async with build_http_client() as client:
                result = await validate_agent_card_from_url(source, client)
        else:
            log.debug("Detected file source")
            result = validate_agent_card_from_file(source)

        _format_validation_result(result, output)

        if not result.valid:
            raise click.Abort()

    asyncio.run(do_validate())


@cli.command()
@click.argument("agent_url")
@click.argument("message")
@click.option("--stream", "-s", is_flag=True, help="Stream responses in real-time")
@click.option("--context-id", help="Context ID for conversation continuity")
@click.option("--task-id", help="Reference an existing task ID")
@click.option(
    "--continue",
    "-c",
    "use_session",
    is_flag=True,
    help="Continue last conversation (use saved context_id)",
)
@click.option(
    "--push-url",
    "-p",
    help="Webhook URL to receive push notifications for this task",
)
@click.option(
    "--push-token",
    help="Optional authentication token for push notifications",
)
@click.option(
    "--output",
    "-o",
    type=click.Choice(["json", "text"]),
    default="text",
    help="Output format",
)
def send(
    agent_url: str,
    message: str,
    stream: bool,
    context_id: Optional[str],
    task_id: Optional[str],
    use_session: bool,
    push_url: Optional[str],
    push_token: Optional[str],
    output: str,
) -> None:
    """Send MESSAGE to an agent at AGENT_URL.

    Use --stream to receive responses in real-time via Server-Sent Events.
    Use --continue to automatically use the last context_id from previous conversation.
    Use --push-url to configure push notifications for task updates.
    """
    log.info("Sending message to %s", agent_url)
    log.debug("Message: %s", message[:100] if len(message) > 100 else message)

    if use_session and not context_id:
        session = get_session(agent_url)
        if session.context_id:
            context_id = session.context_id
            log.info("Using saved context ID: %s", context_id)

    if context_id:
        log.debug("Using context ID: %s", context_id)
    if task_id:
        log.debug("Using task ID: %s", task_id)

    async def send_msg() -> None:
        try:
            async with build_http_client() as http_client:
                service = A2AService(
                    http_client,
                    agent_url,
                    enable_streaming=stream,
                    push_notification_url=push_url,
                    push_notification_token=push_token,
                )

                if output == "text":
                    console.print(f"[dim]Sending message to {agent_url}...[/dim]")
                    if push_url:
                        console.print(f"[dim]Push notifications: {push_url}[/dim]")

                if stream:
                    log.debug("Using streaming mode")
                    collected_text: list[str] = []
                    last_context_id: str | None = None
                    last_task_id: str | None = None
                    last_state = None

                    async for event in service.stream(message, context_id, task_id):
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
                            print_json(json.dumps(event_data))
                        else:
                            if event.text and event.text not in collected_text:
                                console.print(event.text, end="", markup=False)
                                collected_text.append(event.text)

                    update_session(agent_url, last_context_id, last_task_id)

                    if output == "text":
                        console.print()
                        console.print()
                        info_parts = []
                        if last_context_id:
                            info_parts.append(
                                f"[bold]Context ID:[/bold] [dim]{last_context_id}[/dim]"
                            )
                        if last_task_id:
                            info_parts.append(
                                f"[bold]Task ID:[/bold] [dim]{last_task_id}[/dim]"
                            )
                        if last_state:
                            info_parts.append(f"[bold]State:[/bold] {last_state.value}")
                        if info_parts:
                            console.print("\n".join(info_parts))

                else:
                    log.debug("Using non-streaming mode")
                    result = await service.send(message, context_id, task_id)
                    update_session(agent_url, result.context_id, result.task_id)
                    _format_send_result(result, output)

        except Exception as e:
            _handle_client_error(e, agent_url)
            raise click.Abort()

    asyncio.run(send_msg())


@cli.group()
def tasks() -> None:
    """Manage A2A tasks."""
    pass


@tasks.command("get")
@click.argument("agent_url")
@click.argument("task_id")
@click.option(
    "--history-length",
    "-n",
    type=int,
    default=None,
    help="Number of history messages to include",
)
@click.option(
    "--output",
    "-o",
    type=click.Choice(["json", "text"]),
    default="text",
    help="Output format",
)
def tasks_get(
    agent_url: str,
    task_id: str,
    history_length: Optional[int],
    output: str,
) -> None:
    """Get the status of a task by TASK_ID."""
    log.info("Getting task %s from %s", task_id, agent_url)

    async def get_task() -> None:
        try:
            async with build_http_client() as http_client:
                service = A2AService(http_client, agent_url)
                result = await service.get_task(task_id, history_length)
                _format_task_result(result, output)

        except Exception as e:
            _handle_client_error(e, agent_url)
            raise click.Abort()

    asyncio.run(get_task())


@tasks.command("cancel")
@click.argument("agent_url")
@click.argument("task_id")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["json", "text"]),
    default="text",
    help="Output format",
)
def tasks_cancel(
    agent_url: str,
    task_id: str,
    output: str,
) -> None:
    """Cancel a running task by TASK_ID."""
    log.info("Canceling task %s at %s", task_id, agent_url)

    async def cancel_task() -> None:
        try:
            async with build_http_client() as http_client:
                service = A2AService(http_client, agent_url)

                if output == "text":
                    console.print(f"[dim]Canceling task {task_id}...[/dim]")

                result = await service.cancel_task(task_id)
                _format_task_result(result, output)

                if output == "text":
                    console.print("[green]Task canceled successfully[/green]")

        except Exception as e:
            _handle_client_error(e, agent_url)
            raise click.Abort()

    asyncio.run(cancel_task())


@tasks.command("resubscribe")
@click.argument("agent_url")
@click.argument("task_id")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["json", "text"]),
    default="text",
    help="Output format",
)
def tasks_resubscribe(
    agent_url: str,
    task_id: str,
    output: str,
) -> None:
    """Resubscribe to a task's event stream by TASK_ID.

    This resumes streaming for a task that you previously disconnected from.
    """
    log.info("Resubscribing to task %s at %s", task_id, agent_url)

    async def resubscribe() -> None:
        try:
            async with build_http_client() as http_client:
                service = A2AService(http_client, agent_url)

                if output == "text":
                    console.print(f"[dim]Resubscribing to task {task_id}...[/dim]")

                async for event in service.resubscribe(task_id):
                    if output == "json":
                        event_data = {
                            "type": event.event_type,
                            "context_id": event.context_id,
                            "task_id": event.task_id,
                            "state": event.state.value if event.state else None,
                            "text": event.text,
                        }
                        print_json(json.dumps(event_data))
                    else:
                        if event.event_type == "status":
                            console.print(
                                f"[dim]Status:[/dim] {event.state.value if event.state else 'unknown'}"
                            )
                        elif event.text:
                            console.print(event.text, markup=False)

        except Exception as e:
            _handle_client_error(e, agent_url)
            raise click.Abort()

    asyncio.run(resubscribe())


@cli.group()
def push() -> None:
    """Manage push notification configurations."""
    pass


@push.command("set")
@click.argument("agent_url")
@click.argument("task_id")
@click.option("--url", "-u", required=True, help="Webhook URL to receive notifications")
@click.option("--token", "-t", help="Optional authentication token")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["json", "text"]),
    default="text",
    help="Output format",
)
def push_set(
    agent_url: str,
    task_id: str,
    url: str,
    token: Optional[str],
    output: str,
) -> None:
    """Set push notification config for a task.

    Configure the agent to send push notifications to a webhook URL
    when task status changes.

    Example:
        handler push set http://localhost:8000 TASK_ID --url http://localhost:9000/webhook
    """
    log.info("Setting push config for task %s at %s", task_id, agent_url)

    async def set_push() -> None:
        try:
            async with build_http_client() as http_client:
                service = A2AService(http_client, agent_url)

                if output == "text":
                    console.print(
                        f"[dim]Setting push notification config for task {task_id}...[/dim]"
                    )

                config = await service.set_push_config(task_id, url, token)

                if output == "json":
                    print_json(config.model_dump_json(indent=2))
                else:
                    console.print(
                        "[green]Push notification config set successfully[/green]"
                    )
                    console.print(f"[bold]Task ID:[/bold] {task_id}")
                    console.print(f"[bold]Webhook URL:[/bold] {url}")
                    if token:
                        console.print(f"[bold]Token:[/bold] {token[:20]}...")

        except Exception as e:
            _handle_client_error(e, agent_url)
            raise click.Abort()

    asyncio.run(set_push())


@push.command("get")
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
def push_get(
    agent_url: str,
    task_id: str,
    config_id: str,
    output: str,
) -> None:
    """Get push notification config for a task."""
    log.info("Getting push config %s for task %s at %s", config_id, task_id, agent_url)

    async def get_push() -> None:
        try:
            async with build_http_client() as http_client:
                service = A2AService(http_client, agent_url)
                config = await service.get_push_config(task_id, config_id)

                if output == "json":
                    print_json(config.model_dump_json(indent=2))
                else:
                    console.print("[bold]Push Notification Config[/bold]")
                    console.print(f"[bold]Task ID:[/bold] {config.task_id}")
                    if config.push_notification_config:
                        pnc = config.push_notification_config
                        console.print(f"[bold]URL:[/bold] {pnc.url}")
                        if pnc.token:
                            console.print(f"[bold]Token:[/bold] {pnc.token[:20]}...")

        except Exception as e:
            _handle_client_error(e, agent_url)
            raise click.Abort()

    asyncio.run(get_push())


@cli.command()
@click.option("--host", default="127.0.0.1", help="Host to bind to", show_default=True)
@click.option("--port", default=9000, help="Port to bind to", show_default=True)
def webhook(host: str, port: int) -> None:
    """Start a local webhook server to receive push notifications.

    This starts a simple HTTP server that receives and displays
    push notifications from A2A agents. Useful for testing.

    Example:
        handler webhook --port 9000
        # Then use http://localhost:9000/webhook as your push notification URL
    """
    log.info("Starting webhook server on %s:%d", host, port)
    run_webhook_server(host, port)


@cli.group()
def session() -> None:
    """Manage saved session state."""
    pass


@session.command("list")
def session_list() -> None:
    """List all saved sessions."""
    store = get_session_store()
    sessions = store.list_all()

    if not sessions:
        console.print("[dim]No saved sessions[/dim]")
        return

    console.print(f"[bold]Saved Sessions ({len(sessions)}):[/bold]")
    console.print()
    for s in sessions:
        console.print(f"[bold cyan]{s.agent_url}[/bold cyan]")
        if s.context_id:
            console.print(f"  [dim]Context ID:[/dim] {s.context_id}")
        if s.task_id:
            console.print(f"  [dim]Task ID:[/dim] {s.task_id}")


@session.command("show")
@click.argument("agent_url")
def session_show(agent_url: str) -> None:
    """Show session for a specific agent."""
    s = get_session(agent_url)
    console.print(f"[bold]Session for {agent_url}[/bold]")
    console.print(f"[bold]Context ID:[/bold] {s.context_id or '[dim]none[/dim]'}")
    console.print(f"[bold]Task ID:[/bold] {s.task_id or '[dim]none[/dim]'}")


@session.command("clear")
@click.argument("agent_url", required=False)
@click.option("--all", "-a", "clear_all", is_flag=True, help="Clear all sessions")
def session_clear(agent_url: Optional[str], clear_all: bool) -> None:
    """Clear saved session(s).

    Provide AGENT_URL to clear a specific session, or use --all to clear all.
    """
    if clear_all:
        clear_session()
        console.print("[green]Cleared all sessions[/green]")
    elif agent_url:
        clear_session(agent_url)
        console.print(f"[green]Cleared session for {agent_url}[/green]")
    else:
        console.print(
            "[yellow]Provide AGENT_URL or use --all to clear sessions[/yellow]"
        )


@cli.command()
def tui() -> None:
    """Launch the TUI."""
    log.info("Launching TUI")
    logging.getLogger().handlers = []
    app = HandlerTUI()
    app.run()


@cli.command()
def version() -> None:
    """Display the current version."""
    log.debug("Displaying version: %s", __version__)
    click.echo(__version__)


@cli.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to", show_default=True)
@click.option("--port", default=8000, help="Port to bind to", show_default=True)
def server(host: str, port: int) -> None:
    """Start the A2A server agent backed by Ollama."""
    log.info("Starting A2A server on %s:%d", host, port)
    run_server(host, port)


def main() -> None:
    """Main entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
