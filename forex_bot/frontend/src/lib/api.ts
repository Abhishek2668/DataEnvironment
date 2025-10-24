export const API_BASE =
  import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE || "http://localhost:8000";
const TOKEN = import.meta.env.VITE_DASH_TOKEN || "dev-token";

export async function api<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(opts.headers as Record<string, string> | undefined),
  };
  if (opts.method && opts.method.toUpperCase() !== "GET") {
    headers["Authorization"] = `Bearer ${TOKEN}`;
  }
  const response = await fetch(`${API_BASE}${path}`, {
    ...opts,
    headers,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${response.status} ${text}`);
  }
  return response.json();
}
