"""MCP server CLI command."""

from typing import Literal

import rich_click as click

from a2a_handler.common import get_logger

log = get_logger(__name__)

TransportType = Literal["stdio", "sse", "streamable-http"]


@click.command()
@click.option(
    "--transport",
    "-t",
    type=click.Choice(["stdio", "sse", "streamable-http"]),
    default="stdio",
    help="Transport protocol to use",
    show_default=True,
)
def mcp(transport: TransportType) -> None:
    """Run a local MCP server exposing A2A capabilities.

    This starts an MCP (Model Context Protocol) server that exposes Handler's
    A2A functionality as MCP tools and resources. You can connect to this
    server from any MCP-compatible client (like Claude Desktop, Cursor, etc.).

    The server provides tools for:
    - Validating A2A agent cards
    - More capabilities coming soon...

    Example configuration for Claude Desktop (claude_desktop_config.json):

        {
          "mcpServers": {
            "handler": {
              "command": "handler",
              "args": ["mcp"]
            }
          }
        }
    """
    from a2a_handler.mcp import run_mcp_server

    log.info("Starting MCP server with %s transport", transport)
    run_mcp_server(transport=transport)
