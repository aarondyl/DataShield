import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Local API is never proxied from the renderer in Desktop mode. The Rust host
// owns the runtime token and exposes a deliberately narrow invoke bridge.
export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
  },
});
