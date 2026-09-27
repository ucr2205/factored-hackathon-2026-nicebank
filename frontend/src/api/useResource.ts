import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../auth/AuthProvider";
import { api } from "./client";

/** Loads a GET resource with the current token; `reload` re-fetches (e.g. after a mutation). */
export function useResource<T>(path: string | null, refreshMs?: number) {
  const { user } = useAuth();
  const token = user?.access_token;
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const reload = useCallback(async () => {
    if (!path || !token) return;
    setLoading(true);
    try {
      setData(await api<T>(path, token));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "error");
    } finally {
      setLoading(false);
    }
  }, [path, token]);

  useEffect(() => {
    void reload();
    if (!refreshMs) return;
    const id = setInterval(() => void reload(), refreshMs);
    return () => clearInterval(id);
  }, [reload, refreshMs]);

  return { data, error, loading, reload };
}
