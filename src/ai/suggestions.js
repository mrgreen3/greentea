// Layer 2: inline ghost-text suggestions as you type, and
// Layer 3: agentic execution (natural language -> proposed command).
//
// These are latency-sensitive and safety-sensitive respectively, so
// they're kept separate from the sidebar chat path:
//   - suggestions want the fastest local model available, debounced
//   - agentic commands must always render as a diff/preview and
//     require explicit confirmation before touching the PTY. No
//     silent execution, ever — this is the one that can rm -rf someone.
//
// TODO: implement debounced suggestion fetch, and a confirm-before-run
// UI (likely a modal or inline block, not just an Enter-to-accept).

export function initSuggestions(term, contextBus) {
  // stub
}
