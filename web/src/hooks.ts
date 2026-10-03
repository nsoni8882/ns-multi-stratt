import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { Timeframe } from "./types";

export interface AsyncState<T> {
  data?: T;
  error?: Error;
  loading: boolean;
  retry: () => void;
}

export function useAsync<T>(load: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [state, setState] = useState<{ data?: T; error?: Error; loading: boolean }>({ loading: true });
  const [attempt, setAttempt] = useState(0);
  const retry = useCallback(() => setAttempt((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    setState({ loading: true });
    load()
      .then((data) => alive && setState({ data, loading: false }))
      .catch((error: Error) => alive && setState({ error, loading: false }));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, attempt]);

  return { ...state, retry };
}

/** Global timeframe, kept in the URL (?tf=4h) so links are shareable. Defaults to 1D. */
export function useTimeframe(): [Timeframe, (tf: Timeframe) => void] {
  const [params, setParams] = useSearchParams();
  const tf: Timeframe = params.get("tf") === "4h" ? "4h" : "1d";
  const setTf = (next: Timeframe) => {
    const p = new URLSearchParams(params);
    if (next === "1d") p.delete("tf");
    else p.set("tf", next);
    setParams(p, { replace: true });
  };
  return [tf, setTf];
}
