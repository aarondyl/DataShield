import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Local API is never proxied from the renderer in Desktop mode. The Rust host
// owns the runtime token and exposes a deliberately narrow invoke bridge.
export default defineConfig({
  plugins: [react()],
  // Reuse the shared product UI brand assets in the installed Desktop bundle.
  publicDir: '../../frontend/public',
  clearScreen: false,
  resolve: {
    // The renderer reuses components from ../../frontend/src while its entry
    // point lives in apps/desktop. Resolve both trees to the Desktop React
    // runtime so ReactDOM and every shared component use one hook dispatcher.
    dedupe: ['react', 'react-dom'],
  },
  server: {
    port: 1420,
    strictPort: true,
  },
});
