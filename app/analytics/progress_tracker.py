from datetime import datetime, timezone
from typing import Dict, List, Set

from app.core.state import ExamRecord

MAX_HISTORY = 50


def record_exam(
    history: List[ExamRecord],
    score_percentage: float,
    total_questions: int,
    weak_topics: Set[str],
) -> List[ExamRecord]:
    record = ExamRecord(
        timestamp=datetime.now(timezone.utc).isoformat(),
        score=round(score_percentage, 1),
        total_questions=total_questions,
        weak_topics=sorted(weak_topics),
    )
    return (list(history) + [record])[-MAX_HISTORY:]


def compute_trend(history: List[ExamRecord]) -> Dict:
    if len(history) < 2:
        return {"has_trend": False}
    first = history[0]["score"]
    latest = history[-1]["score"]
    return {
        "has_trend": True,
        "first_score": first,
        "latest_score": latest,
        "improvement": round(latest - first, 1),
    }


def format_progress_section(history: List[ExamRecord]) -> str:
    if not history:
        return ""
    lines = ["### 📈 Progress Trend\n"]
    for i, record in enumerate(history, start=1):
        lines.append(f"- **Exam {i}:** {record['score']:.1f}%  ({record['total_questions']} questions)")
    trend = compute_trend(history)
    if not trend["has_trend"]:
        lines.append("\n*Not enough history to show a trend.*")
    else:
        delta = trend["improvement"]
        arrow = "📈" if delta >= 0 else "📉"
        sign = "+" if delta >= 0 else ""
        lines.append(
            f"\n{arrow} **Progress:** {sign}{delta:.1f}% "
            f"(from {trend['first_score']:.1f}% → {trend['latest_score']:.1f}%)"
        )
    return "\n".join(lines)
