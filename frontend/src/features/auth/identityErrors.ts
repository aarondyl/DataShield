type Translate = (key: string) => string;

export function identityErrorMessage(error: unknown, t: Translate): string {
  const message = typeof error === 'string' ? error : error instanceof Error ? error.message : '';
  if (message.includes('Email already registered')) return t('appnew.auth.emailTaken');
  if (message.includes('Invalid email or password')) return t('appnew.auth.invalidCredentials');
  if (message.includes('Invalid or expired')) return t('appnew.desktopAccount.invalidCode');
  if (message.includes('Too many') || message.includes('HTTP 429')) return t('appnew.desktopAccount.rateLimited');
  if (message.includes('verification required')) return t('appnew.desktopAccount.emailVerificationRequired');
  if (message.includes('organization') || message.includes('role') || message.includes('permission')) return t('appnew.desktopAccount.accessDenied');
  if (message.includes('unavailable') || message.includes('not configured') || message.includes('HTTP 5')) return t('appnew.desktopAccount.serviceUnavailable');
  if (message.includes('HTTP 401')) return t('appnew.auth.invalidCredentials');
  return t('appnew.desktopAccount.requestFailed');
}
