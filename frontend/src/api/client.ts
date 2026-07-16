/**
 * Base API client.
 *
 * All API modules should use this client for requests.
 * In development, Vite proxies /api to the backend.
 * In production, nginx handles the proxy.
 *
 * Projects can register an auth-failure handler for 401/403 responses to
 * trigger token refresh, logout, or redirect flows.
 */

const BASE_URL = "/api/v1";

interface RequestOptions extends RequestInit {
  params?: Record<string, string>;
}

type ApiResponseBody =
  | boolean
  | number
  | string
  | null
  | Record<string, unknown>
  | unknown[]
  | undefined;

type AuthFailureHandler = (error: ApiError) => void | Promise<void>;

let authFailureHandler: AuthFailureHandler | undefined;

export class ApiError extends Error {
  readonly status: number;
  readonly statusText: string;
  readonly data: ApiResponseBody;

  constructor(message: string, response: Response, data: ApiResponseBody) {
    super(message);
    this.name = "ApiError";
    this.status = response.status;
    this.statusText = response.statusText;
    this.data = data;
  }
}

function isObjectBody(value: ApiResponseBody): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function looksLikeJson(bodyText: string): boolean {
  const trimmedBody = bodyText.trim();
  return trimmedBody.startsWith("{") || trimmedBody.startsWith("[");
}

function getErrorMessage(response: Response, data: ApiResponseBody): string {
  if (typeof data === "string" && data.trim()) {
    return data.trim();
  }

  if (isObjectBody(data)) {
    const detail = data.detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail.trim();
    }

    const message = data.message;
    if (typeof message === "string" && message.trim()) {
      return message.trim();
    }
  }

  return response.statusText || `Request failed: ${response.status}`;
}

async function parseResponseBody(response: Response): Promise<ApiResponseBody> {
  if (response.status === 204 || response.status === 205) {
    return undefined;
  }

  const bodyText = await response.text();
  if (!bodyText.trim()) {
    return undefined;
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("json") || looksLikeJson(bodyText)) {
    try {
      return JSON.parse(bodyText) as ApiResponseBody;
    } catch {
      return bodyText;
    }
  }

  return bodyText;
}

function isAuthFailureStatus(status: number): boolean {
  return status === 401 || status === 403;
}

/**
 * Register optional 401/403 handling for logout, token refresh, or redirects.
 * Pass `undefined` to clear the current handler.
 */
export function setAuthFailureHandler(
  handler: AuthFailureHandler | undefined
): void {
  authFailureHandler = handler;
}

async function request<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const { params, ...init } = options;

  let url = `${BASE_URL}${endpoint}`;
  if (params) {
    const searchParams = new URLSearchParams(params);
    url += `?${searchParams.toString()}`;
  }

  const headers = new Headers(init.headers);
  if (init.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  // Optional auth extension: attach a bearer token if the project stores one.
  const token = localStorage.getItem("access_token");
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(url, {
    credentials: "same-origin",
    ...init,
    headers,
  });
  const data = await parseResponseBody(response);

  if (!response.ok) {
    const error = new ApiError(getErrorMessage(response, data), response, data);
    if (isAuthFailureStatus(response.status)) {
      await authFailureHandler?.(error);
    }
    throw error;
  }

  return data as T;
}

export const api = {
  get: <T>(endpoint: string, params?: Record<string, string>) =>
    request<T>(endpoint, { method: "GET", params }),

  post: <T>(endpoint: string, body?: unknown) =>
    request<T>(endpoint, { method: "POST", body: JSON.stringify(body) }),

  put: <T>(endpoint: string, body?: unknown) =>
    request<T>(endpoint, { method: "PUT", body: JSON.stringify(body) }),

  patch: <T>(endpoint: string, body?: unknown) =>
    request<T>(endpoint, { method: "PATCH", body: JSON.stringify(body) }),

  delete: <T>(endpoint: string) =>
    request<T>(endpoint, { method: "DELETE" }),
};
