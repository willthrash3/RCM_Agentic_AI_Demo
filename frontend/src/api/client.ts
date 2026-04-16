const API_BASE = import.meta.env.VITE_API_URL || '/api/v1';
const API_KEY = import.meta.env.VITE_API_KEY || 'demo-key-12345';

export async function api<T = unknown>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': API_KEY,
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json() as Promise<T>;
}

export const apiBase = API_BASE;
export const apiKey = API_KEY;
