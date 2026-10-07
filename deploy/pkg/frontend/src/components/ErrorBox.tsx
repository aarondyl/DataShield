import { useTranslation } from 'react-i18next';

export default function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const { t } = useTranslation();
  return (
    <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3 flex items-center justify-between">
      <span>{t('common.errorBox.message', { message })}</span>
      {onRetry && (
        <button onClick={onRetry} className="ml-4 underline shrink-0">
          {t('common.actions.retry')}
        </button>
      )}
    </div>
  );
}
