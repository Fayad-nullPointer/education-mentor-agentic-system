from typing import Dict, List

from app.core.state import TopicPerformance

GAP_THRESHOLD = 50.0
MIN_WEAK_IN_CLUSTER = 2

FOUNDATIONAL_GAPS: Dict[str, List[str]] = {
    "RAG Foundations": ["embedding", "vector search", "vector db", "retrieval", "rag", "chunk", "semantic search"],
    "LangGraph Fundamentals": ["agentstate", "agent state", "node", "edge", "workflow", "langgraph", "graph"],
    "LLM & Prompting": ["prompt", "llm", "language model", "chain", "output parser", "token"],
    "Agentic Systems": ["agent", "react", "tool", "tool call", "planner", "supervisor", "multi-agent"],
}


def detect_knowledge_gaps(profile: Dict[str, TopicPerformance]) -> List[str]:
    if not profile:
        return []
    weak_topics = {
        topic.lower()
        for topic, perf in profile.items()
        if perf["accuracy"] < GAP_THRESHOLD
    }
    detected: List[str] = []
    for cluster_name, keywords in FOUNDATIONAL_GAPS.items():
        matches = sum(1 for weak in weak_topics if any(kw in weak for kw in keywords))
        if matches >= MIN_WEAK_IN_CLUSTER:
            detected.append(cluster_name)
    return sorted(detected)


def format_gaps_section(profile: Dict[str, TopicPerformance]) -> str:
    gaps = detect_knowledge_gaps(profile)
    if not gaps:
        return ""
    lines = ["### 🧩 Knowledge Gaps Detected\n"]
    lines.append("The following foundational areas need attention based on your performance history:\n")
    for gap in gaps:
        lines.append(f"- ⚠️ **{gap}**")
    lines.append("\nFocus on these foundations before advancing to more complex topics.")
    return "\n".join(lines)
