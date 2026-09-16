"""Structured, single-line JSON logging for every tool call.

Every tool invocation logs one JSON line on completion: tool name,
duration in milliseconds, outcome (ok/error + error code if any), and a
handful of non-sensitive parameter summaries. No API keys, no full
resume/job text, no PII beyond what the caller already sent as a job
title/location -- see `redact_params`.
"""

from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from typing import Any, Iterator

logger = logging.getLogger("jobmatch_mcp")

_SENSITIVE_KEYS = {"resume_text", "resume", "app_key", "api_key", "token"}


def configure_logging(level: str = "INFO") -> None:
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, level, logging.INFO))
    logger.propagate = False


def redact_params(params: dict[str, Any]) -> dict[str, Any]:
    """Drop/trim anything that shouldn't land in a log line."""
    redacted: dict[str, Any] = {}
    for key, value in params.items():
        if key.lower() in _SENSITIVE_KEYS:
            redacted[key] = f"<redacted len={len(str(value))}>"
        elif isinstance(value, str) and len(value) > 120:
            redacted[key] = value[:120] + "...<truncated>"
        else:
            redacted[key] = value
    return redacted


@contextmanager
def log_tool_call(tool_name: str, params: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Wrap a tool body; logs one structured line with latency + outcome.

    Usage:
        with log_tool_call("search_jobs", {"query": query}) as outcome:
            result = do_the_work()
            outcome["ok"] = True
            return result
    """
    start = time.perf_counter()
    outcome: dict[str, Any] = {"ok": None, "error_code": None}
    try:
        yield outcome
    finally:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        record = {
            "tool": tool_name,
            "duration_ms": duration_ms,
            "ok": outcome.get("ok"),
            "error_code": outcome.get("error_code"),
            "params": redact_params(params),
        }
        logger.info(json.dumps(record, default=str))
