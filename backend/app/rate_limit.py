"""Optional starter rate limiting middleware."""

import asyncio
import math
import time
from collections import defaultdict, deque
from collections.abc import Iterable
from typing import Final

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from app.config import settings

RATE_LIMIT_HEADER_PREFIX: Final[str] = "X-RateLimit"


class InMemoryRateLimitMiddleware(BaseHTTPMiddleware):
    """Apply a simple per-client rate limit within a single app process."""

    def __init__(
        self,
        app,
        *,
        request_limit: int,
        window_seconds: int,
        exempt_path_prefixes: Iterable[str],
        trust_proxy_headers: bool,
    ) -> None:
        super().__init__(app)

        if request_limit < 1:
            raise ValueError("request_limit must be at least 1")
        if window_seconds < 1:
            raise ValueError("window_seconds must be at least 1")

        self.request_limit = request_limit
        self.window_seconds = window_seconds
        self.exempt_path_prefixes = tuple(exempt_path_prefixes)
        self.trust_proxy_headers = trust_proxy_headers
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if self._is_exempt(request.url.path):
            return await call_next(request)

        allowed, remaining, retry_after = await self._register_request(
            self._client_key(request)
        )
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers=self._build_headers(remaining, retry_after),
            )

        response = await call_next(request)
        for header, value in self._build_headers(remaining).items():
            response.headers[header] = value
        return response

    def _is_exempt(self, path: str) -> bool:
        return any(path.startswith(prefix) for prefix in self.exempt_path_prefixes)

    def _client_key(self, request: Request) -> str:
        if self.trust_proxy_headers:
            forwarded_for = request.headers.get("x-forwarded-for", "")
            first_hop = forwarded_for.split(",", maxsplit=1)[0].strip()
            if first_hop:
                return first_hop

        if request.client and request.client.host:
            return request.client.host

        return "unknown-client"

    async def _register_request(self, client_key: str) -> tuple[bool, int, int | None]:
        now = time.monotonic()
        window_start = now - self.window_seconds

        async with self._lock:
            request_times = self._requests[client_key]
            while request_times and request_times[0] <= window_start:
                request_times.popleft()

            if len(request_times) >= self.request_limit:
                retry_after = max(
                    1,
                    math.ceil(self.window_seconds - (now - request_times[0])),
                )
                return False, 0, retry_after

            request_times.append(now)
            remaining = self.request_limit - len(request_times)
            return True, remaining, None

    def _build_headers(
        self, remaining: int, retry_after: int | None = None
    ) -> dict[str, str]:
        headers = {
            f"{RATE_LIMIT_HEADER_PREFIX}-Limit": str(self.request_limit),
            f"{RATE_LIMIT_HEADER_PREFIX}-Remaining": str(max(remaining, 0)),
            f"{RATE_LIMIT_HEADER_PREFIX}-Window-Seconds": str(self.window_seconds),
        }
        if retry_after is not None:
            headers["Retry-After"] = str(retry_after)
        return headers


def configure_rate_limiting(app: FastAPI) -> None:
    """Install the starter rate limiting middleware when enabled."""
    app.state.rate_limiting_mode = "disabled"

    if not settings.RATE_LIMIT_ENABLED:
        return

    app.add_middleware(
        InMemoryRateLimitMiddleware,
        request_limit=settings.RATE_LIMIT_REQUESTS,
        window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
        exempt_path_prefixes=settings.rate_limit_exempt_paths_list,
        trust_proxy_headers=settings.RATE_LIMIT_TRUST_PROXY_HEADERS,
    )
    app.state.rate_limiting_mode = "in-memory"
