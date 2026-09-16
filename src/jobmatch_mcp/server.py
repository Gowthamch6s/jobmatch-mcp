"""JobMatch MCP server.

Exposes four narrow, single-responsibility tools over stdio (the MCP
transport baseline, compatible with Claude Desktop, Cursor, and any other
MCP host):

    search_jobs            -- live (or mock) job listings for a query
    score_resume_match     -- 0-100 match score of a resume against a job description
    track_application      -- create/update a tracked application (local SQLite)
    list_applications       -- list tracked applications, optionally by status

Design choices, and why:
  * Auth (ADZUNA_APP_ID/KEY) is read server-side from the environment in
    config.py and never appears in a tool's input schema or output --
    the model can request a search, it can never see or forward a key.
  * Every expected failure mode raises a JobMatchError subclass (errors.py)
    and is caught here, turned into a structured
    {"ok": false, "error": {"code", "message", "retryable"}} response
    instead of a raw exception -- see errors.ERROR_CATALOG for the full,
    documented list. Only genuinely unexpected exceptions propagate to
    FastMCP's own error handling.
  * Every call is wrapped in log_tool_call, which emits one structured
    JSON log line with tool name, latency, and outcome -- no resume text,
    API keys, or other sensitive payloads (see logging_utils.redact_params).
"""

from __future__ import annotations

from typing import Literal

from fastmcp import FastMCP

from . import adzuna_client, matching, storage
from .config import load_settings
from .errors import JobMatchError
from .logging_utils import configure_logging, log_tool_call

settings = load_settings()
configure_logging(settings.log_level)

mcp = FastMCP(
    "jobmatch-mcp",
    version="0.1.0",
    instructions=(
        "Tools for an active job search: search live job postings, score how "
        "well a resume matches a specific posting, and track applications "
        "through their pipeline (saved -> applied -> interviewing -> offer/"
        "rejected/withdrawn). Call search_jobs first to find postings, then "
        "score_resume_match against a chosen posting's description, then "
        "track_application to record the outcome."
    ),
)


@mcp.tool()
async def search_jobs(
    query: str,
    location: str | None = None,
    max_results: int = 5,
) -> dict:
    """Search live job postings by title/keyword and optional location.

    Args:
        query: Job title or keyword, e.g. "agentic AI engineer". Required, non-empty.
        location: City/region to filter by, e.g. "Tampa, FL". Optional; omit for all locations.
        max_results: Number of listings to return, 1-20. Defaults to 5.

    Returns:
        {"ok": true, "listings": [...], "source": "adzuna"|"mock"} on success, where
        each listing has title/company/location/description/url/salary_min/salary_max.
        If ADZUNA_APP_ID/ADZUNA_APP_KEY are not configured server-side, results come
        from a deterministic mock dataset (source="mock") so this tool always works.
        On failure: {"ok": false, "error": {"code", "message", "retryable"}} with
        code one of INVALID_QUERY, NO_RESULTS_FOUND, RATE_LIMITED, UPSTREAM_UNAVAILABLE.
    """
    params = {"query": query, "location": location, "max_results": max_results}
    with log_tool_call("search_jobs", params) as outcome:
        try:
            listings = await adzuna_client.search_jobs(settings, query, location, max_results)
        except JobMatchError as exc:
            outcome["ok"] = False
            outcome["error_code"] = exc.code
            return exc.to_dict()
        outcome["ok"] = True
        source = listings[0]["source"] if listings else "mock"
        return {"ok": True, "listings": listings, "source": source}


@mcp.tool()
def score_resume_match(resume_text: str, job_description: str) -> dict:
    """Score how well a resume matches a specific job description.

    Args:
        resume_text: Plain-text resume content (or a relevant excerpt).
        job_description: Plain-text job posting description to match against.

    Returns:
        {"ok": true, "score": 0-100, "matched_terms": [...], "missing_terms": [...]}
        matched_terms/missing_terms are ranked by importance to the posting,
        with recognized technical skills weighted above generic words.
        On failure: {"ok": false, "error": {"code", "message", "retryable"}} with
        code INVALID_QUERY if either input is empty.
    """
    params = {"resume_text": resume_text, "job_description": job_description}
    with log_tool_call("score_resume_match", params) as outcome:
        from .errors import InvalidQueryError

        if not resume_text.strip() or not job_description.strip():
            err = InvalidQueryError("`resume_text` and `job_description` must both be non-empty.")
            outcome["ok"] = False
            outcome["error_code"] = err.code
            return err.to_dict()

        result = matching.score_match(resume_text, job_description)
        outcome["ok"] = True
        return {"ok": True, **result}


@mcp.tool()
def track_application(
    job_title: str,
    company: str,
    status: Literal["saved", "applied", "interviewing", "offer", "rejected", "withdrawn"] = "saved",
    job_url: str | None = None,
    match_score: int | None = None,
    notes: str | None = None,
    application_id: int | None = None,
) -> dict:
    """Create a new tracked application, or update an existing one by id.

    Args:
        job_title: Title of the role, e.g. "Agentic AI Engineer". Required.
        company: Hiring company name. Required.
        status: Pipeline stage. One of saved, applied, interviewing, offer,
            rejected, withdrawn. Defaults to "saved".
        job_url: Link to the posting. Optional.
        match_score: 0-100 score from score_resume_match, if computed. Optional.
        notes: Free-text notes (e.g. recruiter name, follow-up date). Optional.
        application_id: If provided, updates that existing application instead
            of creating a new one. Omit when creating a new entry.

    Returns:
        {"ok": true, "application": {...full row...}} on success.
        On failure: {"ok": false, "error": {"code", "message", "retryable"}} with
        code INVALID_QUERY (bad status/empty fields) or APPLICATION_NOT_FOUND
        (application_id given but doesn't exist).
    """
    params = {
        "job_title": job_title,
        "company": company,
        "status": status,
        "application_id": application_id,
    }
    with log_tool_call("track_application", params) as outcome:
        try:
            row = storage.track_application(
                settings.db_path,
                job_title=job_title,
                company=company,
                status=status,
                job_url=job_url,
                match_score=match_score,
                notes=notes,
                application_id=application_id,
            )
        except JobMatchError as exc:
            outcome["ok"] = False
            outcome["error_code"] = exc.code
            return exc.to_dict()
        outcome["ok"] = True
        return {"ok": True, "application": row}


@mcp.tool()
def list_applications(
    status: Literal["saved", "applied", "interviewing", "offer", "rejected", "withdrawn"] | None = None,
) -> dict:
    """List tracked applications, optionally filtered by pipeline status.

    Args:
        status: If given, only return applications in this status. Omit for all.

    Returns:
        {"ok": true, "applications": [...]} ordered by most recently updated.
        On failure: {"ok": false, "error": {"code", "message", "retryable"}} with
        code INVALID_QUERY if `status` isn't a recognized value.
    """
    params = {"status": status}
    with log_tool_call("list_applications", params) as outcome:
        try:
            rows = storage.list_applications(settings.db_path, status=status)
        except JobMatchError as exc:
            outcome["ok"] = False
            outcome["error_code"] = exc.code
            return exc.to_dict()
        outcome["ok"] = True
        return {"ok": True, "applications": rows}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
