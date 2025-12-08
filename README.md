# Handler

[![CI](https://github.com/alDuncanson/handler/actions/workflows/ci.yml/badge.svg)](https://github.com/alDuncanson/handler/actions/workflows/ci.yml)
[![A2A Protocol](https://img.shields.io/badge/A2A_Protocol-v0.3.0-blue)](https://a2a-protocol.org/latest/)
[![PyPI version](https://img.shields.io/pypi/v/a2a-handler)](https://pypi.org/project/a2a-handler/)
[![PyPI - Status](https://img.shields.io/pypi/status/a2a-handler)](https://pypi.org/project/a2a-handler/)
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

```bash
handler --help
```

To start a local A2A server agent (requires [Ollama](https://ollama.com/)):

```bash
handler server
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
