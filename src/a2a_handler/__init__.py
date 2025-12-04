"""Handler - A2A protocol client and TUI for agent interaction"""

from a2a_handler._version import __version__
from a2a_handler.tui import HandlerTUI, main

__all__ = ["__version__", "HandlerTUI", "main"]
