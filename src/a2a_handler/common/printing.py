"""Unified Rich printing configuration for Handler packages."""

from typing import Literal

from rich.markdown import Markdown
from rich.panel import Panel
from rich.json import JSON

from .logging import console

BorderStyle = Literal["green", "blue", "yellow", "red", "cyan", "magenta", "dim"]


def print_panel(
    content: str,
    title: str | None = None,
    border_style: BorderStyle = "green",
    expand: bool = False,
    markdown: bool = False,
) -> None:
    """Print content in a Rich panel.

    Args:
        content: The content to display
        title: Optional panel title
        border_style: Border color/style
        expand: Whether to expand panel to full width
        markdown: Whether to render content as markdown
    """
    renderable = Markdown(content) if markdown else content
    console.print(
        Panel(renderable, title=title, border_style=border_style, expand=expand)
    )


def print_info(content: str, title: str | None = None) -> None:
    """Print an info panel (cyan border)."""
    print_panel(content, title=title, border_style="cyan")


def print_success(content: str, title: str | None = None) -> None:
    """Print a success panel (green border)."""
    print_panel(content, title=title, border_style="green")


def print_warning(content: str, title: str | None = None) -> None:
    """Print a warning panel (yellow border)."""
    print_panel(content, title=title, border_style="yellow")


def print_error(content: str, title: str | None = None) -> None:
    """Print an error panel (red border)."""
    print_panel(content, title=title, border_style="red")


def print_json(data: str, title: str | None = None) -> None:
    """Print JSON in a panel with structural highlighting.

    Args:
        data: JSON string to display
        title: Optional panel title
    """
    json_renderable = JSON(data, highlight=False)
    console.print(
        Panel(json_renderable, title=title, border_style="green", expand=False)
    )


def print_markdown(
    content: str, title: str | None = None, border_style: BorderStyle = "green"
) -> None:
    """Print markdown content in a panel.

    Args:
        content: Markdown content to display
        title: Optional panel title
        border_style: Border color/style
    """
    print_panel(content, title=title, border_style=border_style, markdown=True)
