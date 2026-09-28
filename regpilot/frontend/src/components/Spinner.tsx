export default function Spinner({ text = '加载中…' }: { text?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-gray-500 py-8 justify-center">
      <span className="inline-block h-4 w-4 rounded-full border-2 border-indigo-600 border-t-transparent animate-spin" />
      {text}
    </div>
  );
}
