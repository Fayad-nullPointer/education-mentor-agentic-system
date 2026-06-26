"""
knowledge_gap.py — Feature 7
Rule-based knowledge gap detection.

If 2 or more topics within a foundational cluster have accuracy below
the GAP_THRESHOLD, the cluster is surfaced as a gap.
"""

from typing import Dict, List
from state import TopicPerformance

# Accuracy threshold below which a topic is considered "at-risk"
GAP_THRESHOLD = 50.0

# Minimum number of weak topics required to declare a cluster gap
MIN_WEAK_IN_CLUSTER = 2

# Cluster → canonical topic keywords (substring matching, case-insensitive)
FOUNDATIONAL_GAPS: Dict[str, List[str]] = {
    "RAG Foundations": [
        "embedding",
        "vector search",
        "vector db",
        "retrieval",
        "rag",
        "chunk",
        "semantic search",
    ],
    "LangGraph Fundamentals": [
        "agentstate",
        "agent state",
        "node",
        "edge",
        "workflow",
        "langgraph",
        "graph",
    ],
    "LLM & Prompting": [
        "prompt",
        "llm",
        "language model",
        "chain",
        "output parser",
        "token",
    ],
    "Agentic Systems": [
        "agent",
        "react",
        "tool",
        "tool call",
        "planner",
        "supervisor",
        "multi-agent",
    ],
}


def detect_knowledge_gaps(profile: Dict[str, TopicPerformance]) -> List[str]:
    """
    Scan the learner profile for foundational knowledge gaps.

    A gap cluster is flagged when at least MIN_WEAK_IN_CLUSTER topics
    whose accuracy is below GAP_THRESHOLD match the cluster's keywords.

    Returns:
        Sorted list of detected cluster names (may be empty).
    """
    if not profile:
        return []

    # Identify at-risk topics
    weak_topics = {
        topic.lower()
        for topic, perf in profile.items()
        if perf["accuracy"] < GAP_THRESHOLD
    }

    detected: List[str] = []
    for cluster_name, keywords in FOUNDATIONAL_GAPS.items():
        matches = sum(
            1
            for weak in weak_topics
            if any(kw in weak for kw in keywords)
        )
        if matches >= MIN_WEAK_IN_CLUSTER:
            detected.append(cluster_name)

    return sorted(detected)


def format_gaps_section(profile: Dict[str, TopicPerformance]) -> str:
    """
    Render the '### 🧩 Knowledge Gaps' section of the report.
    Returns an empty string when no gaps are detected or profile is empty.
    """
    gaps = detect_knowledge_gaps(profile)
    if not gaps:
        return ""

    lines = ["### 🧩 Knowledge Gaps Detected\n"]
    lines.append(
        "The following foundational areas need attention based on your performance history:\n"
    )
    for gap in gaps:
        lines.append(f"- ⚠️ **{gap}**")

    lines.append(
        "\nFocus on these foundations before advancing to more complex topics."
    )
    return "\n".join(lines)
