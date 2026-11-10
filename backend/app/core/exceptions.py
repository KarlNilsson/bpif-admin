"""Domain exceptions raised by services and their mapping to HTTP responses.

Services raise these exceptions and never `HTTPException`, so they stay
independent of HTTP. `register_exception_handlers` translates them into
responses with the same `{"detail": "<message>"}` shape as `HTTPException`.
"""

from collections.abc import Awaitable, Callable
from typing import cast

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

ExceptionHandler = Callable[[Request, Exception], Awaitable[JSONResponse]]


class DomainError(Exception):
    """Base class for errors raised by services."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(DomainError):
    """The requested resource does not exist (404)."""


class ConflictError(DomainError):
    """The request conflicts with the current state (409)."""


# A bare DomainError is deliberately not mapped: it is a programming error and
# surfaces as a 500.
STATUS_CODES: dict[type[DomainError], int] = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ConflictError: status.HTTP_409_CONFLICT,
}


def _make_handler(status_code: int) -> ExceptionHandler:
    async def handler(request: Request, exc: Exception) -> JSONResponse:
        # Only registered for DomainError subclasses (see below).
        message = cast(DomainError, exc).message
        return JSONResponse({'detail': message}, status_code=status_code)

    return handler


def register_exception_handlers(app: FastAPI) -> None:
    for exc_class, status_code in STATUS_CODES.items():
        app.add_exception_handler(exc_class, _make_handler(status_code))
