"""A2A protocol client utilities."""

import uuid
from dataclasses import dataclass
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

from a2a_handler.common import get_logger

log = get_logger(__name__)

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
    log.info("Fetching agent card from [url]%s[/url]", agent_url)
    resolver = A2ACardResolver(client, agent_url)
    card = await resolver.get_agent_card()
    log.info("Received card for [agent]%s[/agent]", card.name)
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
    log.info("Sending message to [url]%s[/url]: %s", agent_url, message_text[:50])
    card = await fetch_agent_card(agent_url, client)
    log.debug("Connected to [agent]%s[/agent]", card.name)

    config = ClientConfig(
        httpx_client=client, supported_transports=[TransportProtocol.jsonrpc]
    )
    factory = ClientFactory(config)
    a2a_client = factory.create(card)

    message = _build_message(message_text, context_id, task_id)

    log.debug("Sending request with ID: %s", message.message_id)

    last_response = None
    async for response in a2a_client.send_message(message):
        last_response = response

    log.debug("Received response")

    if last_response is None:
        return {}

    if isinstance(last_response, tuple):
        return last_response[0].model_dump()

    return last_response.model_dump() if hasattr(last_response, "model_dump") else {}


@dataclass
class ParsedResponse:
    """Parsed A2A response with extracted text content."""

    text: str
    raw: dict[str, Any]

    @property
    def has_content(self) -> bool:
        """Check if the response has meaningful content."""
        return bool(self.text)


def parse_response(response: dict[str, Any]) -> ParsedResponse:
    """Parse an A2A response and extract text content.

    Args:
        response: Raw response dictionary from send_message_to_agent

    Returns:
        ParsedResponse with extracted text and raw data
    """
    if not response:
        log.debug("Empty response received")
        return ParsedResponse(text="", raw=response)

    texts: list[str] = []

    if "parts" in response:
        texts.extend(p.get("text", "") for p in response["parts"])
        log.debug("Extracted %d parts from response", len(response["parts"]))

    for artifact in response.get("artifacts", []):
        artifact_parts = artifact.get("parts", [])
        texts.extend(p.get("text", "") for p in artifact_parts)
        log.debug("Extracted %d parts from artifact", len(artifact_parts))

    text = "\n".join(t for t in texts if t)
    log.debug("Parsed response with %d characters", len(text))

    return ParsedResponse(text=text, raw=response)
