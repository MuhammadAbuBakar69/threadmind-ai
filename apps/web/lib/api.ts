/**
 * Typed API client.
 *
 * One rule: never send an organization id as proof of authorization. The token identifies the user;
 * the server resolves which organization they may act in.
 */

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export type HealthResponse = { status: "ok"; service: string; version: string };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const message = body?.error?.message ?? `Request failed with ${response.status}`;
    throw new Error(message);
  }

  return (await response.json()) as T;
}

export const api = {
  health: () => request<HealthResponse>("/health"),
};
