"""Handler - A2A protocol client and TUI for agent interaction"""

from importlib.metadata import version

from a2a_handler.tui import HandlerTUI, main

__version__ = version("a2a-handler")

__all__ = ["__version__", "HandlerTUI", "main"]
