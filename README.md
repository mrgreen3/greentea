# greentea 🍵

An AI-native terminal setup for Wayland, built the Unix way: **foot** stays foot, AI lives in a small external companion that composes with it rather than a monolith trying to be both.

## Why the pivot

The original plan wrapped `xterm.js` in a Tauri shell. That fought against keeping things simple and light — a full web stack for a terminal, GPU acceleration foot proves you don't need, and a "beautiful as a webpage" aesthetic that isn't really what a terminal should chase anyway. This version adds only what's actually needed, on top of a terminal that's already one of the fastest around.

## Architecture

- **[foot](https://codeberg.org/dnkl/foot)** — untouched, upstream, configured via `foot.ini`. Pure C, Wayland-native, no XWayland, ~21MB idle. Sixel image support built in, so inline images are already solved with zero code.
- **the companion** — a small script/daemon (Python, matching greenclaw/beerfetch) triggered by foot's `pipe-visible` / `pipe-scrollback` keybindings. Receives scrollback, talks to [greenclaw](https://github.com/mrgreen3/greenclaw) (local Qwen/Ollama routing, Claude for heavier asks), returns a response.
- **response surface** — TBD: a `fuzzel`-style overlay (fast, in-and-out) vs. a small persistent popup window (more chat-like). Decide once the pipe → greenclaw round-trip works.

## AI, three layers (same shape as before, different plumbing)

1. **Sidebar-equivalent chat** — keybind pipes scrollback to the companion, response shown in an overlay
2. **Inline suggestions** — deferred; needs a shell-side hook (precmd/preexec), not a foot feature
3. **Agentic execution** — natural language → proposed command, shown as a diff, confirmed before it runs. Never silent — this is the one that can `rm -rf` someone.

## Status

Clean slate. Previous Tauri/xterm.js scaffold removed. Starting with `foot.ini` config and the companion script's pipe → greenclaw round-trip.

## License

Licensed under either of

- Apache License, Version 2.0 ([LICENSE-APACHE](LICENSE-APACHE))
- MIT license ([LICENSE-MIT](LICENSE-MIT))

at your option.
