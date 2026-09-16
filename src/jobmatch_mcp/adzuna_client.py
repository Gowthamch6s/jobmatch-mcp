"""Adzuna job search client with a deterministic mock fallback.

Real mode: calls the Adzuna Search API (https://developer.adzuna.com/)
using ADZUNA_APP_ID / ADZUNA_APP_KEY read server-side from config.py.
Mock mode: if credentials are absent, returns deterministic sample
listings generated from the query itself. This keeps the server fully
runnable, demoable, and testable (including in CI) without secrets,
while making it obvious to a caller which mode produced a result via
the `source` field on every listing.
"""

from __future__ import annotations

import httpx

from .config import Settings
from .errors import (
    InvalidQueryError,
    NoResultsFoundError,
    UpstreamRateLimitedError,
    UpstreamUnavailableError,
)

ADZUNA_BASE_URL = "https://api.adzuna.com/v1/api/jobs"
DEFAULT_COUNTRY = "us"


def _mock_listings(query: str, location: str | None, max_results: int) -> list[dict]:
    """Deterministic, offline sample data -- same query always returns the
    same listings, so tests and evals don't depend on network state."""
    seed_companies = [
        "Vertex Analytics",
        "Northwind Robotics",
        "Cobalt Systems",
        "Fieldstone AI",
        "Harborlight Labs",
    ]
    query_title = query.title()
    role_suffix = "" if "engineer" in query.lower() else " Engineer"

    listings = []
    for i, company in enumerate(seed_companies[:max_results]):
        listings.append(
            {
                "title": f"{query_title}{role_suffix}" if i % 2 == 0 else f"Senior {query_title}{role_suffix}",
                "company": company,
                "location": location or "Remote",
                "description": (
                    f"We are hiring for a {query} role. Experience with Python, "
                    f"APIs, and cloud deployment preferred. Team of 5-10 engineers."
                ),
                "url": f"https://example.invalid/jobs/{company.lower().replace(' ', '-')}-{i}",
                "salary_min": 90000 + i * 5000,
                "salary_max": 130000 + i * 5000,
                "source": "mock",
            }
        )
    return listings


async def search_jobs(
    settings: Settings,
    query: str,
    location: str | None = None,
    max_results: int = 5,
) -> list[dict]:
    if not query or not query.strip():
        raise InvalidQueryError("`query` must be a non-empty job title or keyword string.")
    if not (1 <= max_results <= 20):
        raise InvalidQueryError("`max_results` must be between 1 and 20.")

    if not settings.has_adzuna_credentials:
        results = _mock_listings(query.strip(), location, max_results)
        if not results:
            raise NoResultsFoundError(f"No mock listings generated for query '{query}'.")
        return results

    params = {
        "app_id": settings.adzuna_app_id,
        "app_key": settings.adzuna_app_key,
        "what": query,
        "results_per_page": max_results,
    }
    if location:
        params["where"] = location

    url = f"{ADZUNA_BASE_URL}/{DEFAULT_COUNTRY}/search/1"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
    except httpx.RequestError as exc:
        raise UpstreamUnavailableError(f"Could not reach Adzuna: {exc}") from exc

    if response.status_code == 429:
        raise UpstreamRateLimitedError("Adzuna rate limit hit; retry after a short backoff.")
    if response.status_code >= 500:
        raise UpstreamUnavailableError(f"Adzuna returned server error {response.status_code}.")
    if response.status_code >= 400:
        raise InvalidQueryError(f"Adzuna rejected the request ({response.status_code}): {response.text[:200]}")

    payload = response.json()
    raw_results = payload.get("results", [])
    if not raw_results:
        raise NoResultsFoundError(f"No live listings found for query '{query}'.")

    listings = []
    for item in raw_results[:max_results]:
        listings.append(
            {
                "title": item.get("title", "Untitled role"),
                "company": (item.get("company") or {}).get("display_name", "Unknown company"),
                "location": (item.get("location") or {}).get("display_name", location or "Unknown"),
                "description": (item.get("description") or "")[:500],
                "url": item.get("redirect_url", ""),
                "salary_min": item.get("salary_min"),
                "salary_max": item.get("salary_max"),
                "source": "adzuna",
            }
        )
    return listings
