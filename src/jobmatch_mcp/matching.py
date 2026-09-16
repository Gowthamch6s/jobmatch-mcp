"""Resume-to-job match scoring.

Deliberately dependency-light (no sklearn/embeddings) so the server has
no heavy ML install and stays fast and deterministic for evals: a plain
TF-IDF-style term-overlap score over the job description, with a bonus
weight for recognized technical skill terms. Swappable later for an
embedding-based scorer behind the same `score_match` function signature
without touching the tool layer.
"""

from __future__ import annotations

import math
import re
from collections import Counter

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
    "have", "in", "is", "it", "of", "on", "or", "our", "team", "that",
    "the", "this", "to", "we", "will", "with", "you", "your", "role",
    "experience", "work", "using", "years", "strong", "ability", "preferred",
}

# A small curated vocabulary of technical skill terms gets extra weight,
# since a resume matching "Docker" or "LangGraph" is a stronger signal
# than matching a filler word like "environment".
_SKILL_TERMS = {
    "python", "javascript", "typescript", "java", "c++", "sql", "bash",
    "pytorch", "tensorflow", "keras", "scikit-learn", "huggingface",
    "langchain", "langgraph", "llamaindex", "rag", "llm", "llms", "nlp",
    "agent", "agentic", "mcp", "fastapi", "docker", "kubernetes", "ci/cd",
    "postgresql", "mongodb", "azure", "aws", "gcp", "react", "nextjs",
    "pinecone", "chromadb", "faiss", "mlflow", "e2b", "ollama", "groq",
}

_TOKEN_RE = re.compile(r"[a-zA-Z0-9+#.\-]+")


def _tokenize(text: str) -> list[str]:
    tokens = [t.lower().strip(".-") for t in _TOKEN_RE.findall(text)]
    return [t for t in tokens if t and t not in _STOPWORDS and len(t) > 1]


def score_match(resume_text: str, job_description: str) -> dict:
    """Score how well a resume matches a job description.

    Returns a dict with a 0-100 `score`, the `matched_terms` that drove it
    (skills weighted first), and `missing_terms` the resume lacks that the
    posting emphasizes -- useful for the caller to show "gaps to close".
    """
    resume_tokens = set(_tokenize(resume_text))
    job_tokens = _tokenize(job_description)
    job_counts = Counter(job_tokens)
    unique_job_terms = set(job_tokens)

    if not unique_job_terms:
        return {"score": 0, "matched_terms": [], "missing_terms": []}

    matched: list[tuple[str, float]] = []
    missing: list[str] = []
    weighted_matched_score = 0.0
    weighted_total = 0.0

    for term in unique_job_terms:
        # log-scaled term frequency in the job posting as an importance proxy
        weight = 1.0 + math.log(1 + job_counts[term])
        if term in _SKILL_TERMS:
            weight *= 2.5
        weighted_total += weight
        if term in resume_tokens:
            weighted_matched_score += weight
            matched.append((term, weight))
        else:
            missing.append(term)

    raw_score = weighted_matched_score / weighted_total if weighted_total else 0.0
    score = round(min(raw_score, 1.0) * 100)

    matched.sort(key=lambda pair: pair[1], reverse=True)
    missing_sorted = sorted(missing, key=lambda t: job_counts[t] * (2.5 if t in _SKILL_TERMS else 1), reverse=True)

    return {
        "score": score,
        "matched_terms": [term for term, _ in matched[:15]],
        "missing_terms": missing_sorted[:15],
    }
