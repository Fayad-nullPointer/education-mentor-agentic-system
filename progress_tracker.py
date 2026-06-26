"""
progress_tracker.py — Features 3 & 4
Manages exam history and generates progress trend information.
"""

from datetime import datetime, timezone
from typing import Dict, List, Set
from state import ExamRecord

MAX_HISTORY = 50


# ---------------------------------------------------------------------------
# Feature 3 — Exam History
# ---------------------------------------------------------------------------

def record_exam(
    history: List[ExamRecord],
    score_percentage: float,
    total_questions: int,
    weak_topics: Set[str],
) -> List[ExamRecord]:
    """
    Append a new ExamRecord to the exam history list.
    Trims the list to MAX_HISTORY oldest-first.

    Args:
        history:          Existing exam_history list (may be empty).
        score_percentage: Percentage score for this exam (0–100).
        total_questions:  Total number of questions graded.
        weak_topics:      Set of topic strings the student missed.

    Returns:
        New list with the record appended (original list unchanged).
    """
    record = ExamRecord(
        timestamp=datetime.now(timezone.utc).isoformat(),
        score=round(score_percentage, 1),
        total_questions=total_questions,
        weak_topics=sorted(weak_topics),
    )
    updated = list(history) + [record]
    # Keep only the most recent MAX_HISTORY records
    return updated[-MAX_HISTORY:]


# ---------------------------------------------------------------------------
# Feature 4 — Progress Trend Analysis
# ---------------------------------------------------------------------------

def compute_trend(history: List[ExamRecord]) -> Dict:
    """
    Compute trend metrics from exam history.

    Returns a dict with keys:
        has_trend (bool)   — False when fewer than 2 exams
        first_score (float)
        latest_score (float)
        improvement (float) — latest - first (can be negative)
    """
    if len(history) < 2:
        return {"has_trend": False}

    first  = history[0]["score"]
    latest = history[-1]["score"]
    return {
        "has_trend": True,
        "first_score": first,
        "latest_score": latest,
        "improvement": round(latest - first, 1),
    }


def format_progress_section(history: List[ExamRecord]) -> str:
    """
    Render the '### 📈 Progress Trend' section.
    Returns an empty string when there is no history yet.
    """
    if not history:
        return ""

    lines = ["### 📈 Progress Trend\n"]

    for i, record in enumerate(history, start=1):
        lines.append(
            f"- **Exam {i}:** {record['score']:.1f}%  "
            f"({record['total_questions']} questions)"
        )

    trend = compute_trend(history)
    if not trend["has_trend"]:
        lines.append("\n*Not enough history to show a trend.*")
    else:
        delta = trend["improvement"]
        arrow = "📈" if delta >= 0 else "📉"
        sign  = "+" if delta >= 0 else ""
        lines.append(
            f"\n{arrow} **Progress:** {sign}{delta:.1f}% "
            f"(from {trend['first_score']:.1f}% → {trend['latest_score']:.1f}%)"
        )

    return "\n".join(lines)
