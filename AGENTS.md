# Agent Development Guide

## Commands
Use `just` for all development tasks:

- **Verify**: `just check` (lint + format + typecheck)
- **Fix**: `just fix` (auto-fix lint/format)
- **Run Server**: `just server` (starts on port 8000)
- **Run TUI**: `just tui`
- **Run Web TUI**: `just web`
- **Run CLI**: `uv run handler`
- **Test**: `just test` (runs pytest)

## Project Structure

- **`packages/cli`**: `handler` CLI tool. Uses `rich` for output.
- **`packages/client`**: A2A protocol wrapper. Shared by CLI and TUI.
- **`packages/server`**: Reference agent server. Uses `google-adk` and `litellm`.
- **`src/handler`**: TUI application (Textual).

## Code Style & Conventions

- **Python 3.11+** with full type hints.
- **Formatting**: `ruff format` (black compatible).
- **Linting**: `ruff check`.
- **Type Checking**: `ty`.
- **Imports**: Standard -> Third-party -> Local.
- **Testing**: Add `pytest` tests for all new functionality.

## Environment

- **OLLAMA_API_BASE**: defaults to `http://localhost:11434`
- **OLLAMA_MODEL**: defaults to `qwen3`

## A2A Protocol

The `packages/client` library encapsulates A2A protocol logic.
- Use `fetch_agent_card` to retrieve agent metadata.
- Use `send_message_to_agent` for interactions.
