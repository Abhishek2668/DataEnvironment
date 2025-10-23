import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";

type Options = {
  immediate?: boolean;
  deps?: unknown[];
};

export function useApi<T>(path: string, options: Options = {}) {
  const { immediate = true, deps = [] } = options;
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(immediate);
  const [error, setError] = useState<Error | null>(null);

  const execute = useCallback(async () => {
    try {
      setLoading(true);
      const response = await api<T>(path);
      setData(response);
      setError(null);
    } catch (err) {
      setError(err as Error);
    } finally {
      setLoading(false);
    }
  }, [path]);

  useEffect(() => {
    if (immediate) {
      void execute();
    }
  }, [execute, immediate, ...deps]);

  return { data, loading, error, refetch: execute };
}
