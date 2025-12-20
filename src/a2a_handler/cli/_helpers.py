"""Shared utilities for CLI commands."""

import httpx
import rich_click as click
from a2a.client.errors import (
    A2AClientError,
    A2AClientHTTPError,
    A2AClientTimeoutError,
)

from a2a_handler.common import Output, get_logger

TIMEOUT = 120
log = get_logger(__name__)


def build_http_client(timeout: int = TIMEOUT) -> httpx.AsyncClient:
    """Build an HTTP client with the specified timeout."""
    return httpx.AsyncClient(timeout=timeout)


def handle_client_error(e: Exception, agent_url: str, output: Output | None) -> None:
    """Handle A2A client errors with appropriate messages."""
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
