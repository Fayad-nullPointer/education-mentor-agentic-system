import re
import requests
from typing import Annotated, Dict, Any, List, Tuple

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

import config
from state import Question

# New analytics modules
from analytics import (
    update_learner_profile,
    sorted_topics_by_accuracy,
    format_analytics_section,
)
from progress_tracker import record_exam, format_progress_section
from knowledge_gap import format_gaps_section
from learning_path import build_learning_path, format_learning_path_section
from learner_profile import compute_next_exam_focus, format_remediation_note


# ---------------------------------------------------------------------------
# Answer parsing
# ---------------------------------------------------------------------------

def parse_student_answers(raw_text: str) -> Dict[str, str]:
    """
    Parse '1-b, 2-c, 3-a' style strings into {question_num: answer_letter}.
    Supports hyphen, colon, period, parenthesis, or space as separators.
    """
    pattern = r'(\d+)\s*[\-\:\.\)\s]?\s*([a-fA-F])'
    matches = re.findall(pattern, raw_text)
    return {q_num: ans.lower() for q_num, ans in matches}


# ---------------------------------------------------------------------------
# Tavily course search (with mock fallback + per-topic cache)
# ---------------------------------------------------------------------------

_course_cache: Dict[str, List[Dict[str, Any]]] = {}


def search_courses_tavily(topic: str) -> List[Dict[str, Any]]:
    """
    Query Tavily for courses on *topic*, restricted to approved domains.
    Results are cached in-process so repeat calls for the same topic are free.
    Falls back to a mock database when the API key is absent.
    """
    if topic in _course_cache:
        return _course_cache[topic]

    if not config.TAVILY_API_KEY or config.TAVILY_API_KEY == "your_tavily_api_key_here":
        mock_database = {
            "rag": [
                {"title": "Retrieval-Augmented Generation (RAG) Specialization",
                 "url": "https://www.coursera.org/specializations/rag-systems",
                 "source": "Coursera (Mock)"},
                {"title": "Vector Databases & Embeddings for RAG",
                 "url": "https://www.deeplearning.ai/short-courses/vector-databases-embeddings",
                 "source": "DeepLearning.AI (Mock)"},
                {"title": "Mastering RAG with LangChain and LlamaIndex",
                 "url": "https://www.udemy.com/course/mastering-rag",
                 "source": "Udemy (Mock)"},
            ],
            "langgraph": [
                {"title": "AI Agents in LangGraph",
                 "url": "https://www.deeplearning.ai/short-courses/ai-agents-langgraph",
                 "source": "DeepLearning.AI (Mock)"},
                {"title": "Building Multi-Agent Systems",
                 "url": "https://www.coursera.org/learn/multi-agent-systems",
                 "source": "Coursera (Mock)"},
            ],
            "agent": [
                {"title": "AI Agents in LangGraph",
                 "url": "https://www.deeplearning.ai/short-courses/ai-agents-langgraph",
                 "source": "DeepLearning.AI (Mock)"},
                {"title": "Building AI Agents with Python",
                 "url": "https://www.udemy.com/course/building-ai-agents",
                 "source": "Udemy (Mock)"},
            ],
        }
        topic_lower = topic.lower()
        result = next(
            (courses for key, courses in mock_database.items() if key in topic_lower),
            [
                {"title": f"Introduction to {topic}",
                 "url": "https://www.coursera.org",
                 "source": "Coursera (Mock)"},
                {"title": f"Advanced {topic} Guide",
                 "url": "https://www.deeplearning.ai",
                 "source": "DeepLearning.AI (Mock)"},
            ],
        )
        _course_cache[topic] = result
        return result

    # Live Tavily request
    domains = ["coursera.org", "udemy.com", "deeplearning.ai"]
    payload = {
        "api_key": config.TAVILY_API_KEY,
        "query": f"{topic} course",
        "include_domains": domains,
        "max_results": 3,
    }
    try:
        response = requests.post("https://api.tavily.com/search", json=payload, timeout=10)
        response.raise_for_status()
        items = response.json().get("results", [])
        result = [
            {
                "title": item.get("title", "Course link"),
                "url": item.get("url", ""),
                "source": item.get("url", "").split("/")[2] if "/" in item.get("url", "") else "Course Platform",
            }
            for item in items
        ]
    except Exception as e:
        print(f"Warning: Tavily search failed ({e}). Using fallback.")
        result = [
            {"title": f"{topic} Course",
             "url": f"https://www.coursera.org/search?query={topic.replace(' ', '+')}",
             "source": "Coursera"},
        ]
    _course_cache[topic] = result
    return result


