/**
 * Typed API client.
 *
 * Two rules:
 *   1. Never send an organization id as proof of authorization. The token identifies the user; the
 *      server resolves which organization they may act in.
 *   2. Never attach a token the server did not ask for. Clerk mints a short-lived JWT per request;
 *      it is fetched here rather than cached in module state, so a revoked session stops working
 *      when it expires instead of lingering for the lifetime of the tab.
 */

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export type HealthResponse = { status: "ok"; service: string; version: string };

/** Shape of the API's error envelope, so callers can branch on a code instead of parsing prose. */
export type ApiErrorBody = { error?: { code?: string; message?: string; request_id?: string } };

export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;
  readonly requestId?: string;

  constructor(status: number, body: ApiErrorBody | null) {
    super(body?.error?.message ?? `Request failed with ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.code = body?.error?.code;
    this.requestId = body?.error?.request_id;
  }
}

async function request<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new ApiError(response.status, await response.json().catch(() => null));
  }

  return (await response.json()) as T;
}

/**
 * Build a client bound to one Clerk session token.
 *
 * Call `getToken()` in a server component or route handler and pass the result in:
 *
 *   const { getToken } = await auth();
 *   const client = createClient(await getToken());
 *
 * Passing the token explicitly keeps this module free of framework imports, so it stays testable
 * and cannot accidentally run an unauthenticated request because a hook was unavailable.
 */
export function createClient(token: string | null) {
  if (!token) {
    throw new Error("No session token. The caller is not signed in.");
  }

  return {
    health: () => request<HealthResponse>("/health", token),
  };
}
