# Handler

[![CI](https://github.com/alDuncanson/handler/actions/workflows/ci.yml/badge.svg)](https://github.com/alDuncanson/handler/actions/workflows/ci.yml)

An [A2A](https://a2a-protocol.org/latest/) Protocol client TUI and CLI.

![Handler TUI](./assets/handler-tui.png)

## Run

This project is managed with [uv](https://docs.astral.sh/uv/), so you can run Handler in a temporary, isolated environment:

```bash
uvx git+https://github.com/alDuncanson/handler
```

or, install it globally:

```bash
uv tool install git+https://github.com/alDuncanson/handler
```

## Use

Now you can use Handler:

```bash
handler
```

If you don't have an A2A server to connect to, Handler provides a local A2A server agent:

```bash
handler server
```

> The server agent requires [Ollama](https://ollama.com/) to be running locally. By default it connects to `http://localhost:11434` and uses the `qwen3` model.
>
> 1. Install and run Ollama
> 2. Pull the model: `ollama pull qwen3`
> 3. (Optional) Configure via environment variables: `OLLAMA_API_BASE` and `OLLAMA_MODEL`

### TUI

Interactive terminal user interface:

```bash
handler tui
```

### CLI

Fetch agent card from A2A server:

```bash
handler card http://localhost:8000
```

Send a message to an A2A agent:

```bash
handler send http://localhost:8000 "Hello World"
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for architecture and development instructions.
