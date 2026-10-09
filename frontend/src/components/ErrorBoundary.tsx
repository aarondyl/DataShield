import { Component, type ErrorInfo, type ReactNode } from 'react';
import i18n from '../i18n';

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

export default class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[DataShield] page crashed:', error, info.componentStack);
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;
    const workbenchHref = window.datashieldDesktop ? '#/app/today' : '/app/today';
    return (
      <div className="ds-page">
        <div className="ds-state error" role="alert">
          <h2>{i18n.t('appnew.common.errorBoundary.title')}</h2>
          <p>{i18n.t('appnew.common.errorBoundary.body')}</p>
          {error.message && (
            <details>
              <summary>{i18n.t('appnew.common.errorBoundary.summary')}</summary>
              <pre>{error.message}</pre>
            </details>
          )}
          <div>
            <a className="ds-button primary" href={workbenchHref}>
              {i18n.t('appnew.common.errorBoundary.backToWorkbench')}
            </a>
            <button type="button" className="ds-button quiet" onClick={() => window.location.reload()}>
              {i18n.t('appnew.common.errorBoundary.reload')}
            </button>
          </div>
        </div>
      </div>
    );
  }
}
