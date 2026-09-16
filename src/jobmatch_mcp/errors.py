"""Structured, documented error responses for every tool.

Design intent: a calling agent should never have to parse a Python
traceback to figure out what went wrong or whether retrying makes sense.
Every *expected* failure mode a tool can hit is modeled as a JobMatchError
with a stable `code`, a human-readable `message`, and a `retryable` flag.
Tools catch these and return them as a structured dict instead of raising,
so the agent gets a predictable, low-token-cost shape:

    {"ok": False, "error": {"code": "...", "message": "...", "retryable": false}}

Unexpected/unmodeled exceptions are left to propagate -- FastMCP converts
those to a standard MCP tool error, which is the correct behavior for
genuine bugs rather than expected domain failures.
"""

from __future__ import annotations


class JobMatchError(Exception):
    """Base class for expected, documented tool failures."""

    code: str = "UNKNOWN_ERROR"
    retryable: bool = False

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

    def to_dict(self) -> dict:
        return {
            "ok": False,
            "error": {
                "code": self.code,
                "message": self.message,
                "retryable": self.retryable,
            },
        }


class InvalidQueryError(JobMatchError):
    """Caller-side input failed validation (empty query, bad enum, etc.)."""

    code = "INVALID_QUERY"
    retryable = False


class NoResultsFoundError(JobMatchError):
    """The search/lookup ran successfully but matched nothing."""

    code = "NO_RESULTS_FOUND"
    retryable = False


class UpstreamRateLimitedError(JobMatchError):
    """The Adzuna API rejected the request for rate limiting."""

    code = "RATE_LIMITED"
    retryable = True


class UpstreamUnavailableError(JobMatchError):
    """The Adzuna API is unreachable or returned a 5xx."""

    code = "UPSTREAM_UNAVAILABLE"
    retryable = True


class ApplicationNotFoundError(JobMatchError):
    """track_application referenced an application id that doesn't exist."""

    code = "APPLICATION_NOT_FOUND"
    retryable = False


ERROR_CATALOG = {
    cls.code: cls.__doc__
    for cls in (
        InvalidQueryError,
        NoResultsFoundError,
        UpstreamRateLimitedError,
        UpstreamUnavailableError,
        ApplicationNotFoundError,
    )
}
