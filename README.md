# Handler

[![CI](https://github.com/alDuncanson/handler/actions/workflows/ci.yml/badge.svg)](https://github.com/alDuncanson/handler/actions/workflows/ci.yml)
[![A2A Protocol](https://img.shields.io/badge/A2A_Protocol-v0.3.0-blue)](https://a2a-protocol.org/latest/)
[![GitHub release](https://img.shields.io/github/v/release/alDuncanson/handler)](https://github.com/alDuncanson/handler/releases)
[![PyPI version](https://img.shields.io/pypi/v/a2a-handler)](https://pypi.org/project/a2a-handler/)
[![GitHub stars](https://img.shields.io/github/stars/alDuncanson/handler)](https://github.com/alDuncanson/handler/stargazers)

An [A2A](https://a2a-protocol.org/latest/) Protocol client TUI and CLI.

![Handler TUI](https://github.com/alDuncanson/Handler/blob/b50274f45080c3b95de37f56937a17c1e82152a4/assets/handler-tui.png?raw=true)

## Install

Install with [uv](https://docs.astral.sh/uv/):

```bash
uv tool install a2a-handler
```

Or run directly without installing:

```bash
uvx --from a2a-handler handler
```

## Use

Then, you can use Handler:

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
