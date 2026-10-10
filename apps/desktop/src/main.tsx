import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import DataShieldApp from '../../../frontend/src/App';
import { initializeRuntime } from '../../../frontend/src/features/runtime';
import '../../../frontend/src/i18n';
import '../../../frontend/src/index.css';

initializeRuntime();

createRoot(document.getElementById('root')!).render(<StrictMode><DataShieldApp /></StrictMode>);
