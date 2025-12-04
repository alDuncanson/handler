# Agent Development Guide

## Commands
Use `just` for all development tasks:

| Command | Description |
|---------|-------------|
| `just install` | Install dependencies |
| `just check` | Run lint, format, and typecheck |
| `just fix` | Auto-fix lint/format issues |
| `just test` | Run pytest test suite |
| `just server` | Start A2A server (port 8000) |
| `just tui` | Run TUI application |
| `just tui-dev` | Run TUI with Textual devtools |
| `just web` | Serve TUI as web app |
| `just console` | Run Textual devtools console |
| `just get-card` | Fetch agent card (CLI) |
| `just send` | Send message to agent (CLI) |
| `just version` | Show current version |

## Project Structure

```
handler/
├── src/a2a_handler/     # Main package
│   ├── _version.py      # Version string
│   ├── cli.py           # CLI (click)
│   ├── client.py        # A2A protocol client (a2a-sdk)
│   ├── server.py        # A2A server agent (google-adk, litellm)
│   ├── tui.py           # TUI application (textual)
│   ├── common/          # Shared utilities (rich, logging)
│   │   ├── logging.py
│   │   └── printing.py
│   └── components/      # TUI components
└── tests/               # pytest tests
```

## Code Style & Conventions

- **Python 3.11+** with full type hints
- **Formatting**: `ruff format` (black compatible)
- **Linting**: `ruff check`
- **Type Checking**: `ty check`
- **Imports**: Standard → Third-party → Local
- **Testing**: pytest with pytest-asyncio for async tests

## Environment Variables

- `OLLAMA_API_BASE`: Ollama server URL (default: `http://localhost:11434`)
- `OLLAMA_MODEL`: Model to use (default: `qwen3`)

## A2A Protocol

The `a2a_handler.client` module provides A2A protocol logic:
- `build_http_client()` - Create configured HTTP client
- `fetch_agent_card()` - Retrieve agent metadata
- `send_message_to_agent()` - Send messages and get responses

## Key Dependencies

- **CLI**: `click`
- **Client**: `a2a-sdk`, `httpx`
- **Server**: `google-adk`, `litellm`, `uvicorn`
- **TUI**: `textual`
- **Common**: `rich`
