import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { copyFileSync, existsSync } from 'node:fs';

const legacyEntries = [
  'index-BZzIoI_2.js',
  'index-hRdbYNGT.js',
  'index-DyYmxPVv.js',
];

const legacyStyles = ['index-CMwXWZRz.css'];

export default defineConfig({
  plugins: [
    react(),
    {
      name: 'datashield-cache-compatibility',
      closeBundle() {
        const entry = 'dist/assets/app.js';
        const stylesheet = 'dist/assets/index.css';
        if (existsSync(entry)) {
          legacyEntries.forEach((name) => copyFileSync(entry, `dist/assets/${name}`));
        }
        if (existsSync(stylesheet)) {
          legacyStyles.forEach((name) => copyFileSync(stylesheet, `dist/assets/${name}`));
        }
      },
    },
  ],
  build: {
    rollupOptions: {
      output: {
        entryFileNames: 'assets/app.js',
        chunkFileNames: 'assets/[name].js',
        assetFileNames: 'assets/[name][extname]',
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
});
