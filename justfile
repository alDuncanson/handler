# Handler Development Commands

# Default - show help
default:
    @just --list

# Install dependencies and set up environment
install:
    uv sync

# Run the reference agent server
server host="0.0.0.0" port="8000":
    uv run handler server --host {{host}} --port {{port}}

# Run the Handler TUI
tui:
    uv run handler tui

# Run the TUI in development mode (with Textual devtools support)
tui-dev:
    uv run textual run --dev handler.tui:HandlerTUI

# Serve the TUI for web access
web:
    uv run textual serve src/handler/tui.py

# Run the Textual console (for devtools)
console:
    uv run textual console

# Fetch an agent card (CLI)
get-card url="http://localhost:8000":
    uv run handler card {{url}}

# Send a message to an agent (CLI)
send url="http://localhost:8000" message="Hello":
    uv run handler send {{url}} "{{message}}"

# Run tests
test:
    uv run pytest

# Run all code quality checks (lint, format, typecheck)
check:
    @echo "Running linter..."
    uv run ruff check .
    @echo "\nChecking formatting..."
    uv run ruff format --check .
    @echo "\nRunning type checker..."
    uv run ty check
    @echo "\n✓ All checks passed!"

# Fix auto-fixable issues (lint & format)
fix:
    uv run ruff check --fix .
    uv run ruff format .

# Show the current version
version:
    uvx hatch version

# Create a git tag for the current version
tag:
    git tag "v$(uvx hatch version)"

# Tag and push the release to origin
release: tag
    git push origin "v$(uvx hatch version)"
