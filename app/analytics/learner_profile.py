from typing import Dict, List, Optional, Tuple

from app.core.state import TopicPerformance

MAX_FOCUS_TOPICS = 3
FOCUS_THRESHOLD = 70.0


def compute_next_exam_focus(profile: Dict[str, TopicPerformance]) -> List[str]:
    if not profile:
        return []
    candidates: List[Tuple[float, str]] = [
        (perf["accuracy"], topic)
        for topic, perf in profile.items()
        if perf["attempts"] > 0 and perf["accuracy"] < FOCUS_THRESHOLD
    ]
    candidates.sort()
    return [topic for _, topic in candidates[:MAX_FOCUS_TOPICS]]


def get_remediation_material(topic: str) -> Optional[Dict]:
    """
    Integration hook: wire this to rag_search for per-topic retrieval.
    Returns None until connected.
    """
    return None


def format_remediation_note(topic: str) -> str:
    material = get_remediation_material(topic)
    if not material:
        return ""
    return (
        f"\n  📌 **Recommended Reading:** {material['title']}  \n"
        f"  *Source: {material['source']}*  \n"
        f"  > {material['excerpt']}"
    )
