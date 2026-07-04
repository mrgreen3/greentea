"""
greentea — a persistent TUI chat client for greenclaw.

Run locally:
    python greentea.py

Serve in a browser (LAN):
    ./serve.sh
"""

import json
from datetime import datetime

import httpx
from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Header, Footer, Input, RichLog
from textual import work


OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "gemma4:cloud"


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
    ]

    def __init__(self):
        super().__init__()
        self._history: list[dict] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical():
            yield RichLog(id="log", wrap=True, markup=True, highlight=False)
            yield Input(placeholder="Type a message and press Enter…", id="message-input")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "greentea"
        self.sub_title = MODEL
        log = self.query_one("#log", RichLog)
        log.write(f"[dim]Connected to {MODEL} via Ollama.[/dim]")
        self.query_one("#message-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return

        event.input.value = ""

        if text == "/clear":
            self.action_clear_log()
            return

        log = self.query_one("#log", RichLog)
        timestamp = datetime.now().strftime("%H:%M")
        log.write(f"[bold cyan]you[/bold cyan] [dim]{timestamp}[/dim]  {text}")

        self._history.append({"role": "user", "content": text})
        event.input.disabled = True
        event.input.placeholder = "Waiting for response…"

        self._fetch_response(list(self._history), timestamp)

    @work(exclusive=False, thread=True)
    def _fetch_response(self, history: list[dict], timestamp: str) -> None:
        log = self.query_one("#log", RichLog)
        input_widget = self.query_one("#message-input", Input)
        chunks: list[str] = []

        try:
            with httpx.stream(
                "POST",
                OLLAMA_URL,
                json={"model": MODEL, "messages": history, "stream": True},
                timeout=120.0,
            ) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    chunk = data.get("message", {}).get("content", "")
                    if chunk:
                        chunks.append(chunk)
                    if data.get("done"):
                        break

            response_text = "".join(chunks)
            self._history.append({"role": "assistant", "content": response_text})

            self.call_from_thread(
                log.write,
                f"[bold green]greentea[/bold green] [dim]{timestamp}[/dim]  {response_text}",
            )

        except Exception as e:
            self.call_from_thread(log.write, f"[bold red]error[/bold red]  {e}")

        def re_enable():
            input_widget.disabled = False
            input_widget.placeholder = "Type a message and press Enter…"
            input_widget.focus()

        self.call_from_thread(re_enable)

    def action_clear_log(self) -> None:
        self._history.clear()
        log = self.query_one("#log", RichLog)
        log.clear()
        log.write(f"[dim]Connected to {MODEL} via Ollama.[/dim]")


def main() -> None:
    app = GreenteaApp()
    app.run()


if __name__ == "__main__":
    main()
