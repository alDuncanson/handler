import asyncio
import json
import logging
from typing import Optional

import click
import httpx

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

log = get_logger(__name__)


class CustomHelpOption(click.Option):
    """Custom help option with a better help message."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("is_flag", True)
        kwargs.setdefault("expose_value", False)
        kwargs.setdefault("is_eager", True)
        kwargs.setdefault("help", "Show this help message.")
        super().__init__(*args, **kwargs)

    def handle_parse_result(self, ctx, opts, args):
        if self.name in opts:
            click.echo(ctx.get_help())
            ctx.exit()
        return super().handle_parse_result(ctx, opts, args)


def add_help_option(f):
    """Decorator to add a custom help option to a command."""
    return click.option("-h", "--help", cls=CustomHelpOption)(f)


CONTEXT_SETTINGS = {"help_option_names": []}


@click.group(context_settings=CONTEXT_SETTINGS)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging output")
@click.option("--debug", "-d", is_flag=True, help="Enable debug logging output")
@add_help_option
@click.pass_context
def cli(ctx, verbose: bool, debug: bool) -> None:
    """Handler - A2A protocol client CLI."""
    ctx.ensure_object(dict)
    if debug:
        log.debug("Debug logging enabled")
        setup_logging(level="DEBUG")
    elif verbose:
        log.debug("Verbose logging enabled")
        setup_logging(level="INFO")
    else:
        setup_logging(level="WARNING")


@cli.command(context_settings=CONTEXT_SETTINGS)
@click.argument("agent_url")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["json", "text"]),
    default="text",
    help="Output format",
)
@add_help_option
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
                    title = f"[bold green]{card_data.name}[/bold green] [dim]({card_data.version})[/dim]"
                    content = f"[italic]{card_data.description}[/italic]\n\n[bold]URL:[/bold] {card_data.url}"

                    if card_data.skills:
                        log.debug("Card has %d skills", len(card_data.skills))
                        content += "\n\n[bold]Skills:[/bold]"
                        for skill in card_data.skills:
                            content += (
                                f"\n• [cyan]{skill.name}[/cyan]: {skill.description}"
                            )

                    if card_data.capabilities:
                        log.debug("Card has capabilities defined")
                        content += "\n\n[bold]Capabilities:[/bold]"
                        if hasattr(card_data.capabilities, "pushNotifications"):
                            status = (
                                "✅"
                                if card_data.capabilities.push_notifications
                                else "❌"
                            )
                            content += f"\n• Push Notifications: {status}"

                    print_panel(content, title=title)

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


@cli.command(context_settings=CONTEXT_SETTINGS)
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
@add_help_option
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


@cli.command(context_settings=CONTEXT_SETTINGS)
@add_help_option
def tui() -> None:
    """Launch the interactive TUI interface."""
    log.info("Launching TUI")
    logging.getLogger().handlers = []
    app = HandlerTUI()
    app.run()


@cli.command(context_settings=CONTEXT_SETTINGS)
@add_help_option
def version() -> None:
    """Display the current version."""
    log.debug("Displaying version: %s", __version__)
    click.echo(__version__)


@cli.command(context_settings=CONTEXT_SETTINGS)
@click.option("--host", default="0.0.0.0", help="Host to bind to", show_default=True)
@click.option("--port", default=8000, help="Port to bind to", show_default=True)
@add_help_option
def server(host: str, port: int) -> None:
    """Start the A2A server agent backed by Ollama.

    Requires Ollama to be running with the qwen3 model. Configure with
    OLLAMA_API_BASE (default: http://localhost:11434) and OLLAMA_MODEL
    environment variables.
    """
    log.info("Starting A2A server on %s:%d", host, port)
    run_server(host, port)


def main() -> None:
    """Main entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
