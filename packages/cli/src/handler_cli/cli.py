import asyncio
import json
from typing import Optional

import click
import httpx
from handler_client import (
    build_http_client,
    fetch_agent_card,
    send_message_to_agent,
)
from handler_common import (
    console,
    get_logger,
    print_error,
    print_json,
    print_markdown,
    print_panel,
    setup_logging,
)


setup_logging(level="INFO")
log = get_logger(__name__)


@click.group()
@click.pass_context
def cli(ctx) -> None:
    """Handler - A2A protocol client CLI"""
    ctx.ensure_object(dict)


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
    """Fetch and display an agent card.

    Args:
        agent_url: The URL of the agent
        output: Output format (json or text)
    """

    async def fetch() -> None:
        try:
            async with build_http_client() as client:
                card_data = await fetch_agent_card(agent_url, client)

                if output == "json":
                    print_json(card_data.model_dump_json(indent=2))
                else:
                    title = f"[bold green]{card_data.name}[/bold green] [dim]({card_data.version})[/dim]"
                    content = f"[italic]{card_data.description}[/italic]\n\n[bold]URL:[/bold] {card_data.url}"

                    if card_data.skills:
                        content += "\n\n[bold]Skills:[/bold]"
                        for skill in card_data.skills:
                            content += (
                                f"\n• [cyan]{skill.name}[/cyan]: {skill.description}"
                            )

                    if card_data.capabilities:
                        content += "\n\n[bold]Capabilities:[/bold]"
                        if hasattr(card_data.capabilities, "pushNotifications"):
                            status = (
                                "✅"
                                if card_data.capabilities.push_notifications
                                else "❌"
                            )
                            content += f"\n• Push Notifications: {status}"

                    print_panel(content, title=title)

        except httpx.TimeoutException:
            print_error("Request timed out")
            raise click.Abort()
        except httpx.HTTPStatusError as e:
            print_error(f"HTTP {e.response.status_code} - {e.response.text}")
            raise click.Abort()
        except Exception as e:
            log.exception("Failed to fetch agent card")
            print_error(str(e))
            raise click.Abort()

    asyncio.run(fetch())


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
    """Send a message to an agent.

    Args:
        agent_url: The URL of the agent
        message: The message to send
        context_id: Optional context ID for conversation continuity
        task_id: Optional task ID to reference
        output: Output format (json or text)
    """

    async def send_msg() -> None:
        try:
            async with build_http_client() as client:
                log.debug("Sending message to %s", agent_url)

                if output == "text":
                    console.print(f"[dim]Sending message to {agent_url}...[/dim]")

                response = await send_message_to_agent(
                    agent_url, message, client, context_id, task_id
                )

                if output == "json":
                    print_json(json.dumps(response, indent=2))
                else:
                    if not response:
                        text = "Error: No result in response"
                    else:
                        texts = []
                        if "parts" in response:
                            texts.extend(p.get("text", "") for p in response["parts"])

                        for artifact in response.get("artifacts", []):
                            texts.extend(
                                p.get("text", "") for p in artifact.get("parts", [])
                            )

                        text = "\n".join(t for t in texts if t) or "No text in response"

                    print_markdown(text, title="Response")

        except httpx.TimeoutException:
            print_error("Request timed out")
            raise click.Abort()
        except httpx.HTTPStatusError as e:
            print_error(f"HTTP {e.response.status_code} - {e.response.text}")
            raise click.Abort()
        except Exception as e:
            log.exception("Failed to send message")
            print_error(str(e))
            raise click.Abort()

    asyncio.run(send_msg())


@cli.command()
def tui() -> None:
    """Launch the Handler TUI interface."""
    import logging

    log.info("Launching TUI")
    try:
        from a2a_handler.tui import HandlerTUI
    except ImportError as e:
        print_error(
            f"Failed to import TUI dependencies: {e}\n\nMake sure handler-tui is installed."
        )
        raise click.Abort()

    logging.getLogger().handlers = []

    app = HandlerTUI()
    app.run()


@cli.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=8000, help="Port to bind to")
def server(host: str, port: int) -> None:
    """Start the A2A server agent backed by Ollama.

    Requires Ollama to be running (default: http://localhost:11434) with the qwen3 model (configurable via OLLAMA_API_BASE and OLLAMA_MODEL).
    """
    try:
        from handler_server.server import run_server
    except ImportError as e:
        print_error(
            f"Failed to import server dependencies: {e}\n\nMake sure handler-server is installed."
        )
        raise click.Abort()

    run_server(host, port)


def main() -> None:
    """Main entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
