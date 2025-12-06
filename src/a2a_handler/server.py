"""Handler A2A server agent with full push notification support."""

import os
from collections.abc import Awaitable, Callable

import click
import httpx
import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import (
    InMemoryPushNotificationConfigStore,
    InMemoryTaskStore,
    BasePushNotificationSender,
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
log = get_logger(__name__)


def create_agent() -> Agent:
    """Create and configure the A2A test agent using LiteLLM with Ollama.

    Returns:
        Configured ADK Agent instance
    """
    load_dotenv()

    ollama_base = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
    ollama_model = os.getenv("OLLAMA_MODEL", "qwen3")

    log.info(
        "Creating agent with model: [highlight]%s[/highlight] at [url]%s[/url]",
        ollama_model,
        ollama_base,
    )

    model = LiteLlm(
        model=f"ollama_chat/{ollama_model}",
        api_base=ollama_base,
        reasoning_effort="none",
    )

    agent = Agent(
        name="Handler",
        model=model,
        description="Handler assistant",
        instruction="""You are Handler, the resident helpful agent for the Handler application.
You are an expert on the Handler toolkit, which is a terminal-based system for communicating with and testing Agent-to-Agent (A2A) protocol agents.
You know that the Handler project consists of:
1. A TUI (Text User Interface) for interactive agent management
2. A CLI (Command Line Interface) for scripting and quick interactions
3. A Client library (packages/client) that implements the A2A protocol
4. A server agent (packages/server) - which is what you are currently running on!

You should be helpful, friendly, and eager to explain how Handler works.
If asked about installation, usage, or development, provide clear, concise guidance based on the project structure.
You are proud to be an A2A server agent.""",
    )

    log.info(
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
    capabilities = AgentCapabilities(
        streaming=True,
        push_notifications=True,
    )

    skill = AgentSkill(
        id="handler_assistant",
        name="Handler Assistant",
        description="Answers questions about the Handler A2A toolkit and helps with usage",
        tags=["a2a", "handler", "help"],
        examples=["What is Handler?", "How do I use the CLI?", "Tell me about A2A"],
    )

    rpc_url = f"http://{host}:{port}/"

    return AgentCard(
        name=agent.name,
        description=agent.description or "Handler A2A agent",
        url=rpc_url,
        version="1.0.0",
        capabilities=capabilities,
        skills=[skill],
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


def create_a2a_app(agent: Agent, agent_card: AgentCard) -> Starlette:
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
    push_config_store = InMemoryPushNotificationConfigStore()
    http_client = httpx.AsyncClient(timeout=30.0)
    push_sender = BasePushNotificationSender(http_client, push_config_store)

    agent_executor = A2aAgentExecutor(
        runner=create_runner_factory(agent),
    )

    request_handler = DefaultRequestHandler(
        agent_executor=agent_executor,
        task_store=task_store,
        push_config_store=push_config_store,
        push_sender=push_sender,
    )

    app = Starlette()

    async def setup_a2a() -> None:
        a2a_app = A2AStarletteApplication(
            agent_card=agent_card,
            http_handler=request_handler,
        )
        a2a_app.add_routes_to_app(app)
        log.info("A2A routes configured with push notification support")

    async def cleanup() -> None:
        await http_client.aclose()
        log.info("HTTP client closed")

    app.add_event_handler("startup", setup_a2a)
    app.add_event_handler("shutdown", cleanup)

    return app


def run_server(host: str, port: int) -> None:
    """Start the A2A server agent.

    Args:
        host: Host address to bind to
        port: Port number to bind to
    """
    console.print(
        f"\n[bold]Starting Handler server on [url]{host}:{port}[/url][/bold]\n"
    )
    log.info("Initializing A2A server with push notification support...")
    agent = create_agent()

    agent_card = build_agent_card(agent, host, port)
    log.info(
        "Agent card capabilities: streaming=%s, push_notifications=%s",
        agent_card.capabilities.streaming if agent_card.capabilities else False,
        agent_card.capabilities.push_notifications
        if agent_card.capabilities
        else False,
    )

    a2a_app = create_a2a_app(agent, agent_card)
    uvicorn.run(a2a_app, host=host, port=port)


@click.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=8000, help="Port to bind to")
def main(host: str, port: int) -> None:
    """CLI entry point."""
    run_server(host, port)


if __name__ == "__main__":
    main()
