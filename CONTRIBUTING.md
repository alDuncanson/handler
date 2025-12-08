# Contributing to Handler

## Prerequisites

- **Python 3.11+**
- **[uv](https://github.com/astral-sh/uv)** for dependency management
- **[just](https://github.com/casey/just)** for running commands
- **[Ollama](https://ollama.com/)** for running the server agent

## Setup

```bash
git clone https://github.com/alDuncanson/handler.git
cd handler
just install
```

## Development

Run `just` to see all available commands.

## Code Style

- **Formatting**: `ruff format`
- **Linting**: `ruff check`
- **Type Checking**: `ty check`
- **Testing**: pytest
