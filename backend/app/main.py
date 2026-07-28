"""Vandals Stats Pipeline — FastAPI Application Entry Point."""

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.auth.prototype import PrototypeAuthMiddleware
from app.config import settings
from app.db.engine import async_session, init_db
from app.logging import (
    REQUEST_ID_HEADER,
    bind_request_id,
    configure_logging,
    reset_request_id,
)
from app.rate_limit import configure_rate_limiting
from app.services.article_generation import article_generation_worker

configure_logging()
request_logger = logging.getLogger("app.request")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    settings.check_security()
    await init_db()
    worker_stop = asyncio.Event()
    worker_task = asyncio.create_task(
        article_generation_worker(async_session, worker_stop),
        name="article-generation-worker",
    )
    try:
        yield
    finally:
        worker_stop.set()
        worker_task.cancel()
        with suppress(asyncio.CancelledError):
            await worker_task


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    lifespan=lifespan,
)

configure_rate_limiting(app)
app.add_middleware(PrototypeAuthMiddleware)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Attach a request ID to responses and request-scoped logs."""
    incoming_request_id = request.headers.get(REQUEST_ID_HEADER, "").strip()
    request_id = incoming_request_id or uuid4().hex
    request.state.request_id = request_id
    token = bind_request_id(request_id)

    try:
        response = await call_next(request)
        request_logger.info(
            "request completed method=%s path=%s status_code=%s",
            request.method,
            request.url.path,
            response.status_code,
        )
    except Exception:
        request_logger.exception(
            "request failed method=%s path=%s",
            request.method,
            request.url.path,
        )
        raise
    finally:
        reset_request_id(token)

    response.headers[REQUEST_ID_HEADER] = request_id
    return response


# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(api_router, prefix="/api/v1")
