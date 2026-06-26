"""
analytics.py — Feature 1, 2, 6, 10
Handles topic-level performance tracking, mastery classification, and readiness scoring.
All functions are pure and stateless; they take data in and return data/strings out.
"""

from typing import Dict, List, Tuple
from state import TopicPerformance, Question


# ---------------------------------------------------------------------------
# Feature 6 — Mastery Level Classification
# ---------------------------------------------------------------------------

def get_mastery_level(accuracy: float) -> str:
    """Return a human-readable mastery label for a given accuracy percentage."""
    if accuracy >= 90:
        return "Mastered"
    if accuracy >= 70:
        return "Advanced"
    if accuracy >= 40:
        return "Intermediate"
    return "Beginner"


# ---------------------------------------------------------------------------
# Feature 1 — Topic Performance Analytics
# ---------------------------------------------------------------------------

def update_learner_profile(
    profile: Dict[str, TopicPerformance],
    graded_questions: List[Tuple[Question, bool]],
) -> Dict[str, TopicPerformance]:
    """
    Mutate (or initialise) the learner profile with results from the current exam.

    Args:
        profile:           Existing learner_profile dict (may be empty).
        graded_questions:  List of (Question, was_correct) pairs.

    Returns:
        Updated learner_profile dict.
    """
    updated = dict(profile)  # shallow copy to avoid mutating caller's dict

    for question, is_correct in graded_questions:
        topic = question["topic"]

        if topic not in updated:
            updated[topic] = TopicPerformance(attempts=0, correct=0, accuracy=0.0)

        entry = dict(updated[topic])  # copy so we don't mutate in place
        entry["attempts"] += 1
        if is_correct:
            entry["correct"] += 1
        entry["accuracy"] = round((entry["correct"] / entry["attempts"]) * 100, 1)

        updated[topic] = TopicPerformance(**entry)

    return updated


def sorted_topics_by_accuracy(
    profile: Dict[str, TopicPerformance],
) -> List[Tuple[str, TopicPerformance]]:
    """Return profile items sorted weakest → strongest by accuracy."""
    return sorted(profile.items(), key=lambda x: x[1]["accuracy"])


# ---------------------------------------------------------------------------
# Feature 10 — Readiness Score
# ---------------------------------------------------------------------------

def compute_readiness_score(profile: Dict[str, TopicPerformance]) -> float:
    """Return the mean accuracy across all tracked topics, or 0.0 if none."""
    if not profile:
        return 0.0
    return round(sum(v["accuracy"] for v in profile.values()) / len(profile), 1)


def get_readiness_label(score: float) -> str:
    """Return a readiness status label for the given overall score."""
    if score >= 90:
        return "Highly Prepared"
    if score >= 70:
        return "Ready"
    if score >= 40:
        return "Developing"
    return "Not Ready"


# ---------------------------------------------------------------------------
# Feature 2 — Learning Analytics Report Section (formatting)
# ---------------------------------------------------------------------------

def format_analytics_section(profile: Dict[str, TopicPerformance]) -> str:
    """
    Render the '### 📊 Learning Analytics' section of the grading report.
    Returns an empty string if profile is empty.
    """
    if not profile:
        return ""

    lines: List[str] = ["### 📊 Topic Analytics\n"]

    sorted_items = sorted_topics_by_accuracy(profile)

    # Topic performance table
    lines.append("**Topic Performance**\n")
    for topic, perf in sorted_items:
        bar_filled = int(perf["accuracy"] / 10)           # 0–10 blocks
        bar_empty  = 10 - bar_filled
        bar = "█" * bar_filled + "░" * bar_empty
        mastery = get_mastery_level(perf["accuracy"])
        lines.append(
            f"- **{topic}** `{bar}` {perf['accuracy']:.1f}%  "
            f"({perf['correct']}/{perf['attempts']}) — *{mastery}*"
        )

    # Strongest / weakest call-outs
    if sorted_items:
        weakest_topic, weakest_perf = sorted_items[0]
        strongest_topic, strongest_perf = sorted_items[-1]

        lines.append("")
        lines.append(f"🏆 **Strongest Topic:** {strongest_topic} ({strongest_perf['accuracy']:.1f}%)")
        lines.append(f"⚠️ **Weakest Topic:** {weakest_topic} ({weakest_perf['accuracy']:.1f}%)")

    # Mastery level breakdown
    lines.append("\n**Topic Mastery Levels**\n")
    for topic, perf in sorted_items:
        lines.append(f"- {topic}: *{get_mastery_level(perf['accuracy'])}*")

    # Readiness score
    readiness = compute_readiness_score(profile)
    label = get_readiness_label(readiness)
    lines.append(f"\n### 🎯 Readiness Score\n")
    lines.append(f"**{readiness:.1f}%** — *{label}*")

    return "\n".join(lines)
