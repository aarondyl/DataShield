import { useTranslation } from 'react-i18next';

export default function EmptyState({ message }: { message?: string }) {
  const { t } = useTranslation();
  return (
    <div className="bg-white border border-dashed border-gray-300 rounded-lg py-12 text-center text-sm text-gray-400">
      {message ?? t('common.emptyState.default')}
    </div>
  );
}
