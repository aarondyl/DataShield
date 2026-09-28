import { useCallback, useEffect, useState } from 'react';

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const memoFn = useCallback(fn, deps);

  const reload = useCallback(() => {
    setLoading(true);
    setError(null);
    memoFn()
      .then(setData)
      .catch((e) => setError(e?.response?.data?.detail ?? e?.message ?? '请求失败'))
      .finally(() => setLoading(false));
  }, [memoFn]);

  useEffect(() => {
    reload();
  }, [reload]);

  return { data, loading, error, reload, setData };
}
