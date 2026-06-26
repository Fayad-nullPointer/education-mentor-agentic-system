"""
learner_profile.py — Features 5 & 9

Feature 5: Adaptive Exam Targeting
    Derive `next_exam_focus` from the learner profile so Team 2's
    Exam Generator can bias future exams toward weak topics.

Feature 9: RAG Remediation Integration
    Provides a get_remediation_material() interface that Team 1 can
    implement. Falls back gracefully when RAG is unavailable.
"""

from typing import Dict, List, Optional, Tuple
from state import TopicPerformance

# Maximum number of weak topics to surface for the next exam
MAX_FOCUS_TOPICS = 3

# Accuracy threshold below which a topic is considered "needs focus"
FOCUS_THRESHOLD = 70.0


# ---------------------------------------------------------------------------
# Feature 5 — Adaptive Exam Targeting
# ---------------------------------------------------------------------------

def compute_next_exam_focus(
    profile: Dict[str, TopicPerformance],
) -> List[str]:
    """
    Identify the weakest topics (accuracy < FOCUS_THRESHOLD) to suggest
    to Team 2's Exam Generator for the next exam.

    Returns a list of topic strings, weakest first, capped at MAX_FOCUS_TOPICS.
    Topics with zero attempts are excluded.
    """
    if not profile:
        return []

    candidates: List[Tuple[float, str]] = [
        (perf["accuracy"], topic)
        for topic, perf in profile.items()
        if perf["attempts"] > 0 and perf["accuracy"] < FOCUS_THRESHOLD
    ]

    # Sort ascending by accuracy (weakest first)
    candidates.sort()
    return [topic for _, topic in candidates[:MAX_FOCUS_TOPICS]]


# ---------------------------------------------------------------------------
# Feature 9 — RAG Remediation Integration
# ---------------------------------------------------------------------------

def get_remediation_material(topic: str) -> Optional[Dict]:
    """
    Integration point for Team 1's RAG subsystem.

    Team 1 should replace the body of this function with a real Qdrant
    retrieval call.  Until then it returns None so the grader falls back
    gracefully.

    Expected return schema:
        {
            "title":   str,   # e.g. "Vector Embeddings — Chapter 3"
            "source":  str,   # e.g. "Foundations of LLMs, p. 47"
            "excerpt": str,   # short passage (<= 2 sentences)
        }
    """
    # ── Team 1 integration hook ──────────────────────────────────────────
    # Example implementation (replace with actual RAG call):
    #
    # from rag_tool import retrieve
    # results = retrieve(query=topic, top_k=1)
    # if results:
    #     return {
    #         "title":   results[0]["title"],
    #         "source":  results[0]["source"],
    #         "excerpt": results[0]["text"][:300],
    #     }
    # ─────────────────────────────────────────────────────────────────────

    return None  # graceful fallback until Team 1 wires in


def format_remediation_note(topic: str) -> str:
    """
    Returns an inline remediation note for a missed question.
    Fetches material from the RAG layer if available; otherwise empty string.
    """
    material = get_remediation_material(topic)
    if not material:
        return ""

    return (
        f"\n  📌 **Recommended Reading:** {material['title']}  \n"
        f"  *Source: {material['source']}*  \n"
        f"  > {material['excerpt']}"
    )
