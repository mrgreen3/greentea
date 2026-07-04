# greentea 🍵

A persistent TUI chat client for [greenclaw](https://github.com/mrgreen3/greenclaw) — greenclaw's own dedicated terminal, usable on desktop, laptop, or phone.

## History of the pivot(s), for context

1. **v0 (abandoned):** `xterm.js` in a Tauri shell — GPU-accelerated, "beautiful as a webpage." Fought against keeping things simple and light; scaffold deleted.
2. **v1 (abandoned):** foot (unmodified, upstream) as the terminal, with a companion script piping scrollback to a keybind, showing AI replies via walker's dmenu. Unix-philosophy-correct, but walker is ephemeral by design — every reply meant open→read→close, never a real conversation. Fine for a one-shot lookup, wrong shape for a chat client.
3. **v2 (current):** drop the pipe-and-popup pattern entirely. Build greentea as an actual persistent chat TUI using [Textual](https://textual.textualize.io/) — scrolling message history, a fixed input line, real back-and-forth — the same shape as Claude Code's terminal interface, just talking to greenclaw instead.

## Why Textual specifically

One codebase, three ways to reach it:
- **Local terminal** — runs in foot on desktop/laptop like any TUI
- **SSH** — Textual apps work over SSH natively, no extra code
- **Browser** — `textual serve` turns the same app into a websocket-based web app; a phone browser can use it with zero install

"Desktop, laptop, or phone at a push" isn't a stretch feature here, it's close to Textual's default behavior.

## Architecture

- **greentea** (this repo) — the Textual TUI: message log widget, input box, talks to greenclaw over a local channel
- **[greenclaw](https://github.com/mrgreen3/greenclaw)** — the actual AI backend (local Qwen/Ollama routing, Claude for heavier asks, skills, Kev Wiki context). Needs a local channel (Unix socket or `localhost` HTTP) alongside its existing Telegram interface — greentea is the first real consumer of that, see greenclaw#41.
- **foot** — just the terminal greentea happens to run in on desktop. Not a dependency of greentea itself; anything that can run a TUI works.

## AI, three layers (same shape as always, now on the right foundation)

1. **Chat** — the core of greentea itself: persistent thread, not a one-shot query
2. **Inline suggestions** — deferred; needs shell-side hooks, separate concern from the chat client
3. **Agentic execution** — natural language → proposed command, shown as a diff, confirmed before it runs. Never silent — this is the one that can `rm -rf` someone.

## Status

Clean slate, second time. Previous foot.ini + walker companion script removed. Starting with the Textual app skeleton — message log + input, wired to greenclaw once its local channel exists.

## License

Licensed under either of

- Apache License, Version 2.0 ([LICENSE-APACHE](LICENSE-APACHE))
- MIT license ([LICENSE-MIT](LICENSE-MIT))

at your option.
