"""A2A server agent with streaming and push notification support.

Provides a local A2A-compatible agent server for testing and development.
"""

import os
from collections.abc import Awaitable, Callable

import click
import httpx
import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import (
    BasePushNotificationSender,
    InMemoryPushNotificationConfigStore,
    InMemoryTaskStore,
)
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from dotenv import load_dotenv
from google.adk.a2a.executor.a2a_agent_executor import A2aAgentExecutor
from google.adk.agents.llm_agent import Agent
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.adk.auth.credential_service.in_memory_credential_service import (
    InMemoryCredentialService,
)
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from starlette.applications import Starlette

from a2a_handler.common import console, get_logger, setup_logging

setup_logging(level="INFO", suppress_libs=["uvicorn", "google"])
logger = get_logger(__name__)

DEFAULT_OLLAMA_API_BASE = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "qwen3"
DEFAULT_HTTP_TIMEOUT_SECONDS = 30


def create_llm_agent() -> Agent:
    """Create and configure the A2A test agent using LiteLLM with Ollama.

    Returns:
        Configured ADK Agent instance
    """
    load_dotenv()

    ollama_api_base = os.getenv("OLLAMA_API_BASE", DEFAULT_OLLAMA_API_BASE)
    ollama_model_name = os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)

    logger.info(
        "Creating agent with model: [highlight]%s[/highlight] at [url]%s[/url]",
        ollama_model_name,
        ollama_api_base,
    )

    language_model = LiteLlm(
        model=f"ollama_chat/{ollama_model_name}",
        api_base=ollama_api_base,
        reasoning_effort="none",
    )

    agent = Agent(
        name="Handler",
        model=language_model,
        description="Handler's Agent",
        instruction="""You are Handler's Agent, the built-in assistant for the Handler application.

Handler is an A2A (Agent-to-Agent) protocol client published on PyPI as `a2a-handler`. It provides tools for developers to communicate with, test, and debug A2A-compatible agents.

Handler's architecture consists of:
1. **TUI** - An interactive terminal interface (Textual-based) for managing agent connections, sending messages, and viewing streaming responses
2. **CLI** - A rich-click powered command-line interface for scripting and automation with commands for:
   - `message send/stream` - Send messages to agents with optional streaming
   - `task get/cancel/resubscribe` - Manage A2A tasks
   - `card get/validate` - Retrieve and validate agent cards
   - `session list/show/clear` - Manage conversation sessions
   - `server agent/push` - Run local servers (including this one!)
3. **A2AService** - A unified service layer wrapping the a2a-sdk for protocol operations
4. **Server Agent** - A local A2A-compatible agent (you!) for testing, built with Google ADK and LiteLLM/Ollama

Handler supports streaming responses, push notifications, session persistence, and both JSON and formatted text output.

You are running as Handler's built-in server agent, useful for testing A2A integrations locally. Be helpful, concise, and knowledgeable about both Handler and the A2A protocol.""",
    )

    logger.info(
        "[success]Agent created successfully:[/success] [agent]%s[/agent]", agent.name
    )
    return agent


def build_agent_card(agent: Agent, host: str, port: int) -> AgentCard:
    """Build an AgentCard with streaming and push notification capabilities.

    Args:
        agent: The ADK agent
        host: Host address for the RPC URL
        port: Port number for the RPC URL

    Returns:
        Configured AgentCard with capabilities enabled
    """
    agent_capabilities = AgentCapabilities(
        streaming=True,
        push_notifications=True,
    )

    agent_skill = AgentSkill(
        id="handler_assistant",
        name="Handler Assistant",
        description="Answers questions about the Handler A2A toolkit and helps with usage",
        tags=["a2a", "handler", "help"],
        examples=["What is Handler?", "How do I use the CLI?", "Tell me about A2A"],
    )

    rpc_endpoint_url = f"http://{host}:{port}/"

    logger.debug("Building agent card with RPC URL: %s", rpc_endpoint_url)

    return AgentCard(
        name=agent.name,
        description=agent.description or "Handler A2A agent",
        url=rpc_endpoint_url,
        version="1.0.0",
        capabilities=agent_capabilities,
        skills=[agent_skill],
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
    )


def create_runner_factory(agent: Agent) -> Callable[[], Awaitable[Runner]]:
    """Create a factory function that builds a Runner for the agent.

    Args:
        agent: The ADK agent to wrap

    Returns:
        A callable that creates a Runner instance
    """

    async def create_runner() -> Runner:
        return Runner(
            app_name=agent.name or "handler_agent",
            agent=agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
            credential_service=InMemoryCredentialService(),
        )

    return create_runner


def create_a2a_application(agent: Agent, agent_card: AgentCard) -> Starlette:
    """Create a Starlette A2A application with full push notification support.

    This is a custom implementation that replaces google-adk's to_a2a() to add
    push notification support. The to_a2a() function doesn't pass push_config_store
    or push_sender to DefaultRequestHandler, causing push notification operations
    to fail with "UnsupportedOperationError".

    Args:
        agent: The ADK agent
        agent_card: Pre-configured agent card

    Returns:
        Configured Starlette application
    """
    task_store = InMemoryTaskStore()
    push_notification_config_store = InMemoryPushNotificationConfigStore()
    http_client = httpx.AsyncClient(timeout=DEFAULT_HTTP_TIMEOUT_SECONDS)
    push_notification_sender = BasePushNotificationSender(
        http_client, push_notification_config_store
    )

    agent_executor = A2aAgentExecutor(
        runner=create_runner_factory(agent),
    )

    request_handler = DefaultRequestHandler(
        agent_executor=agent_executor,
        task_store=task_store,
        push_config_store=push_notification_config_store,
        push_sender=push_notification_sender,
    )

    application = Starlette()

    async def setup_a2a_routes() -> None:
        a2a_starlette_app = A2AStarletteApplication(
            agent_card=agent_card,
            http_handler=request_handler,
        )
        a2a_starlette_app.add_routes_to_app(application)
        logger.info("A2A routes configured with push notification support")

    async def cleanup_http_client() -> None:
        await http_client.aclose()
        logger.info("HTTP client closed")

    application.add_event_handler("startup", setup_a2a_routes)
    application.add_event_handler("shutdown", cleanup_http_client)

    return application


def run_server(host: str, port: int) -> None:
    """Start the A2A server agent.

    Args:
        host: Host address to bind to
        port: Port number to bind to
    """
    console.print(
        f"\n[bold]Starting Handler server on [url]{host}:{port}[/url][/bold]\n"
    )
    logger.info("Initializing A2A server with push notification support...")

    agent = create_llm_agent()
    agent_card = build_agent_card(agent, host, port)

    streaming_enabled = (
        agent_card.capabilities.streaming if agent_card.capabilities else False
    )
    push_notifications_enabled = (
        agent_card.capabilities.push_notifications if agent_card.capabilities else False
    )

    logger.info(
        "Agent card capabilities: streaming=%s, push_notifications=%s",
        streaming_enabled,
        push_notifications_enabled,
    )

    a2a_application = create_a2a_application(agent, agent_card)
    uvicorn.run(a2a_application, host=host, port=port)


@click.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=8000, help="Port to bind to")
def main(host: str, port: int) -> None:
    """CLI entry point."""
    run_server(host, port)


if __name__ == "__main__":
    main()
