"""Tests the tool functions as the MCP server exposes them -- calling the
underlying Python functions directly (FastMCP tools remain plain callables),
covering both the happy path and every documented structured error shape."""

import pytest

from jobmatch_mcp import server


@pytest.mark.asyncio
async def test_search_jobs_happy_path(isolated_db):
    result = await server.search_jobs("agentic ai engineer", max_results=2)
    assert result["ok"] is True
    assert len(result["listings"]) == 2
    assert result["source"] == "mock"


@pytest.mark.asyncio
async def test_search_jobs_invalid_query_returns_structured_error(isolated_db):
    result = await server.search_jobs("")
    assert result["ok"] is False
    assert result["error"]["code"] == "INVALID_QUERY"
    assert result["error"]["retryable"] is False


def test_score_resume_match_happy_path(isolated_db):
    result = server.score_resume_match(
        "Python, LangGraph, FastAPI, Docker experience.",
        "Looking for a Python engineer with LangGraph and Docker skills.",
    )
    assert result["ok"] is True
    assert 0 <= result["score"] <= 100
    assert "python" in result["matched_terms"]


def test_score_resume_match_empty_input_returns_structured_error(isolated_db):
    result = server.score_resume_match("", "some job description")
    assert result["ok"] is False
    assert result["error"]["code"] == "INVALID_QUERY"


def test_track_application_then_list_round_trip(isolated_db):
    created = server.track_application(
        job_title="Agentic AI Engineer", company="Vertex Analytics", status="applied"
    )
    assert created["ok"] is True
    app_id = created["application"]["id"]

    listed = server.list_applications(status="applied")
    assert listed["ok"] is True
    assert any(a["id"] == app_id for a in listed["applications"])


def test_track_application_unknown_id_returns_structured_error(isolated_db):
    result = server.track_application(
        job_title="X", company="Y", status="saved", application_id=999
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "APPLICATION_NOT_FOUND"


def test_list_applications_invalid_status_returns_structured_error(isolated_db):
    result = server.list_applications(status="ghosted")
    assert result["ok"] is False
    assert result["error"]["code"] == "INVALID_QUERY"
