"""A2A server agent with streaming and push notifications.

Provides a local A2A-compatible agent server for testing and development.
"""

import asyncio
import os
import secrets
import subprocess
from collections.abc import Awaitable, Callable

import httpx
import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import (
    BasePushNotificationSender,
    InMemoryPushNotificationConfigStore,
    InMemoryTaskStore,
)
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    APIKeySecurityScheme,
    In,
    SecurityScheme,
)
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
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from a2a_handler.common import get_logger, setup_logging

setup_logging(level="INFO")
logger = get_logger(__name__)

DEFAULT_OLLAMA_API_BASE = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "llama3.2:1b"
DEFAULT_HTTP_TIMEOUT_SECONDS = 30


def get_ollama_models() -> list[str]:
    """Get list of locally available Ollama models.

    Returns:
        List of model names available in Ollama
    """
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return []
        lines = result.stdout.strip().split("\n")
        if len(lines) <= 1:
            return []
        return [line.split()[0] for line in lines[1:] if line.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError, IndexError):
        return []


def check_ollama_model(model: str) -> bool:
    """Check if a specific Ollama model is available locally.

    Args:
        model: The model name to check

    Returns:
        True if the model is available
    """
    available_models = get_ollama_models()
    model_base = model.split(":")[0]
    return any(m == model or m.startswith(f"{model_base}:") for m in available_models)


def prompt_ollama_pull(model: str) -> bool:
    """Prompt user to pull an Ollama model if not available.

    Args:
        model: The model name to pull

    Returns:
        True if pull succeeded or user declined, False on error
    """
    print(f"\nModel '{model}' not found locally.")
    response = input("Would you like to pull it now? [y/N]: ").strip().lower()

    if response not in ("y", "yes"):
        print("Skipping model pull. Server may fail to start.")
        return True

    print(f"\nPulling model {model}...\n")
    try:
        result = subprocess.run(
            ["ollama", "pull", model],
            timeout=600,
        )
        if result.returncode == 0:
            print(f"\nSuccessfully pulled {model}\n")
            return True
        print(f"\nFailed to pull {model}\n")
        return False
    except subprocess.TimeoutExpired:
        print(f"\nTimeout pulling {model}\n")
        return False
    except FileNotFoundError:
        print("\nOllama CLI not found. Please install Ollama.\n")
        return False


def generate_api_key() -> str:
    """Generate a secure random API key.

    Returns:
        A URL-safe random string suitable for use as an API key
    """
    return secrets.token_urlsafe(32)


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce API key authentication on A2A endpoints."""

    OPEN_PATHS = {
        "/.well-known/agent-card.json",
        "/health",
    }

    def __init__(self, app: Starlette, api_key: str) -> None:
        super().__init__(app)
        self.api_key = api_key

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in self.OPEN_PATHS:
            return await call_next(request)

        if request.method == "GET" and request.url.path == "/":
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        api_key_header = request.headers.get("X-API-Key")

        authenticated = False

        if api_key_header and api_key_header == self.api_key:
            authenticated = True
        elif auth_header:
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
                if token == self.api_key:
                    authenticated = True
            elif auth_header.startswith("ApiKey "):
                token = auth_header[7:]
                if token == self.api_key:
                    authenticated = True

        if not authenticated:
            return JSONResponse(
                status_code=401,
                content={
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32000,
                        "message": "Unauthorized: Invalid or missing API key",
                    },
                    "id": None,
                },
                headers={"WWW-Authenticate": 'ApiKey realm="Handler Server"'},
            )

        return await call_next(request)


def create_language_model(model: str | None = None) -> LiteLlm:
    """Create an Ollama language model via LiteLLM.

    Args:
        model: Model identifier. If None, uses OLLAMA_MODEL env var or default.

    Returns:
        LiteLlm instance configured for Ollama
    """
    load_dotenv()

    effective_model = model or os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
    ollama_api_base = os.getenv("OLLAMA_API_BASE", DEFAULT_OLLAMA_API_BASE)
    logger.info(
        "Creating agent with Ollama model: %s at %s",
        effective_model,
        ollama_api_base,
    )

    return LiteLlm(
        model=f"ollama_chat/{effective_model}",
        api_base=ollama_api_base,
        reasoning_effort="none",
    )


def create_llm_agent(model: str | None = None) -> Agent:
    """Create and configure the A2A agent using Ollama via LiteLLM.

    Args:
        model: Ollama model identifier (e.g., 'llama3.2:1b')

    Returns:
        Configured ADK Agent instance
    """
    language_model = create_language_model(model)

    instruction = """You are Handler's Agent, the built-in assistant for the Handler application.

Handler is an A2A protocol client published on PyPI as `a2a-handler`. It provides tools for developers to communicate with, test, and debug A2A-compatible agents.

Handler's architecture consists of:
1. **TUI** - An interactive terminal interface (Textual-based) for managing agent connections, sending messages, and viewing streaming responses
2. **CLI** - A rich-click powered command-line interface for scripting and automation
3. **A2AService** - A unified service layer wrapping the a2a-sdk for protocol operations
4. **Server Agent** - A local A2A-compatible agent (you!) for testing, built with Google ADK

