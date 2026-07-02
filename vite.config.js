import { defineConfig } from 'vite';

// Tauri expects a fixed port and relative asset paths
export default defineConfig({
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true
  },
  envPrefix: ['VITE_', 'TAURI_'],
  build: {
    target: 'esnext',
    minify: 'esbuild',
    sourcemap: true
  }
});
