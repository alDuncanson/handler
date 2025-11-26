"""Handler A2A server agent."""

import os

import click
import uvicorn
from dotenv import load_dotenv
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm
from handler_common import console, get_logger, setup_logging

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


def run_server(host: str, port: int) -> None:
    """Start the A2A server agent.

    Args:
        host: Host address to bind to
        port: Port number to bind to
    """
    console.print(
        f"\n[bold]Starting Handler server on [url]{host}:{port}[/url][/bold]\n"
    )
    log.info("Initializing A2A server...")
    agent = create_agent()
    a2a_app = to_a2a(agent, host=host, port=port)
    uvicorn.run(a2a_app, host=host, port=port)


@click.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=8000, help="Port to bind to")
def main(host: str, port: int) -> None:
    """CLI entry point."""
    run_server(host, port)


if __name__ == "__main__":
    main()
