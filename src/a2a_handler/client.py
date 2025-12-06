"""A2A protocol client utilities.

This module provides backwards-compatible functions that wrap A2AService.
For new code, use A2AService directly.
"""

from dataclasses import dataclass
from typing import Any

import httpx
from a2a.types import AgentCard

from a2a_handler.a2a_service import A2AService
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
    service = A2AService(client, agent_url)
    return await service.get_card()


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
    service = A2AService(client, agent_url)
    result = await service.send(message_text, context_id, task_id)
    return result.raw


@dataclass
class ParsedResponse:
    """Parsed A2A response with extracted text content."""

    text: str
    raw: dict[str, Any]
    context_id: str | None = None
    task_id: str | None = None

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
    context_id = response.get("context_id")
    task_id = response.get("id") or response.get("task_id")

    if "parts" in response:
        for p in response["parts"]:
            if isinstance(p, dict):
                if "root" in p and isinstance(p["root"], dict):
                    texts.append(p["root"].get("text", ""))
                else:
                    texts.append(p.get("text", ""))
        log.debug("Extracted %d parts from response", len(response["parts"]))

    for artifact in response.get("artifacts", []):
        artifact_parts = artifact.get("parts", [])
        for p in artifact_parts:
            if isinstance(p, dict):
                if "root" in p and isinstance(p["root"], dict):
                    texts.append(p["root"].get("text", ""))
                else:
                    texts.append(p.get("text", ""))
        log.debug("Extracted %d parts from artifact", len(artifact_parts))

    if "history" in response:
        for msg in response["history"]:
            if msg.get("role") == "agent":
                for p in msg.get("parts", []):
                    if isinstance(p, dict):
                        if "root" in p and isinstance(p["root"], dict):
                            texts.append(p["root"].get("text", ""))
                        else:
                            texts.append(p.get("text", ""))

    text = "\n".join(t for t in texts if t)
    log.debug("Parsed response with %d characters", len(text))

    return ParsedResponse(
        text=text,
        raw=response,
        context_id=context_id,
        task_id=task_id,
    )
