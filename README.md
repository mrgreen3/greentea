# greentea 🍵

An AI-native terminal for Wayland. Built on `xterm.js` (WebGL-accelerated) inside a Tauri shell, with a layered AI system baked in rather than bolted on.

## Why

Most terminals are either fast and ugly, or pretty and slow. greentea targets both: GPU-accelerated rendering via `@xterm/addon-webgl`, native Wayland via Tauri (no Electron, no XWayland dependency), and AI that actually understands what's on your screen.

## AI, three layers deep

1. **Sidebar chat** — ask questions about your terminal session, greenclaw/Ollama-backed
2. **Inline suggestions** — ghost-text completions as you type, low-latency local model
3. **Agentic execution** — natural language → proposed command, shown as a diff, confirmed before it runs (never silent)

All three share one context bus: cwd, scrollback, exit codes, shell history — so the AI isn't starting from zero every time you ask it something.

## Stack

- **Shell:** Tauri 2 (Rust), `x11` feature disabled — pure Wayland
- **Terminal:** `@xterm/xterm` + `@xterm/addon-webgl`, `addon-fit`, `addon-search`, `addon-unicode11`
- **PTY:** `portable-pty` (Rust), spawned in-process, streamed over Tauri IPC
- **AI backend:** [greenclaw](https://github.com/mrgreen3/greenclaw) (local Qwen via Ollama for routing/suggestions, Claude for heavier lifting)

## Status

PTY wired: real shell behind the terminal, spawn/write/resize over IPC. AI context bus is next.

## Structure

```
src-tauri/     Rust backend: PTY spawn, IPC commands, window config
src/           Frontend: xterm.js terminal, AI panel, theming
src/ai/        Context bus, greenclaw client, suggestion engine
```

## License

Licensed under either of

- Apache License, Version 2.0 ([LICENSE-APACHE](LICENSE-APACHE))
- MIT license ([LICENSE-MIT](LICENSE-MIT))

at your option, matching the upstream Tauri project.
