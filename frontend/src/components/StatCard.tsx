interface Props {
  label: string;
  value: string | number;
  hint?: string;
}

export default function StatCard({ label, value, hint }: Props) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-5">
      <div className="text-sm text-gray-500">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-slate-900 truncate" title={String(value)}>
        {value}
      </div>
      {hint && <div className="mt-1 text-xs text-gray-400">{hint}</div>}
    </div>
  );
}