Handler supports streaming responses, push notifications, session persistence, and both JSON and formatted text output.

Be conversational, helpful, and concise."""

    agent = Agent(
        name="Handler",
        model=language_model,
        description="Handler's built-in assistant for testing and development",
        instruction=instruction,
    )

    logger.info("Agent created successfully: %s", agent.name)
    return agent


def build_agent_card(
    agent: Agent,
    host: str,
    port: int,
    require_auth: bool = False,
) -> AgentCard:
    """Build an AgentCard with streaming and push notification capabilities.

    Args:
        agent: The ADK agent
        host: Host address for the RPC URL
        port: Port number for the RPC URL
        require_auth: Whether to require API key authentication

    Returns:
        Configured AgentCard with capabilities enabled
    """
    agent_capabilities = AgentCapabilities(
        streaming=True,
        push_notifications=True,
    )

    skills = [
        AgentSkill(
            id="handler_assistant",
            name="Handler Assistant",
            description="Helps with Handler CLI commands, TUI usage, and troubleshooting",
            tags=["handler", "cli", "tui", "help"],
            examples=[
                "How do I send a message with Handler?",
                "What CLI commands are available?",
                "How do I validate an agent card?",
            ],
        ),
    ]

    display_host = "localhost" if host == "0.0.0.0" else host
    rpc_endpoint_url = f"http://{display_host}:{port}/"

    logger.debug("Building agent card with RPC URL: %s", rpc_endpoint_url)

    security_schemes: dict[str, SecurityScheme] | None = None
    security: list[dict[str, list[str]]] | None = None

    if require_auth:
        api_key_scheme = SecurityScheme(
            root=APIKeySecurityScheme(
                type="apiKey",
                name="X-API-Key",
                in_=In.header,
            )
        )
        security_schemes = {"apiKey": api_key_scheme}
        security = [{"apiKey": []}]
        logger.info("API key authentication enabled")

    return AgentCard(
        name=agent.name,
        description=agent.description or "Handler A2A agent",
        url=rpc_endpoint_url,
        version="1.0.0",
        capabilities=agent_capabilities,
        skills=skills,
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        security_schemes=security_schemes,
        security=security,
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


def create_a2a_application(
    agent: Agent,
    agent_card: AgentCard,
    api_key: str | None = None,
) -> Starlette:
    """Create a Starlette A2A application with full push notification support.

    This is a custom implementation that replaces google-adk's to_a2a() to add
    push notification support. The to_a2a() function doesn't pass push_config_store
    or push_sender to DefaultRequestHandler, causing push notification operations
    to fail with "UnsupportedOperationError".

    Args:
        agent: The ADK agent
        agent_card: Pre-configured agent card
        api_key: Optional API key for authentication

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

    middleware: list[Middleware] = []
    if api_key:
        middleware.append(
            Middleware(APIKeyAuthMiddleware, api_key=api_key)  # type: ignore[arg-type]
        )

    application = Starlette(middleware=middleware)

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


def run_server(
    host: str,
    port: int,
    require_auth: bool = False,
    api_key: str | None = None,
    model: str | None = None,
) -> None:
    """Start the A2A server agent.

    Args:
        host: Host address to bind to
        port: Port number to bind to
        require_auth: Whether to require API key authentication
        api_key: Specific API key to use (generated if not provided and auth required)
        model: Ollama model identifier (e.g., 'llama3.2:1b')
    """
    effective_model = model or os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)

    if not check_ollama_model(effective_model):
        if not prompt_ollama_pull(effective_model):
            return

    print(f"\nStarting Handler server on {host}:{port}\n")
    logger.info("Initializing A2A server with push notification support...")

    effective_api_key = None
    if require_auth:
        effective_api_key = (
            api_key or os.getenv("HANDLER_API_KEY") or generate_api_key()
        )
        print(
            f"Authentication required!\n"
            f"API Key: {effective_api_key}\n"
            f"\nUse with Handler CLI:\n"
            f'  handler message send http://localhost:{port} "message" '
            f"--api-key {effective_api_key}\n"
        )

    agent = create_llm_agent(model=effective_model)
    agent_card = build_agent_card(agent, host, port, require_auth=require_auth)

    streaming_enabled = (
        agent_card.capabilities.streaming if agent_card.capabilities else False
    )
    push_notifications_enabled = (
        agent_card.capabilities.push_notifications if agent_card.capabilities else False
    )
    auth_enabled = agent_card.security_schemes is not None

    logger.info(
        "Agent card capabilities: streaming=%s, push_notifications=%s, auth=%s",
        streaming_enabled,
        push_notifications_enabled,
        auth_enabled,
    )

    a2a_application = create_a2a_application(agent, agent_card, effective_api_key)

    config = uvicorn.Config(a2a_application, host=host, port=port)
    server = uvicorn.Server(config)

    asyncio.run(server.serve())
