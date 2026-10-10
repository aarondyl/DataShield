import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { initializeRuntime } from './features/runtime';
import './index.css';
import './i18n';

initializeRuntime();

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
