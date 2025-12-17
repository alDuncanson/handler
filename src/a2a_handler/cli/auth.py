"""Auth commands for managing authentication credentials."""

from typing import Optional

import rich_click as click

from a2a_handler.auth import AuthType, create_api_key_auth, create_bearer_auth
from a2a_handler.common import Output
from a2a_handler.session import clear_credentials, get_credentials, set_credentials


@click.group()
def auth() -> None:
    """Manage authentication credentials for agents."""
    pass


@auth.command("set")
@click.argument("agent_url")
@click.option("--bearer", "-b", "bearer_token", help="Bearer token for authentication")
@click.option("--api-key", "-k", "api_key", help="API key for authentication")
@click.option(
    "--api-key-header",
    default="X-API-Key",
    help="Header name for API key (default: X-API-Key)",
)
def auth_set(
    agent_url: str,
    bearer_token: Optional[str],
    api_key: Optional[str],
    api_key_header: str,
) -> None:
    """Set authentication credentials for an agent.

    Provide either --bearer or --api-key (not both).
    """
    output = Output()
    if bearer_token and api_key:
        output.error("Provide either --bearer or --api-key, not both")
        raise click.Abort()

    if not bearer_token and not api_key:
        output.error("Provide --bearer or --api-key")
        raise click.Abort()

    if bearer_token:
        credentials = create_bearer_auth(bearer_token)
        auth_type_display = "Bearer token"
    else:
        credentials = create_api_key_auth(api_key or "", header_name=api_key_header)
        auth_type_display = f"API key (header: {api_key_header})"

    set_credentials(agent_url, credentials)

    output.success(f"Set {auth_type_display} for {agent_url}")


@auth.command("show")
@click.argument("agent_url")
def auth_show(agent_url: str) -> None:
    """Show authentication credentials for an agent."""
    output = Output()
    credentials = get_credentials(agent_url)

    output.header(f"Auth for {agent_url}")

    if not credentials:
        output.dim("No credentials configured")
        return

    output.field("Type", credentials.auth_type.value)
    masked_value = (
        f"{credentials.value[:4]}...{credentials.value[-4:]}"
        if len(credentials.value) > 8
        else "****"
    )
    output.field("Value", masked_value)

    if credentials.auth_type == AuthType.API_KEY:
        output.field("Header", credentials.header_name or "X-API-Key")


@auth.command("clear")
@click.argument("agent_url")
def auth_clear(agent_url: str) -> None:
    """Clear authentication credentials for an agent."""
    output = Output()
    clear_credentials(agent_url)
    output.success(f"Cleared credentials for {agent_url}")
