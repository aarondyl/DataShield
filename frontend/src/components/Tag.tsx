export default function Tag({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-block px-2 py-0.5 text-xs bg-indigo-50 text-indigo-700 border border-indigo-100 rounded mr-1 mb-1">
      {children}
    </span>
  );
}
