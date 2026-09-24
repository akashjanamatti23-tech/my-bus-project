import { useCallback, useEffect, useState } from 'react';
import { api } from './api';

export function useResource<T = any>(path: string | null, poll = false) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  // undefined renders no native text node in conditional JSX; an empty string can
  // become a raw child under View with React 19 / React Native Web.
  const [error, setError] = useState<string | undefined>(undefined);
  const refresh = useCallback(async () => {
    if (!path) { setLoading(false); return; }
    try { const result = await api<T>(path); setData(result); setError(undefined); }
    catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }, [path]);
  useEffect(() => { setLoading(true); setData(null); refresh(); const timer = poll ? setInterval(refresh, 15000) : undefined; return () => clearInterval(timer); }, [refresh, poll]);
  return { data, loading, error, refresh, setData };
}