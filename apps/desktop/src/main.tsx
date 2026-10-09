import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import DataShieldApp from '../../../frontend/src/App';
import '../../../frontend/src/i18n';
import '../../../frontend/src/index.css';

window.datashieldDesktop = true;

createRoot(document.getElementById('root')!).render(<StrictMode><DataShieldApp /></StrictMode>);
