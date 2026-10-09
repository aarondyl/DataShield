import { useTranslation } from 'react-i18next';

export default function Spinner({ text }: { text?: string }) {
  const { t } = useTranslation();
  return (
    <div className="flex items-center gap-2 text-sm text-gray-500 py-8 justify-center">
      <span className="inline-block h-4 w-4 rounded-full border-2 border-indigo-600 border-t-transparent animate-spin" />
      {text ?? t('common.loading')}
    </div>
  );
}
