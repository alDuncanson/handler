# Contributing to Handler

## Architecture

Handler is a [uv managed workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/) with four main components:

- **`packages/cli`** (`handler-cli`): The command-line interface, built with `click` and `rich`. It serves as the main entry point (`handler`) for all operations.
- **`src/handler`** (`handler-app`): The TUI application, built with `Textual`. It provides a rich, interactive dashboard for agent communication.
- **`packages/client`** (`handler-client`): A shared library implementing the A2A protocol client logic (HTTP/JSON).
- **`packages/server`** (`handler-server`): A reference A2A server agent implementation using `google-adk` and `litellm`, used for testing and development.

## Development

### Prerequisites
- **Python 3.11+**
- **[uv](https://github.com/astral-sh/uv)** (required for dependency management)
- **[just](https://github.com/casey/just)** (recommended for running commands)

### Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/alDuncanson/handler.git
    cd handler
    ```

2.  **Install dependencies:**
    ```bash
    just install
    # Or: uv sync
    ```

### Commands

Use `just` to manage the development lifecycle:

| Command | Description |
|---------|-------------|
| `just install` | Install dependencies and setup environment |
| `just check` | Run lint, format, and type checks |
| `just test` | Run the test suite |
| `just tui-dev` | Run TUI in dev mode with live editing support |
| `just web` | Serve TUI as a web application |
| `just console` | Run Textual devtools console |
