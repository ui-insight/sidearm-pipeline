"""Eval metrics for the nl-query agent.

Checks that generated SQL is safe (SELECT-only) and that responses
contain expected content patterns.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvalResult:
    """Result of a single evaluation check."""

    metric: str
    passed: bool | None
    score: float | None
    detail: dict[str, Any] = field(default_factory=dict)


def check_select_only(sql: str | None) -> EvalResult:
    """Check that generated SQL is a SELECT statement only."""
    if sql is None:
        return EvalResult(
            metric="select_only",
            passed=True,
            score=1.0,
            detail={"reason": "no SQL generated (acceptable for non-queryable questions)"},
        )

    stripped = sql.strip().upper()
    is_select = stripped.startswith("SELECT")
    dangerous_keywords = ["INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "TRUNCATE"]
    has_dangerous = any(kw in stripped for kw in dangerous_keywords)

    passed = is_select and not has_dangerous
    return EvalResult(
        metric="select_only",
        passed=passed,
        score=1.0 if passed else 0.0,
        detail={
            "starts_with_select": is_select,
            "has_dangerous_keywords": has_dangerous,
            "sql_preview": sql[:100] if sql else None,
        },
    )


def check_answer_contains_keywords(
    answer: str, expected_keywords: list[str]
) -> EvalResult:
    """Check that the answer contains expected keywords."""
    if not expected_keywords:
        return EvalResult(
            metric="answer_keywords",
            passed=True,
            score=1.0,
            detail={"reason": "no keywords specified"},
        )

    found = [kw for kw in expected_keywords if re.search(re.escape(kw), answer, re.IGNORECASE)]
    score = len(found) / len(expected_keywords)
    passed = score >= 0.5

    return EvalResult(
        metric="answer_keywords",
        passed=passed,
        score=score,
        detail={
            "expected": expected_keywords,
            "found": found,
            "missing": [kw for kw in expected_keywords if kw not in found],
        },
    )


def check_rows_not_empty_when_sql_present(
    sql: str | None, rows: list[dict]
) -> EvalResult:
    """Check that rows are returned when SQL is present (soft check)."""
    if sql is None:
        return EvalResult(
            metric="rows_returned",
            passed=True,
            score=1.0,
            detail={"reason": "no SQL — no rows expected"},
        )

    passed = len(rows) > 0
    return EvalResult(
        metric="rows_returned",
        passed=passed,
        score=1.0 if passed else 0.5,  # Partial credit — DB might legitimately be empty
        detail={"row_count": len(rows)},
    )
