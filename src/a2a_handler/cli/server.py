"""Server commands for running local A2A servers."""

from typing import Optional

import rich_click as click

from a2a_handler.common import get_logger
from a2a_handler.server import run_server
from a2a_handler.webhook import run_webhook_server

log = get_logger(__name__)


@click.group()
def server() -> None:
    """Run local servers."""
    pass


@server.command("agent")
@click.option("--host", default="0.0.0.0", help="Host to bind to", show_default=True)
@click.option("--port", default=8000, help="Port to bind to", show_default=True)
@click.option("--auth/--no-auth", default=False, help="Require API key authentication")
@click.option(
    "--api-key",
    default=None,
    help="Specific API key to use (auto-generated if not set)",
)
@click.option(
    "--model",
    "-m",
    default=None,
    help="Model to use (e.g., 'llama3.2:1b', 'qwen3', 'gemini-2.0-flash')",
)
def server_agent(
    host: str,
    port: int,
    auth: bool,
    api_key: Optional[str],
    model: Optional[str],
) -> None:
    """Start a local A2A agent server."""
    log.info("Starting A2A server on %s:%d", host, port)
    run_server(
        host=host,
        port=port,
        require_auth=auth,
        api_key=api_key,
        model=model,
    )


@server.command("push")
@click.option("--host", default="127.0.0.1", help="Host to bind to", show_default=True)
@click.option("--port", default=9000, help="Port to bind to", show_default=True)
def server_push(host: str, port: int) -> None:
    """Start a local webhook server for receiving push notifications."""
    log.info("Starting webhook server on %s:%d", host, port)
    run_webhook_server(host, port)