# ---------------------------------------------------------------------------
# LLM mistake explanation
# ---------------------------------------------------------------------------

def generate_mistake_explanation(question: Question, user_ans: str) -> str:
    """
    Use the configured LLM to explain why the student's answer was wrong.
    Falls back to a static template if no API key is available.
    """
    options_str    = "\n".join([f"  {k}) {v}" for k, v in question["options"].items()])
    correct_text   = question["options"].get(question["correct_option"], "")
    user_text      = question["options"].get(user_ans, "Unknown Option")

    has_api_key = (
        (config.GEMINI_API_KEY and config.GEMINI_API_KEY != "your_gemini_api_key_here")
        or (config.OPENAI_API_KEY and config.OPENAI_API_KEY != "your_openai_api_key_here")
    )

    if not has_api_key:
        return (
            f"The correct option is '{question['correct_option']}' ({correct_text}). "
            f"You selected '{user_ans}' ({user_text}). "
            f"Please review '{question['topic']}' to understand why "
            f"'{question['correct_option']}' is correct."
        )

    try:
        model = config.get_model()
        prompt = ChatPromptTemplate.from_messages([
            ("system",
             "You are an expert AI engineering tutor. The student answered a question "
             "incorrectly. Explain why the correct answer is correct and why the student's "
             "chosen answer is incorrect. Keep it brief (1-2 sentences), direct, and encouraging."),
            ("user",
             "Question: {question}\nOptions:\n{options}\n"
             "Correct Option: {correct_option} - {correct_text}\n"
             "Student Selected: {user_option} - {user_text}"),
        ])
        chain = prompt | model | StrOutputParser()
        return chain.invoke({
            "question":      question["question"],
            "options":       options_str,
            "correct_option": question["correct_option"],
            "correct_text":  correct_text,
            "user_option":   user_ans,
            "user_text":     user_text,
        }).strip()
    except Exception as e:
        print(f"Warning: LLM explanation failed: {e}")
        return (
            f"Correct option is '{question['correct_option']}' ({correct_text}). "
            f"Your option was '{user_ans}' ({user_text})."
        )


# ---------------------------------------------------------------------------
# Main grading tool
# ---------------------------------------------------------------------------

