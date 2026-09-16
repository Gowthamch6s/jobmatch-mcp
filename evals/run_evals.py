#!/usr/bin/env python3
"""Reproducible offline eval suite for the resume-match scorer.

Mirrors the eval pattern used in AI Career Copilot: a fixed set of
resume/job-description cases with expected score bounds and expected
relative rankings, run against the deterministic (no-network,
no-credentials-needed) scoring function. Prints a pass rate and exits
non-zero on any failure so it can gate CI the same way the test suite does.

Usage:
    python evals/run_evals.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jobmatch_mcp.matching import score_match  # noqa: E402

CASES_PATH = Path(__file__).resolve().parent / "cases.json"


def run_threshold_cases(cases: list[dict]) -> tuple[int, int]:
    passed = 0
    for case in cases:
        result = score_match(case["resume_text"], case["job_description"])
        score = result["score"]
        ok = True
        failures = []

        if "min_score" in case and score < case["min_score"]:
            ok = False
            failures.append(f"score {score} < min_score {case['min_score']}")
        if "max_score" in case and score > case["max_score"]:
            ok = False
            failures.append(f"score {score} > max_score {case['max_score']}")
        for term in case.get("must_include_matched", []):
            if term not in result["matched_terms"]:
                ok = False
                failures.append(f"expected matched term '{term}' missing (got {result['matched_terms']})")

        status = "PASS" if ok else "FAIL"
        print(f"[{status}] threshold:{case['id']}  score={score}" + (f"  -- {'; '.join(failures)}" if failures else ""))
        passed += int(ok)
    return passed, len(cases)


def run_ranking_cases(cases: list[dict]) -> tuple[int, int]:
    passed = 0
    for case in cases:
        higher = score_match(case["higher_resume"], case["job_description"])["score"]
        lower = score_match(case["lower_resume"], case["job_description"])["score"]
        ok = higher > lower
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] ranking:{case['id']}  higher_resume={higher}  lower_resume={lower}")
        passed += int(ok)
    return passed, len(cases)


def main() -> int:
    data = json.loads(CASES_PATH.read_text())

    t_passed, t_total = run_threshold_cases(data.get("score_threshold_cases", []))
    r_passed, r_total = run_ranking_cases(data.get("relative_ranking_cases", []))

    total_passed = t_passed + r_passed
    total_cases = t_total + r_total
    pass_rate = (total_passed / total_cases * 100) if total_cases else 0.0

    print()
    print(f"Eval summary: {total_passed}/{total_cases} passed ({pass_rate:.1f}%)")

    return 0 if total_passed == total_cases else 1


if __name__ == "__main__":
    raise SystemExit(main())
