import { Terminal } from '@xterm/xterm';
import { WebglAddon } from '@xterm/addon-webgl';
import { FitAddon } from '@xterm/addon-fit';
import { SearchAddon } from '@xterm/addon-search';
import { Unicode11Addon } from '@xterm/addon-unicode11';
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import '@xterm/xterm/css/xterm.css';

import { ContextBus } from './ai/context-bus.js';
import { initSidebar } from './ai/sidebar.js';
import { initSuggestions } from './ai/suggestions.js';

const term = new Terminal({
  fontFamily: "'JetBrainsMono Nerd Font Mono', 'FiraCode Nerd Font', 'Fira Code', monospace",
  fontSize: 14,
  cursorBlink: true,
  cursorStyle: 'bar',
  allowTransparency: true,
  allowProposedApi: true, // required by the Unicode11 addon
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

term.onData((data) => invoke('write_pty', { data }));
term.onResize(({ cols, rows }) => invoke('resize_pty', { cols, rows }));

// Register the output listener before spawning so early output isn't lost.
listen('pty://output', (event) => term.write(event.payload))
  .then(() => invoke('spawn_pty', { cols: term.cols, rows: term.rows }))
  .catch((e) => term.writeln(`\x1b[31mfailed to start shell: ${e}\x1b[0m`));