@tool
def grade_exam(student_answers: str, state: Annotated[dict, InjectedState]) -> str:
    """
    Parse student answers, grade them against the active exam in AgentState,
    generate LLM mistake explanations with optional RAG remediation notes,
    update the learner profile and exam history in state, and return a
    comprehensive markdown report.

    Args:
        student_answers: Free-text answers, e.g. '1-b, 2-c, 3-a, 4-d, 5-b'.
    """
    # ── 1. Retrieve active exam ───────────────────────────────────────────
    active_exam: List[Question] = state.get("active_exam")
    if not active_exam:
        return (
            "Error: No active exam found in the agent state. "
            "Please request an exam first before submitting answers."
        )

    # ── 2. Parse answers ──────────────────────────────────────────────────
    parsed_answers = parse_student_answers(student_answers)
    if not parsed_answers:
        return (
            "Could not parse any answers from your input. "
            "Please use a format like: '1-b, 2-c, 3-a, 4-d, 5-b'."
        )

    # ── 3. Grade responses ────────────────────────────────────────────────
    correct_count    = 0
    total_questions  = len(active_exam)
    mistakes         = []
    weak_topics: set = set()

    graded_questions: List[Tuple[Question, bool]] = []  # for profile update

    for question in active_exam:
        q_id_str    = str(question["id"])
        correct_opt = question["correct_option"].lower()
        student_opt = parsed_answers.get(q_id_str)
        if student_opt is not None:
            student_opt = student_opt.lower()

        is_correct = student_opt == correct_opt
        graded_questions.append((question, is_correct))

        if is_correct:
            correct_count += 1
        else:
            user_ans = student_opt if student_opt else "unanswered"
            mistakes.append({"question": question, "user_answer": user_ans})
            weak_topics.add(question["topic"])

    score_percentage = (correct_count / total_questions) * 100

    # ── 4. Update learner profile (Feature 1) ─────────────────────────────
    existing_profile = state.get("learner_profile") or {}
    updated_profile  = update_learner_profile(existing_profile, graded_questions)
    state["learner_profile"] = updated_profile

    # ── 5. Record exam history (Feature 3) ───────────────────────────────
    existing_history = state.get("exam_history") or []
    updated_history  = record_exam(
        existing_history, score_percentage, total_questions, weak_topics
    )
    state["exam_history"] = updated_history

    # ── 6. Adaptive exam focus (Feature 5) ───────────────────────────────
    state["next_exam_focus"] = compute_next_exam_focus(updated_profile)

    # ── 7. Fetch courses (deduplicated via cache) ─────────────────────────
    # Build a map of topic → courses for the learning path builder
    course_map: Dict[str, List[Dict]] = {}
    for topic in weak_topics:
        course_map[topic] = search_courses_tavily(topic)

    # ── 8. Generate mistake feedback with RAG remediation ─────────────────
    mistakes_feedback: List[str] = []
    for mistake in mistakes:
        question = mistake["question"]
        user_ans = mistake["user_answer"]
        explanation   = generate_mistake_explanation(question, user_ans)
        remediation   = format_remediation_note(question["topic"])  # Feature 9

        block = (
            f"**Question {question['id']}:** {question['question']}\n"
            f"- *Your Answer:* {user_ans.upper()}\n"
            f"- *Correct Answer:* {question['correct_option'].upper()}\n"
            f"- *Explanation:* {explanation}\n"
        )
        if remediation:
            block += remediation + "\n"
        mistakes_feedback.append(block)

    # ── 9. Legacy course recommendations (up to 3, original behaviour) ────
    course_recommendations: List[str] = []
    all_courses: List[Tuple[str, Dict]] = []
    for topic in list(weak_topics)[:3]:
        courses = course_map.get(topic, [])
        if courses:
            all_courses.append((topic, courses[0]))
    # top up to 3
    if len(all_courses) < 3:
        for topic in weak_topics:
            for course in course_map.get(topic, [])[1:]:
                if len(all_courses) >= 3:
                    break
                all_courses.append((topic, course))
            if len(all_courses) >= 3:
                break
    for topic, course in all_courses[:3]:
        course_recommendations.append(
            f"- **{course['title']}** ({course['source']})\n"
            f"  Link: {course['url']} *(Topic: {topic})*"
        )

    # ── 10. Build ordered learning path (Feature 8) ───────────────────────
    sorted_weak = [
        (topic, updated_profile[topic]["accuracy"])
        for topic in weak_topics
        if topic in updated_profile
    ]
    sorted_weak.sort(key=lambda x: x[1])  # weakest first
    learning_path = build_learning_path(sorted_weak, course_map)

    # ── 11. Assemble final report ─────────────────────────────────────────
    report: List[str] = []

    # Header + score
    report.append("## 📝 Exam Grading Report\n")
    report.append(f"**Score:** {correct_count}/{total_questions} ({score_percentage:.1f}%)\n")

    if correct_count == total_questions:
        report.append("🎉 Perfect score! Excellent understanding of the material.\n")
    else:
        # Mistakes & explanations
        report.append("### 🔍 Incorrect Answers & Explanations\n")
        report.append("\n".join(mistakes_feedback))

    # Analytics (Features 2, 6, 10)
    analytics_block = format_analytics_section(updated_profile)
    if analytics_block:
        report.append(analytics_block)

    # Knowledge gaps (Feature 7)
    gaps_block = format_gaps_section(updated_profile)
    if gaps_block:
        report.append(gaps_block)

    # Progress trend (Feature 4)
    trend_block = format_progress_section(updated_history)
    if trend_block:
        report.append(trend_block)

    # Learning path (Feature 8)
    path_block = format_learning_path_section(learning_path)
    if path_block:
        report.append(path_block)

    # Legacy course recommendations
    if course_recommendations and correct_count < total_questions:
        report.append("### 📚 Recommended Courses\n")
        report.append(
            "Based on the topics you missed, here are some recommended courses "
            "to strengthen your knowledge:\n"
        )
        report.append("\n".join(course_recommendations))

    return "\n\n".join(filter(None, report))