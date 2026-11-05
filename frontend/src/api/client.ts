import type { AskRequest, AskResponse, DocumentInfo, Health } from "./types";

/**
 * Why a request failed, so the UI can show a clear message:
 * - network: the API could not be reached at all
 * - not_found: 404 (e.g. an unknown document)
 * - invalid: 422 (the request was rejected by validation)
 * - unavailable: 503 (nothing ingested yet)
 * - server: any other non-2xx answer, or a body that is not JSON
 */
export type ApiErrorKind = "network" | "not_found" | "invalid" | "unavailable" | "server";

export class ApiError extends Error {
  constructor(
    readonly kind: ApiErrorKind,
    readonly status: number | null,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function errorKind(status: number): ApiErrorKind {
  if (status === 404) return "not_found";
  if (status === 422) return "invalid";
  if (status === 503) return "unavailable";
  return "server";
}

/** FastAPI puts the reason in "detail": a string, or a list of validation errors. */
function detailOf(body: unknown): string | null {
  if (!body || typeof body !== "object" || !("detail" in body)) return null;
  const d = (body as { detail: unknown }).detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) {
    const msgs = d.map((e) => (e && typeof e === "object" && "msg" in e ? String(e.msg) : ""));
    return msgs.filter(Boolean).join("; ") || null;
  }
  return null;
}

export interface ApiClient {
  health(): Promise<Health>;
  documents(corpus?: AskRequest["corpus"]): Promise<DocumentInfo[]>;
  ask(req: AskRequest, signal?: AbortSignal): Promise<AskResponse>;
}

export function createClient(
  baseUrl: string = import.meta.env.VITE_API_BASE ?? "/api",
  fetchFn: typeof fetch = (...args) => fetch(...args),
): ApiClient {
  async function request<T>(path: string, init?: RequestInit): Promise<T> {
    let res: Response;
    try {
      res = await fetchFn(`${baseUrl}${path}`, init);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") throw err;
      throw new ApiError("network", null, err instanceof Error ? err.message : String(err));
    }
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      body = null;
    }
    if (!res.ok) {
      throw new ApiError(errorKind(res.status), res.status, detailOf(body) ?? res.statusText);
    }
    if (body === null) throw new ApiError("server", res.status, "response is not JSON");
    return body as T;
  }

  return {
    health: () => request<Health>("/health"),
    documents: (corpus) =>
      request<DocumentInfo[]>(corpus ? `/documents?corpus=${encodeURIComponent(corpus)}` : "/documents"),
    ask: (req, signal) =>
      request<AskResponse>("/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req),
        signal,
      }),
  };
}
