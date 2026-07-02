// Layer 1: sidebar chat. Talks to greenclaw (local Qwen/Ollama routing,
// Claude for heavier asks) with the context bus snapshot attached to
// every message so it isn't starting cold.
//
// TODO: wire to greenclaw's existing interface instead of a bare
// Ollama/API call — reuse its routing rather than duplicating it.

export function initSidebar(contextBus) {
  const toggle = () => {
    document.getElementById('ai-sidebar').classList.toggle('collapsed');
  };

  window.addEventListener('keydown', (e) => {
    // Cmd/Ctrl+K toggles the sidebar, matches common command-palette muscle memory
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault();
      toggle();
    }
  });

  return { toggle };
}
