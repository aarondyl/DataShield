export default function EmptyState({ message = '暂无数据' }: { message?: string }) {
  return (
    <div className="bg-white border border-dashed border-gray-300 rounded-lg py-12 text-center text-sm text-gray-400">
      {message}
    </div>
  );
}
