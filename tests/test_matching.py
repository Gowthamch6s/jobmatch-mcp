from jobmatch_mcp.matching import score_match

STRONG_RESUME = """
Agentic AI Engineer. Built LangGraph multi-agent systems with FastAPI,
PostgreSQL, and Docker. Experience with RAG, LLMs, Python, and E2B
sandboxed execution. Shipped a Next.js dashboard for real-time monitoring.
"""

WEAK_RESUME = """
Marketing coordinator. Managed social media campaigns, wrote newsletters,
coordinated events, and tracked engagement metrics in spreadsheets.
"""

JOB_DESCRIPTION = """
We are hiring an Agentic AI Engineer with strong Python skills, experience
building multi-agent systems with LangGraph, RAG pipelines, FastAPI
backends, and Docker deployments. PostgreSQL experience is a plus.
"""


def test_strong_resume_scores_higher_than_weak_resume():
    strong = score_match(STRONG_RESUME, JOB_DESCRIPTION)
    weak = score_match(WEAK_RESUME, JOB_DESCRIPTION)
    assert strong["score"] > weak["score"]
    assert strong["score"] >= 50
    assert weak["score"] <= 20


def test_matched_terms_include_key_skills():
    result = score_match(STRONG_RESUME, JOB_DESCRIPTION)
    assert "python" in result["matched_terms"]
    assert "langgraph" in result["matched_terms"]


def test_missing_terms_surface_gaps():
    result = score_match(WEAK_RESUME, JOB_DESCRIPTION)
    assert "python" in result["missing_terms"] or "langgraph" in result["missing_terms"]


def test_empty_job_description_yields_zero_score():
    result = score_match(STRONG_RESUME, "")
    assert result["score"] == 0
    assert result["matched_terms"] == []


def test_score_is_bounded_0_to_100():
    result = score_match(STRONG_RESUME, JOB_DESCRIPTION)
    assert 0 <= result["score"] <= 100
