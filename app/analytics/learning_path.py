from typing import Dict, List, Tuple

MAX_STEPS = 4


def build_learning_path(
    weak_topics_sorted: List[Tuple[str, float]],
    course_map: Dict[str, List[Dict]],
) -> List[Dict]:
    path = []
    seen_urls: set = set()
    for topic, accuracy in weak_topics_sorted:
        if len(path) >= MAX_STEPS:
            break
        courses = course_map.get(topic, [])
        chosen = None
        for course in courses:
            url = course.get("url", "")
            if url not in seen_urls:
                chosen = course
                seen_urls.add(url)
                break
        path.append({
            "step": len(path) + 1,
            "topic": topic,
            "accuracy": accuracy,
            "course_title": chosen["title"] if chosen else f"Study {topic}",
            "course_url": chosen["url"] if chosen else "",
            "course_source": chosen["source"] if chosen else "",
        })
    return path


def format_learning_path_section(path: List[Dict]) -> str:
    if not path:
        return ""
    lines = ["### 🗺️ Recommended Learning Path\n"]
    lines.append("Work through these steps in order, starting from your weakest areas:\n")
    for step in path:
        lines.append(f"**Step {step['step']} — {step['topic']}** ({step['accuracy']:.1f}% accuracy)")
        if step["course_url"]:
            lines.append(f"  📖 [{step['course_title']}]({step['course_url']}) *({step['course_source']})*")
        else:
            lines.append(f"  📖 {step['course_title']}")
        lines.append("")
    return "\n".join(lines)
