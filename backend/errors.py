"""One JSON error envelope for every failure: ``{"error": {"code", "message", "request_id"}}``."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from snap2cook.exceptions import (CorpusLoadError, FileOperationError, GenerationError, InvalidImageError,
                                  NoIngredientsDetectedError, RateLimitExceededError, Snap2CookError,
                                  UnsupportedTierError, VisionProviderError)

log = logging.getLogger("snap2cook.api")


class AdminAuthError(Snap2CookError):
    """Wrong admin credentials."""

    default_user_message = "Invalid credentials."


# domain exception -> (HTTP status, machine code); the first isinstance match wins
STATUS_MAP: list[tuple[type[Snap2CookError], int, str]] = [
    (RateLimitExceededError, 429, "rate_limited"),
    (AdminAuthError, 401, "invalid_credentials"),
    (InvalidImageError, 400, "invalid_image"),
    (UnsupportedTierError, 400, "unsupported_tier"),
    (NoIngredientsDetectedError, 422, "no_ingredients"),
    (VisionProviderError, 503, "vision_unavailable"),
    (GenerationError, 503, "generation_unavailable"),
    (CorpusLoadError, 500, "corpus_error"),
    (FileOperationError, 500, "file_error"),
]


def envelope(request: Request, code: str, message: str, status: int, **extra: object) -> JSONResponse:
    """Build the error response and note the error for the request log."""
    request.state.error = f"{code}: {message}"[:500]
    body = {"error": {"code": code, "message": message,
                      "request_id": getattr(request.state, "request_id", None), **extra}}
    headers = {"Retry-After": str(extra["retry_after"])} if "retry_after" in extra else None
    return JSONResponse(body, status_code=status, headers=headers)


def install_error_handlers(app: FastAPI) -> None:
    """Register handlers so the UI always receives a friendly, structured message."""

    @app.exception_handler(Snap2CookError)
    async def domain_error(request: Request, exc: Snap2CookError) -> JSONResponse:
        status, code = next(((s, c) for cls, s, c in STATUS_MAP if isinstance(exc, cls)), (500, "internal_error"))
        log.warning("domain error %s: %s", code, exc.message)
        extra = {"retry_after": exc.retry_after} if isinstance(exc, RateLimitExceededError) else {}
        return envelope(request, code, exc.user_message, status, **extra)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(p) for p in first.get("loc", [])[1:])
        return envelope(request, "invalid_request", f"Invalid input{' (' + where + ')' if where else ''}.", 422)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return envelope(request, "http_error", str(exc.detail), exc.status_code)

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error on %s", request.url.path)
        return envelope(request, "internal_error", "Something went wrong on our side. Please try again.", 500)
