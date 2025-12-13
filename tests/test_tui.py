"""Tests for the TUI application."""

import pytest

from a2a_handler.tui import HandlerTUI


@pytest.mark.asyncio
async def test_app_startup():
    """Test that the app starts up and displays the initial state."""
    app = HandlerTUI()
    async with app.run_test() as _:
        assert app.query_one("#root-container")
