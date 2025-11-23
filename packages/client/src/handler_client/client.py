import logging
import uuid
from typing import Any

import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.types import (
    AgentCard,
    Message,
    Part,
    Role,
    TextPart,
    TransportProtocol,
)

logger = logging.getLogger(__name__)

TIMEOUT = 120


def build_http_client(timeout: int = TIMEOUT) -> httpx.AsyncClient:
    """Build an HTTP client with the specified timeout.

    Args:
        timeout: Request timeout in seconds

    Returns:
        Configured HTTP client
    """
    return httpx.AsyncClient(timeout=timeout)


async def fetch_agent_card(agent_url: str, client: httpx.AsyncClient) -> AgentCard:
    """Fetch agent card from the specified URL.

    Args:
        agent_url: The base URL of the agent
        client: HTTP client to use for the request

    Returns:
        The agent's card with metadata and capabilities

    Raises:
        httpx.RequestError: If the request fails
    """
    logger.info("Fetching agent card from %s", agent_url)
    resolver = A2ACardResolver(client, agent_url)
    card = await resolver.get_agent_card()
    logger.info("Received card for %s", card.name)
    return card


def _build_message(
    message_text: str,
    context_id: str | None = None,
    task_id: str | None = None,
) -> Message:
    """Build a message object.

    Args:
        message_text: The message content
        context_id: Optional context ID for conversation continuity
        task_id: Optional task ID to reference

    Returns:
        A properly formatted message
    """
    return Message(
        message_id=str(uuid.uuid4()),
        role=Role.user,
        parts=[Part(TextPart(text=message_text))],
        context_id=context_id,
        task_id=task_id,
    )


async def send_message_to_agent(
    agent_url: str,
    message_text: str,
    client: httpx.AsyncClient,
    context_id: str | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    """Send a message to an agent and return the response.

    Args:
        agent_url: The base URL of the agent
        message_text: The message to send
        client: HTTP client to use
        context_id: Optional context ID for conversation continuity
        task_id: Optional task ID to reference

    Returns:
        Response data as a dictionary

    Raises:
        httpx.RequestError: If the request fails
        httpx.TimeoutException: If the request times out
    """
    logger.info("Sending message to %s: %s", agent_url, message_text[:50])
    card = await fetch_agent_card(agent_url, client)
    logger.debug("Connected to %s", card.name)

    config = ClientConfig(
        httpx_client=client, supported_transports=[TransportProtocol.jsonrpc]
    )
    factory = ClientFactory(config)
    a2a_client = factory.create(card)

    message = _build_message(message_text, context_id, task_id)

    logger.debug("Sending request with ID: %s", message.message_id)

    last_response = None
    async for response in a2a_client.send_message(message):
        last_response = response

    logger.debug("Received response")

    if last_response is None:
        return {}

    if isinstance(last_response, tuple):
        return last_response[0].model_dump()

    return last_response.model_dump() if hasattr(last_response, "model_dump") else {}
