# Contributing to Handler

## Architecture

Handler is a [uv managed workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/) with five packages:

| Package | Name | Description |
|---------|------|-------------|
| `packages/cli` | `handler-cli` | CLI built with `click`. Entry point: `handler` |
| `packages/client` | `handler-client` | A2A protocol client library using `a2a-sdk` |
| `packages/common` | `handler-common` | Shared utilities (logging, printing with `rich`) |
| `packages/server` | `handler-server` | Reference A2A agent using `google-adk` + `litellm` |
| `src/handler` | `handler-app` | TUI application built with `textual` |

## Prerequisites

- **Python 3.11+**
- **[uv](https://github.com/astral-sh/uv)** for dependency management
- **[just](https://github.com/casey/just)** for running commands (recommended)
- **[Ollama](https://ollama.com/)** for running the reference server agent

## Setup

```bash
git clone https://github.com/alDuncanson/handler.git
cd handler
just install  # or: uv sync
```

## Development Commands

| Command | Description |
|---------|-------------|
| `just install` | Install dependencies |
| `just check` | Run lint, format, and typecheck |
| `just fix` | Auto-fix lint/format issues |
| `just test` | Run pytest test suite |
| `just server` | Start A2A server on port 8000 |
| `just tui` | Run TUI application |
| `just tui-dev` | Run TUI with Textual devtools |
| `just web` | Serve TUI as web app |
| `just console` | Run Textual devtools console |
| `just get-card [url]` | Fetch agent card from URL |
| `just send [url] [msg]` | Send message to agent |

## Code Style

- **Formatting**: `ruff format` (black compatible)
- **Linting**: `ruff check`
- **Type Checking**: `ty check`
- **Imports**: Standard → Third-party → Local
- **Testing**: Add `pytest` tests for new functionality

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_API_BASE` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `qwen3` | Model for reference agent |

## A2A Protocol

The `packages/client` library provides the A2A protocol implementation:

```python
from handler_client import build_http_client, fetch_agent_card, send_message_to_agent

async with build_http_client() as client:
    card = await fetch_agent_card("http://localhost:8000", client)
    response = await send_message_to_agent("http://localhost:8000", "Hello", client)
```
