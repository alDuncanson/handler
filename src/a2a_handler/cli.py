import asyncio
import json
import logging
from typing import Any, Optional

import httpx
import rich_click as click

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
            "name": "Conversation Options",
            "options": ["--context-id", "--task-id"],
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
}
click.rich_click.COMMAND_GROUPS = {
    "handler": [
        {
            "name": "Agent Commands",
            "commands": ["card", "send", "validate"],
        },
        {
            "name": "Interface Commands",
            "commands": ["tui", "server"],
        },
        {
            "name": "Utility Commands",
            "commands": ["version"],
        },
    ],
}

setup_logging(level="WARNING")

from a2a.client.errors import (  # noqa: E402
    A2AClientError,
    A2AClientHTTPError,
    A2AClientTimeoutError,
)

from a2a_handler.client import (  # noqa: E402
    build_http_client,
    fetch_agent_card,
    parse_response,
    send_message_to_agent,
)
from a2a_handler.server import run_server  # noqa: E402
from a2a_handler.tui import HandlerTUI  # noqa: E402
from a2a_handler.validation import (  # noqa: E402
    ValidationResult,
    validate_agent_card_from_file,
    validate_agent_card_from_url,
)

log = get_logger(__name__)


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
                card_data = await fetch_agent_card(agent_url, client)
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

        except A2AClientTimeoutError:
            log.error("Request to %s timed out", agent_url)
            print_error("Request timed out")
            raise click.Abort()
        except A2AClientHTTPError as e:
            log.error("A2A client error: %s", e)
            if "connection" in str(e).lower():
                print_error(f"Connection failed: Is the server running at {agent_url}?")
            else:
                print_error(str(e))
            raise click.Abort()
        except A2AClientError as e:
            log.error("A2A client error: %s", e)
            print_error(str(e))
            raise click.Abort()
        except httpx.ConnectError:
            log.error("Connection refused to %s", agent_url)
            print_error(f"Connection refused: Is the server running at {agent_url}?")
            raise click.Abort()
        except httpx.TimeoutException:
            log.error("Request to %s timed out", agent_url)
            print_error("Request timed out")
            raise click.Abort()
        except httpx.HTTPStatusError as e:
            log.error(
                "HTTP error %d from %s: %s",
                e.response.status_code,
                agent_url,
                e.response.text,
            )
            print_error(f"HTTP {e.response.status_code} - {e.response.text}")
            raise click.Abort()
        except Exception as e:
            log.exception("Failed to fetch agent card from %s", agent_url)
            print_error(str(e))
            raise click.Abort()

    asyncio.run(fetch())


def _format_validation_result(result: ValidationResult, output: str) -> None:
    """Format and print validation result."""
    if output == "json":
        import json

        output_data = {
            "valid": result.valid,
            "source": result.source,
            "sourceType": result.source_type.value,
            "agentName": result.agent_name,
            "protocolVersion": result.protocol_version,
            "issues": [
                {"field": i.field, "message": i.message, "type": i.issue_type}
                for i in result.issues
            ],
            "warnings": [
                {"field": w.field, "message": w.message, "type": w.issue_type}
                for w in result.warnings
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
                    f"  [yellow]⚠[/yellow] {warning.field}: {warning.message}"
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
            content_parts.append(f"  [red]✗[/red] {issue.field}: {issue.message}")

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
@click.option("--context-id", help="Context ID for conversation continuity")
@click.option("--task-id", help="Reference an existing task ID")
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
    context_id: Optional[str],
    task_id: Optional[str],
    output: str,
) -> None:
    """Send MESSAGE to an agent at AGENT_URL."""
    log.info("Sending message to %s", agent_url)
    log.debug("Message: %s", message[:100] if len(message) > 100 else message)

    if context_id:
        log.debug("Using context ID: %s", context_id)
    if task_id:
        log.debug("Using task ID: %s", task_id)

    async def send_msg() -> None:
        try:
            log.debug("Building HTTP client")
            async with build_http_client() as client:
                if output == "text":
                    console.print(f"[dim]Sending message to {agent_url}...[/dim]")

                log.debug("Sending message via A2A client")
                response = await send_message_to_agent(
                    agent_url, message, client, context_id, task_id
                )
                log.debug("Received response from agent")

                if output == "json":
                    log.debug("Outputting response as JSON")
                    print_json(json.dumps(response, indent=2))
                else:
                    log.debug("Parsing response for text output")
                    parsed = parse_response(response)

                    if parsed.has_content:
                        log.debug("Response contains %d characters", len(parsed.text))
                        print_markdown(parsed.text, title="Response")
                    else:
                        log.warning("Response contained no text content")
                        print_markdown("No text in response", title="Response")

        except A2AClientTimeoutError:
            log.error("Request to %s timed out", agent_url)
            print_error("Request timed out")
            raise click.Abort()
        except A2AClientHTTPError as e:
            log.error("A2A client error: %s", e)
            if "connection" in str(e).lower():
                print_error(f"Connection failed: Is the server running at {agent_url}?")
            else:
                print_error(str(e))
            raise click.Abort()
        except A2AClientError as e:
            log.error("A2A client error: %s", e)
            print_error(str(e))
            raise click.Abort()
        except httpx.ConnectError:
            log.error("Connection refused to %s", agent_url)
            print_error(f"Connection refused: Is the server running at {agent_url}?")
            raise click.Abort()
        except httpx.TimeoutException:
            log.error("Request to %s timed out", agent_url)
            print_error("Request timed out")
            raise click.Abort()
        except httpx.HTTPStatusError as e:
            log.error(
                "HTTP error %d from %s: %s",
                e.response.status_code,
                agent_url,
                e.response.text,
            )
            print_error(f"HTTP {e.response.status_code} - {e.response.text}")
            raise click.Abort()
        except Exception as e:
            log.exception("Failed to send message to %s", agent_url)
            print_error(str(e))
            raise click.Abort()

    asyncio.run(send_msg())


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
