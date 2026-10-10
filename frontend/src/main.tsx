import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { initializeRuntime } from './runtime';
import './index.css';
import './i18n';

// Set the runtime mode before App renders. The mode selects the HashRouter,
// Rust's authenticated local API bridge, and local workspace flows. Without
// this marker a packaged Tauri window falls back to browser API requests.
initializeRuntime();

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
