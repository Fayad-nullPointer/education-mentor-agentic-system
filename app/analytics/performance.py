from typing import Dict, List, Tuple

from app.core.state import TopicPerformance, Question


def get_mastery_level(accuracy: float) -> str:
    if accuracy >= 90:
        return "Mastered"
    if accuracy >= 70:
        return "Advanced"
    if accuracy >= 40:
        return "Intermediate"
    return "Beginner"


def update_learner_profile(
    profile: Dict[str, TopicPerformance],
    graded_questions: List[Tuple[Question, bool]],
) -> Dict[str, TopicPerformance]:
    updated = dict(profile)
    for question, is_correct in graded_questions:
        topic = question["topic"]
        if topic not in updated:
            updated[topic] = TopicPerformance(attempts=0, correct=0, accuracy=0.0)
        entry = dict(updated[topic])
        entry["attempts"] += 1
        if is_correct:
            entry["correct"] += 1
        entry["accuracy"] = round((entry["correct"] / entry["attempts"]) * 100, 1)
        updated[topic] = TopicPerformance(**entry)
    return updated


def sorted_topics_by_accuracy(
    profile: Dict[str, TopicPerformance],
) -> List[Tuple[str, TopicPerformance]]:
    return sorted(profile.items(), key=lambda x: x[1]["accuracy"])


def compute_readiness_score(profile: Dict[str, TopicPerformance]) -> float:
    if not profile:
        return 0.0
    return round(sum(v["accuracy"] for v in profile.values()) / len(profile), 1)


def get_readiness_label(score: float) -> str:
    if score >= 90:
        return "Highly Prepared"
    if score >= 70:
        return "Ready"
    if score >= 40:
        return "Developing"
    return "Not Ready"


def format_analytics_section(profile: Dict[str, TopicPerformance]) -> str:
    if not profile:
        return ""

    lines: List[str] = ["### 📊 Topic Analytics\n"]
    sorted_items = sorted_topics_by_accuracy(profile)

    lines.append("**Topic Performance**\n")
    for topic, perf in sorted_items:
        bar_filled = int(perf["accuracy"] / 10)
        bar = "█" * bar_filled + "░" * (10 - bar_filled)
        mastery = get_mastery_level(perf["accuracy"])
        lines.append(
            f"- **{topic}** `{bar}` {perf['accuracy']:.1f}%  "
            f"({perf['correct']}/{perf['attempts']}) — *{mastery}*"
        )

    if sorted_items:
        weakest_topic, weakest_perf = sorted_items[0]
        strongest_topic, strongest_perf = sorted_items[-1]
        lines.append("")
        lines.append(f"🏆 **Strongest Topic:** {strongest_topic} ({strongest_perf['accuracy']:.1f}%)")
        lines.append(f"⚠️ **Weakest Topic:** {weakest_topic} ({weakest_perf['accuracy']:.1f}%)")

    lines.append("\n**Topic Mastery Levels**\n")
    for topic, perf in sorted_items:
        lines.append(f"- {topic}: *{get_mastery_level(perf['accuracy'])}*")

    readiness = compute_readiness_score(profile)
    label = get_readiness_label(readiness)
    lines.append(f"\n### 🎯 Readiness Score\n")
    lines.append(f"**{readiness:.1f}%** — *{label}*")

    return "\n".join(lines)
