import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api, setAuthFailureHandler } from "../src/api/client";

const fetchMock = vi.fn<
  (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
>();

function createLocalStorageMock() {
  return {
    clear: vi.fn(),
    getItem: vi.fn(() => null),
    removeItem: vi.fn(),
    setItem: vi.fn(),
  };
}

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");

  return new Response(JSON.stringify(body), {
    ...init,
    headers,
  });
}

function textResponse(body: string, init: ResponseInit = {}): Response {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "text/plain");

  return new Response(body, {
    ...init,
    headers,
  });
}

describe("api client", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("localStorage", createLocalStorageMock());
    setAuthFailureHandler(undefined);
  });

  afterEach(() => {
    setAuthFailureHandler(undefined);
    vi.unstubAllGlobals();
  });

  it("returns parsed JSON for successful responses", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ status: "ok" }));

    await expect(api.get<{ status: string }>("/health")).resolves.toEqual({
      status: "ok",
    });
  });

  it("returns undefined for 204 responses", async () => {
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));

    await expect(api.delete<void>("/items/1")).resolves.toBeUndefined();
  });

  it("throws typed ApiError instances for JSON error responses", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        { detail: "Validation failed", code: "bad_request" },
        { status: 400, statusText: "Bad Request" }
      )
    );

    await expect(api.get("/broken")).rejects.toMatchObject({
      data: { detail: "Validation failed", code: "bad_request" },
      message: "Validation failed",
      name: "ApiError",
      status: 400,
      statusText: "Bad Request",
    });
  });

  it("keeps non-JSON error messages readable", async () => {
    fetchMock.mockResolvedValueOnce(
      textResponse("Upstream proxy unavailable", {
        status: 502,
        statusText: "Bad Gateway",
      })
    );

    await expect(api.get("/proxy")).rejects.toMatchObject({
      data: "Upstream proxy unavailable",
      message: "Upstream proxy unavailable",
      name: "ApiError",
      status: 502,
    });
  });

  it("calls the auth-failure handler for unauthorized responses", async () => {
    const onAuthFailure = vi.fn();
    setAuthFailureHandler(onAuthFailure);

    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        { detail: "Token expired" },
        { status: 401, statusText: "Unauthorized" }
      )
    );

    let thrownError: unknown;
    try {
      await api.get("/protected");
    } catch (error) {
      thrownError = error;
    }

    expect(thrownError).toBeInstanceOf(ApiError);
    expect(onAuthFailure).toHaveBeenCalledTimes(1);
    expect(onAuthFailure).toHaveBeenCalledWith(
      expect.objectContaining({
        message: "Token expired",
        status: 401,
      })
    );
  });
});
