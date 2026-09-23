import { useEffect, useRef, useState } from "react";

/**
 * Minimal async request state for the API service layer. `key` identifies the
 * request: when it changes (or on first render) the request runs and `loading`
 * is true until a result for the current key arrives.
 */
export function useRequest<T>(fetcher: () => Promise<T>, key: string) {
  const fetcherRef = useRef(fetcher);
  const [result, setResult] = useState<{
    key: string;
    data: T | null;
    error: Error | null;
  } | null>(null);

  // Keep the latest fetcher without re-running the request on every render.
  useEffect(() => {
    fetcherRef.current = fetcher;
  });

  useEffect(() => {
    let alive = true;
    fetcherRef
      .current()
      .then((data) => {
        if (alive) setResult({ key, data, error: null });
      })
      .catch((error: Error) => {
        if (alive) setResult({ key, data: null, error });
      });
    return () => {
      alive = false;
    };
  }, [key]);

  const current = result?.key === key ? result : null;
  return {
    data: current?.data ?? null,
    error: current?.error ?? null,
    loading: current === null,
  };
}
