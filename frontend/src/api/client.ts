const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8081";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

/** Calls the backend with the in-memory access token and maps error bodies to ApiError. */
export async function api<T>(path: string, token: string, init?: { method?: "GET" | "POST"; body?: unknown }): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method: init?.method ?? "GET",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: init?.body === undefined ? undefined : JSON.stringify(init.body),
    });
  } catch {
    throw new ApiError(0, "network_error", "backend unreachable");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, data.error ?? "unknown", data.message ?? res.statusText);
  return data as T;
}

// Jaeger, Prometheus and Mailpit are reached through the gateway (/jaeger, /prometheus, /mail; team login).
export const TOOLS_URL = import.meta.env.VITE_TOOLS_URL ?? "http://localhost:8090";
export const JAEGER_URL = `${TOOLS_URL}/jaeger`;
