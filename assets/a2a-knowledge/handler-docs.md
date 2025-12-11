# Handler Documentation - Knowledge Base

Handler is an A2A (Agent-to-Agent) protocol client published on PyPI as `a2a-handler`. It provides tools for developers to communicate with, test, and debug A2A-compatible agents.

## Installation

```bash
uv tool install a2a-handler
```

## Architecture

Handler consists of four main components:

### 1. TUI (Terminal User Interface)
An interactive Textual-based terminal interface for:
- Managing agent connections
- Sending messages
- Viewing streaming responses
- Managing sessions

Launch with: `handler`

### 2. CLI (Command Line Interface)
A rich-click powered CLI for scripting and automation.

### 3. A2AService
A unified service layer wrapping the a2a-sdk for protocol operations.

### 4. Server Agent
A local A2A-compatible agent for testing, built with Google ADK and LiteLLM/Ollama.

## CLI Commands

### Message Commands
```bash
# Send a message to an agent
handler message send <agent_url> "Your message"

# Stream a message with real-time updates
handler message stream <agent_url> "Your message"

# With authentication
handler message send <agent_url> "message" --auth-type bearer --auth-value <token>
handler message send <agent_url> "message" --auth-type api-key --auth-value <key>
```

### Task Commands
```bash
# Get task status
handler task get <agent_url> <task_id>

# Cancel a task
handler task cancel <agent_url> <task_id>

# Resubscribe to task updates
handler task resubscribe <agent_url> <task_id>
```

### Card Commands
```bash
# Get agent card
handler card get <agent_url>

# Validate agent card
handler card validate <agent_url>
```

### Session Commands
```bash
# List sessions
handler session list

# Show session details
handler session show <session_id>

# Clear sessions
handler session clear
```

### Server Commands
```bash
# Start the local server agent
handler server agent --host 0.0.0.0 --port 8000

# Start push notification server
handler server push --port 8001
```

## Authentication Support

Handler supports multiple authentication methods:

### Bearer Token
```bash
handler message send <url> "message" --auth-type bearer --auth-value "your-token"
```

### API Key
```bash
handler message send <url> "message" --auth-type api-key --auth-value "your-key"
```

### Basic Auth
```bash
handler message send <url> "message" --auth-type basic --auth-value "user:password"
```

## Server Agent Configuration

The server agent uses environment variables:

```bash
# Ollama configuration
OLLAMA_API_BASE=http://localhost:11434
OLLAMA_MODEL=qwen3

# Server configuration (via CLI flags)
--host 0.0.0.0
--port 8000
```

## Features

### Streaming Responses
Handler supports SSE streaming for real-time updates from agents that have `capabilities.streaming: true`.

### Push Notifications
Support for webhook-based async task updates from agents with `capabilities.pushNotifications: true`.

### Session Persistence
Handler maintains session state for continuing conversations with agents.

### Output Formats
- Formatted text output (default)
- JSON output with `--json` flag

## Common Workflows

### Testing a Local Agent
```bash
# Terminal 1: Start server agent
handler server agent --port 8000

# Terminal 2: Send messages
handler message send http://localhost:8000 "Hello, what can you do?"
handler message stream http://localhost:8000 "Tell me about A2A"
```

### Validating Agent Card
```bash
handler card get https://agent.example.com
handler card validate https://agent.example.com
```

### Working with Tasks
```bash
# Send message and get task ID
handler message send <url> "Long running task"

# Check task status
handler task get <url> <task_id>

# Cancel if needed
handler task cancel <url> <task_id>
```

## Error Handling

Handler provides clear error messages for:
- Connection failures
- Authentication errors (401, 403)
- Invalid agent cards
- Task not found errors
- Unsupported operations

## Tips

1. Use `--json` for scripting and automation
2. Use streaming (`message stream`) for long responses
3. Always validate agent cards before integration
4. Use environment variables for credentials in production
