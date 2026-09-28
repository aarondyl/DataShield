export default function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3 flex items-center justify-between">
      <span>请求失败:{message}(请确认后端 localhost:8000 已启动)</span>
      {onRetry && (
        <button onClick={onRetry} className="ml-4 underline shrink-0">
          重试
        </button>
      )}
    </div>
  );
}
