"""
Headless smoke test — proves the app boots, accepts input, and the
message log updates, without needing a real TTY. Run with:
    python test_greentea.py
"""

import asyncio
from greentea import GreenteaApp
from textual.widgets import RichLog, Input


async def smoke_test():
    app = GreenteaApp()
    async with app.run_test() as pilot:
        # App mounted without raising — first real check.
        log = app.query_one("#log", RichLog)
        input_widget = app.query_one("#message-input", Input)
        assert input_widget.has_focus, "input should be focused on mount"

        # Type a message and submit it.
        await pilot.click("#message-input")
        for ch in "hello greentea":
            await pilot.press(*[ch])
        await pilot.press("enter")
        await pilot.pause()

        assert input_widget.value == "", "input should clear after submit"
        # RichLog doesn't expose plain text easily, but line count is a
        # reasonable proxy that both the "you" and echo lines got written.
        assert len(log.lines) >= 3, f"expected at least 3 log lines, got {len(log.lines)}"

        print("OK: app mounted, accepted input, log updated, input cleared.")


if __name__ == "__main__":
    asyncio.run(smoke_test())
