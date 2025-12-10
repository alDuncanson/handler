"""Footer component displaying keyboard shortcut buttons."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Button


class Footer(Container):
    """Custom footer with shortcut buttons."""

    def compose(self) -> ComposeResult:
        with Horizontal(classes="footer-buttons"):
            yield Button("Ctrl+Q Quit", id="footer-quit")
            yield Button("Ctrl+C Clear", id="footer-clear")
            yield Button("Ctrl+P Palette", id="footer-palette")

    def on_mount(self) -> None:
        self.border_title = "COMMANDS"
