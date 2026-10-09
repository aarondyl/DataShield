import { useTranslation } from 'react-i18next';
import type { RiskLevel } from '../types';

const styles: Record<string, string> = {
  high: 'bg-red-100 text-red-800 border-red-200',
  medium: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  low: 'bg-green-100 text-green-800 border-green-200',
  unknown: 'bg-gray-100 text-gray-600 border-gray-200',
};

export default function RiskBadge({ level }: { level: RiskLevel | null | undefined }) {
  const { t } = useTranslation();
  const key = level ?? 'unknown';
  return (
    <span className={`inline-block px-2 py-0.5 text-xs font-medium border rounded ${styles[key]}`}>
      {t(`common.status.${key}`)}
    </span>
  );
}
