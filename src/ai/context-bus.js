// The context bus is the shared state all three AI layers read from:
// sidebar chat, inline suggestions, and agentic execution. Keeping it
// centralized means the AI never has to re-derive "what's going on"
// from scratch on every request.
//
// TODO: replace the scrollback stub with a real ring buffer fed by
// PTY output events, and track cwd + last exit code from shell hooks
// (OSC 7 for cwd, a PROMPT_COMMAND/precmd hook for exit codes).

export class ContextBus {
  constructor(term) {
    this.term = term;
    this.cwd = null;
    this.lastExitCode = null;
    this.maxScrollbackLines = 200;
  }

  getRecentScrollback() {
    const buffer = this.term.buffer.active;
    const start = Math.max(0, buffer.length - this.maxScrollbackLines);
    const lines = [];
    for (let i = start; i < buffer.length; i++) {
      const line = buffer.getLine(i);
      if (line) lines.push(line.translateToString(true));
    }
    return lines.join('\n');
  }

  snapshot() {
    return {
      cwd: this.cwd,
      lastExitCode: this.lastExitCode,
      scrollback: this.getRecentScrollback()
    };
  }
}
