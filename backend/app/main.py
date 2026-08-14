import logging
import time
import uuid

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.limiter import limiter
from app.core.logging import configure_logging

settings = get_settings()
configure_logging(settings.environment)

request_logger = logging.getLogger("app.requests")
error_logger = logging.getLogger("app.errors")

app = FastAPI(
    title="ONDC Blockchain-AI API",
    description="Trust scoring, fraud detection, recommendations, and dispute "
    "resolution for a Blockchain-AI enhanced ONDC network.",
    version="0.1.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """One line per request: method, path, status, latency, and a
    correlation id echoed back as X-Request-ID — enough to trace a single
    request through the logs without pulling in a tracing library."""
    request_id = str(uuid.uuid4())
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    request_logger.info(
        "%s %s -> %s (%.1fms) request_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        request_id,
    )
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Same `{"detail": ...}` envelope shape as every HTTPException response
    in this API, plus the field-level errors — a client branching on
    `detail` doesn't need a special case for validation failures.

    Drops each error's `ctx` key: pydantic populates it with the raw
    exception instance for validators that `raise ValueError(...)` (e.g.
    `_validate_city` in app/schemas/user.py), which isn't JSON-serializable
    and would otherwise blow up `JSONResponse.render` here. `msg` already
    has `ctx`'s content interpolated into it, so nothing is lost.
    """
    errors = [{k: v for k, v in error.items() if k != "ctx"} for error in exc.errors()]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Validation error", "errors": errors},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Anything that reaches here is a bug, not an expected error path —
    expected errors are raised as HTTPException throughout this codebase
    and never reach this handler. Logs the full traceback server-side,
    returns a generic message client-side (no stack trace, no internal
    detail leaked)."""
    error_logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"detail": "Internal server error"}
    )


# Added last so it wraps outermost — CORS headers should still be present
# on rate-limited (429) and error (422/500) responses, not just 2xx ones.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}
