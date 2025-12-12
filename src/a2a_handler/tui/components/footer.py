"""Footer component displaying keyboard shortcut buttons."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Button


class Footer(Container):
    """Custom footer with shortcut buttons."""

    ALLOW_MAXIMIZE = False

    def compose(self) -> ComposeResult:
        with Horizontal(classes="footer-buttons"):
            yield Button("Ctrl+Q Quit", id="footer-quit")
            yield Button("Ctrl+C Clear", id="footer-clear")
            yield Button("Ctrl+P Palette", id="footer-palette")
            yield Button("Ctrl+M Maximize", id="footer-maximize")

    def on_mount(self) -> None:
        self.border_title = "COMMANDS"
        self.query_one("#footer-maximize", Button).display = False

    def show_maximize_button(self, show: bool) -> None:
        """Show or hide the maximize button."""
        self.query_one("#footer-maximize", Button).display = show
