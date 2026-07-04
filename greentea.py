"""
greentea — a persistent TUI chat client for greenclaw.

This is the skeleton stage (greentea#7): message log + input, proving
the UI loop works. No greenclaw wiring yet — that's blocked on
greenclaw#41 (local channel) and will be its own follow-up.

Run locally:
    python greentea.py

Run over SSH: works with zero changes — Textual apps read/write via
stdin/stdout escape sequences same as any TUI, nothing special needed.

Serve in a browser (e.g. for phone access):
    textual serve greentea.py
Then open the printed URL from any device on the same network.
"""

from datetime import datetime

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Header, Footer, Input, RichLog


class GreenteaApp(App):
    """Chat-shaped TUI. Message log on top, input pinned to the bottom."""

    CSS = """
    Screen {
        background: $surface;
    }

    #log {
        border: round $primary;
        margin: 1 1 0 1;
        padding: 0 1;
    }

    #message-input {
        margin: 0 1 1 1;
    }
    """

    BINDINGS = [
        ("ctrl+q", "quit", "Quit"),
        ("ctrl+l", "clear_log", "Clear"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical():
            yield RichLog(id="log", wrap=True, markup=True, highlight=False)
            yield Input(placeholder="Type a message and press Enter…", id="message-input")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "greentea"
        self.sub_title = "greenclaw chat — skeleton, no AI wired up yet"
        log = self.query_one("#log", RichLog)
        log.write("[dim]greentea skeleton running. No greenclaw connection yet — "
                   "messages just echo into this log for now.[/dim]")
        self.query_one("#message-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return

        log = self.query_one("#log", RichLog)
        timestamp = datetime.now().strftime("%H:%M")
        log.write(f"[bold cyan]you[/bold cyan] [dim]{timestamp}[/dim]  {text}")

        # Placeholder response so the loop is visibly a round-trip even
        # before greenclaw is wired in. Swap point: once greenclaw#41's
        # local channel exists, replace this with a real call and
        # write the actual response here instead.
        log.write(f"[bold green]greentea[/bold green] [dim]{timestamp}[/dim]  "
                  f"(no AI connected yet — echoing) {text}")

        event.input.value = ""

    def action_clear_log(self) -> None:
        self.query_one("#log", RichLog).clear()


def main() -> None:
    app = GreenteaApp()
    app.run()


if __name__ == "__main__":
    main()
