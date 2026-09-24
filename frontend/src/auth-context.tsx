import React, { createContext, useContext, useEffect, useState } from 'react';
import { api, onSessionExpired, TOKEN_KEY } from './api';
import { storage } from '@/src/utils/storage';

type User = { id: string; name: string; email: string; mobile: string; role: string; mobile_verified: boolean; driver_code?: string };
const Auth = createContext<{ user: User | null; loading: boolean; accept: (result: any) => Promise<void>; logout: () => Promise<void> }>({ user: null, loading: true, accept: async () => {}, logout: async () => {} });
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    onSessionExpired(() => setUser(null));
    (async () => { try { const token = await storage.secureGet(TOKEN_KEY, ''); if (token) setUser(await api('/auth/me')); } catch { setUser(null); } finally { setLoading(false); } })();
  }, []);
  const accept = async (result: any) => {
    const stored = await storage.secureSet(TOKEN_KEY, result.access_token);
    if (!stored) throw new Error('Unable to securely store your session. Please try again.');
    setUser(result.user);
  };
  const logout = async () => {
    await api('/auth/logout', 'POST');
    await storage.secureRemove(TOKEN_KEY);
    setUser(null);
  };
  return <Auth.Provider value={{ user, loading, accept, logout }}>{children}</Auth.Provider>;
}
export const useAuth = () => useContext(Auth);