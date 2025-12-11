"""A2A server agent with streaming, push notifications, and knowledge base.

Provides a local A2A-compatible agent server for testing and development,
with Qdrant-backed semantic search for A2A protocol expertise.
"""

import asyncio
from contextlib import AsyncExitStack
import os
import secrets
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
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools import BaseTool
from mcp import StdioServerParameters
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from a2a_handler.common import console, get_logger, setup_logging
from a2a_handler.knowledge import get_mcp_server_env, initialize_knowledge_base

setup_logging(level="INFO", suppress_libs=["uvicorn", "google", "httpcore", "httpx"])
logger = get_logger(__name__)

DEFAULT_OLLAMA_API_BASE = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "qwen3"
DEFAULT_HTTP_TIMEOUT_SECONDS = 30


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
        "/",
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


async def get_mcp_tools_async(
    exit_stack: AsyncExitStack,
) -> list[BaseTool]:
    """Get MCP tools from the Qdrant knowledge base server.

    Uses the exit_stack pattern to properly manage the MCP connection lifecycle.

    Args:
        exit_stack: AsyncExitStack to manage MCP connection cleanup

    Returns:
        List of MCP tools from the Qdrant server
    """
    env = get_mcp_server_env()

    server_params = StdioServerParameters(
        command="uvx",
        args=["mcp-server-qdrant"],
        env=env,
    )

    toolset = McpToolset(
        connection_params=StdioConnectionParams(
            server_params=server_params,
            timeout=60,
        ),
    )

    exit_stack.push_async_callback(toolset.close)
    tools = await toolset.get_tools()
    return tools


async def create_llm_agent_async(
    exit_stack: AsyncExitStack,
    use_knowledge_base: bool = True,
) -> Agent:
    """Create and configure the A2A test agent using LiteLLM with Ollama.

    Args:
        exit_stack: AsyncExitStack to manage MCP connection cleanup
        use_knowledge_base: Whether to include knowledge base tools

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

    tools: list[BaseTool] = []
    if use_knowledge_base:
        mcp_tools = await get_mcp_tools_async(exit_stack)
        tools.extend(mcp_tools)
        logger.info(
            "Knowledge base tools enabled via Qdrant MCP server (%d tools)",
            len(mcp_tools),
        )

    instruction = """You are Handler's Agent, the built-in assistant for the Handler application and an expert on the A2A (Agent-to-Agent) protocol.

## About Handler

Handler is an A2A protocol client published on PyPI as `a2a-handler`. It provides tools for developers to communicate with, test, and debug A2A-compatible agents.

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

## Your Capabilities

You have access to a knowledge base about the A2A protocol specification and Handler documentation. Use the `qdrant-find` tool to search for relevant information when answering questions about:
- A2A protocol concepts, methods, and data structures
- Handler CLI commands and usage
- Agent Card configuration
- Task lifecycle and states
- Authentication and security
- Streaming and push notifications

When you learn new information that should be remembered, use the `qdrant-store` tool to save it.

## Guidelines

- Be helpful, concise, and accurate
- Search the knowledge base before answering technical questions
- Provide code examples when helpful
- Explain A2A concepts clearly for both beginners and experts
- If you're unsure about something, say so and suggest where to find more information"""

    agent = Agent(
        name="Handler",
        model=language_model,
        description="Handler's A2A Protocol Expert Agent - answers questions about A2A and Handler",
        instruction=instruction,
        tools=tools or None,
    )

    logger.info(
        "[success]Agent created successfully:[/success] [agent]%s[/agent]", agent.name
    )
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
            id="a2a_expert",
            name="A2A Protocol Expert",
            description="Answers questions about the A2A protocol specification, concepts, methods, and best practices",
            tags=["a2a", "protocol", "specification", "expert"],
            examples=[
                "What is the A2A protocol?",
                "Explain the Task lifecycle in A2A",
                "What methods does A2A support?",
                "How does authentication work in A2A?",
            ],
        ),
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


async def _run_server_async(
    host: str,
    port: int,
    require_auth: bool,
    effective_api_key: str | None,
    init_knowledge: bool,
) -> None:
    """Internal async server runner with proper MCP cleanup.

    Args:
        host: Host address to bind to
        port: Port number to bind to
        require_auth: Whether to require API key authentication
        effective_api_key: API key to use for authentication
        init_knowledge: Whether to include knowledge base tools
    """
    async with AsyncExitStack() as exit_stack:
        agent = await create_llm_agent_async(
            exit_stack, use_knowledge_base=init_knowledge
        )
        agent_card = build_agent_card(agent, host, port, require_auth=require_auth)

        streaming_enabled = (
            agent_card.capabilities.streaming if agent_card.capabilities else False
        )
        push_notifications_enabled = (
            agent_card.capabilities.push_notifications
            if agent_card.capabilities
            else False
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

        try:
            await server.serve()
        finally:
            logger.info("Server shutting down, cleaning up MCP connections...")


def run_server(
    host: str,
    port: int,
    require_auth: bool = False,
    api_key: str | None = None,
    init_knowledge: bool = True,
) -> None:
    """Start the A2A server agent.

    Args:
        host: Host address to bind to
        port: Port number to bind to
        require_auth: Whether to require API key authentication
        api_key: Specific API key to use (generated if not provided and auth required)
        init_knowledge: Whether to initialize the knowledge base on startup
    """
    console.print(
        f"\n[bold]Starting Handler server on [url]{host}:{port}[/url][/bold]\n"
    )
    logger.info("Initializing A2A server with push notification support...")

    if init_knowledge:
        logger.info("Initializing knowledge base...")
        asyncio.run(initialize_knowledge_base())

    effective_api_key = None
    if require_auth:
        effective_api_key = (
            api_key or os.getenv("HANDLER_API_KEY") or generate_api_key()
        )
        console.print(
            f"[bold yellow]Authentication required![/bold yellow]\n"
            f"API Key: [bold green]{effective_api_key}[/bold green]\n"
            f"\nUse with Handler CLI:\n"
            f'  [dim]handler message send http://localhost:{port} "message" '
            f"--auth-type api-key --auth-value {effective_api_key}[/dim]\n"
        )

    asyncio.run(
        _run_server_async(
            host=host,
            port=port,
            require_auth=require_auth,
            effective_api_key=effective_api_key,
            init_knowledge=init_knowledge,
        )
    )
