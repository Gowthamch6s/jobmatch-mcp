import pytest

from jobmatch_mcp import adzuna_client
from jobmatch_mcp.config import load_settings
from jobmatch_mcp.errors import InvalidQueryError


@pytest.mark.asyncio
async def test_mock_mode_returns_deterministic_listings():
    settings = load_settings()
    assert settings.has_adzuna_credentials is False

    first = await adzuna_client.search_jobs(settings, "agentic ai engineer", max_results=3)
    second = await adzuna_client.search_jobs(settings, "agentic ai engineer", max_results=3)

    assert first == second  # deterministic, safe for evals/CI
    assert len(first) == 3
    assert all(listing["source"] == "mock" for listing in first)
    assert all("title" in listing and "company" in listing for listing in first)


@pytest.mark.asyncio
async def test_empty_query_raises_invalid_query_error():
    settings = load_settings()
    with pytest.raises(InvalidQueryError):
        await adzuna_client.search_jobs(settings, "   ")


@pytest.mark.asyncio
async def test_max_results_out_of_range_raises_invalid_query_error():
    settings = load_settings()
    with pytest.raises(InvalidQueryError):
        await adzuna_client.search_jobs(settings, "engineer", max_results=50)


@pytest.mark.asyncio
async def test_location_is_reflected_in_mock_listings():
    settings = load_settings()
    listings = await adzuna_client.search_jobs(settings, "ml engineer", location="Tampa, FL", max_results=2)
    assert all(listing["location"] == "Tampa, FL" for listing in listings)
