"""
Headless smoke tests. Run with:
    python test_greentea.py
"""

import asyncio
from unittest.mock import patch, MagicMock
from greentea import GreenteaApp
from textual.widgets import RichLog, Input


async def smoke_test():
    app = GreenteaApp()
    async with app.run_test() as pilot:
        log = app.query_one("#log", RichLog)
        input_widget = app.query_one("#message-input", Input)

        assert input_widget.has_focus, "input should be focused on mount"
        assert len(log.lines) >= 1, "welcome line should be present"

        # Typing with no text submitted does nothing
        await pilot.press("enter")
        assert not input_widget.disabled, "empty submit should not disable input"

        print("OK: app mounted, focused, empty submit ignored.")


async def mock_ollama_test():
    """Submit a message with Ollama mocked to avoid real network calls."""
    import httpx

    fake_response_lines = [
        b'{"message":{"role":"assistant","content":"Hi"},"done":false}\n',
        b'{"message":{"role":"assistant","content":" there"},"done":false}\n',
        b'{"message":{"role":"assistant","content":""},"done":true}\n',
    ]

    class FakeStream:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def raise_for_status(self): pass
        def iter_lines(self):
            for line in fake_response_lines:
                yield line.decode().strip()

    app = GreenteaApp()
    async with app.run_test() as pilot:
        input_widget = app.query_one("#message-input", Input)
        log = app.query_one("#log", RichLog)

        with patch("httpx.stream", return_value=FakeStream()):
            await pilot.click("#message-input")
            for ch in "hello":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause(1.0)

        assert input_widget.value == "", "input should clear after submit"
        # Give background worker time to write response
        for _ in range(20):
            await pilot.pause(0.1)
            if not input_widget.disabled:
                break

        assert not input_widget.disabled, "input should re-enable after response"
        assert len(app._history) == 2, f"history should have user+assistant, got {len(app._history)}"
        assert app._history[1]["content"] == "Hi there", f"unexpected response: {app._history[1]['content']}"

        print("OK: message submitted, response received, history updated.")


if __name__ == "__main__":
    asyncio.run(smoke_test())
    asyncio.run(mock_ollama_test())
    print("All tests passed.")
