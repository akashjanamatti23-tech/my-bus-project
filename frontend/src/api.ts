import Constants from 'expo-constants';
import { storage } from '@/src/utils/storage';

export const TOKEN_KEY = 'gobus.access-token';
export const API_URL = `${Constants.expoConfig?.extra?.backendUrl ?? ''}/api`;
let expired: (() => void) | undefined;
export function onSessionExpired(callback: () => void) { expired = callback; }
export async function api<T = any>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const token = await storage.secureGet(TOKEN_KEY, '');
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 20000);
  try {
    const response = await fetch(`${API_URL}${path}`, {
      method, signal: controller.signal,
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      if (response.status === 401 && !path.startsWith('/auth/login')) { await storage.secureRemove(TOKEN_KEY); expired?.(); }
      const message = Array.isArray(data.detail) ? data.detail.map((d: any) => `${d.loc?.slice(1).join(' ')}: ${d.msg}`).join('\n') : data.detail;
      throw new Error(message || 'Unable to complete your request. Please try again.');
    }
    return data;
  } catch (e: any) {
    if (e.name === 'AbortError') throw new Error('The connection is taking too long. Please try again.');
    if (e instanceof TypeError) throw new Error('Unable to connect. Check your connection and try again.');
    throw e;
  } finally { clearTimeout(timeout); }
}