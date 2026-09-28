import type { RiskLevel } from '../types';

const styles: Record<string, string> = {
  high: 'bg-red-100 text-red-800 border-red-200',
  medium: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  low: 'bg-green-100 text-green-800 border-green-200',
  unknown: 'bg-gray-100 text-gray-600 border-gray-200',
};

export default function RiskBadge({ level }: { level: RiskLevel | null | undefined }) {
  const key = level ?? 'unknown';
  const labels = { high: '高', medium: '中', low: '低', unknown: '未知' };
  return (
    <span className={`inline-block px-2 py-0.5 text-xs font-medium border rounded ${styles[key]}`}>
      {labels[key as keyof typeof labels]}
    </span>
  );
}
