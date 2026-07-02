import { Terminal } from '@xterm/xterm';
import { WebglAddon } from '@xterm/addon-webgl';
import { FitAddon } from '@xterm/addon-fit';
import { SearchAddon } from '@xterm/addon-search';
import { Unicode11Addon } from '@xterm/addon-unicode11';
import { invoke } from '@tauri-apps/api/core';
import '@xterm/xterm/css/xterm.css';

import { ContextBus } from './ai/context-bus.js';
import { initSidebar } from './ai/sidebar.js';
import { initSuggestions } from './ai/suggestions.js';

const term = new Terminal({
  fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
  fontSize: 14,
  cursorBlink: true,
  cursorStyle: 'bar',
  allowTransparency: true,
  theme: {
    background: '#00000000', // let the CSS glass background show through
    foreground: '#e8e6e1',
    cursor: '#8fd6a8'
  }
});

const fitAddon = new FitAddon();
term.loadAddon(fitAddon);
term.loadAddon(new SearchAddon());
term.loadAddon(new Unicode11Addon());

term.open(document.getElementById('terminal'));

// WebGL addon can lose its context (OOM, suspend/resume); fall back
// gracefully rather than leaving the terminal blank.
try {
  const webgl = new WebglAddon();
  webgl.onContextLoss(() => webgl.dispose());
  term.loadAddon(webgl);
} catch (e) {
  console.warn('WebGL renderer unavailable, falling back to canvas', e);
}

fitAddon.fit();
window.addEventListener('resize', () => fitAddon.fit());

const contextBus = new ContextBus(term);
initSidebar(contextBus);
initSuggestions(term, contextBus);

// Sanity check that Tauri IPC is wired up; replaced by real PTY
// spawn/write/resize commands once lib.rs grows them.
invoke('greeting').then((msg) => {
  term.writeln(`\x1b[90m${msg}\x1b[0m`);
  term.writeln("\x1b[90mPTY not wired up yet \u2014 this is a scaffold.\x1b[0m");
});
