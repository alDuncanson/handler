import pytest
from handler.tui import HandlerTUI


@pytest.mark.asyncio
async def test_app_startup():
    """Test that the app starts up and displays the initial state."""
    app = HandlerTUI()
    async with app.run_test() as _:
        assert app.query_one("#root-container")

        root = app.query_one("#root-container")
        assert "Disconnected" in str(root.border_title)

        disconnect_btn = app.query_one("#disconnect-btn")
        assert disconnect_btn.disabled is True
