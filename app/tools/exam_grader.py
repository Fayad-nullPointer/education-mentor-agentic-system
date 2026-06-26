"""
Exam grader tool — grades student answers against the active exam in AgentState.
Ported from feature/adaptive-learning-intelligence-engine (most complete version).
Replaces config.get_model() with get_llm() (Gemini only).
"""

import re
from typing import Annotated, Any

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from app.analytics.knowledge_gap import format_gaps_section
from app.analytics.learner_profile import compute_next_exam_focus, format_remediation_note
from app.analytics.learning_path import build_learning_path, format_learning_path_section
from app.analytics.performance import format_analytics_section, update_learner_profile
from app.analytics.progress_tracker import format_progress_section, record_exam
from app.core.llm import get_llm
from app.tools.course_search import search_courses_for_topic


def _parse_student_answers(raw_text: str) -> dict[str, str]:
    """Parse '1-b, 2-c, 3-a' style answers into {question_num: answer_letter}."""
    pattern = r"(\d+)\s*[\-\:\.\)\s]?\s*([a-fA-F])"
    matches = re.findall(pattern, raw_text)
    return {q_num: ans.lower() for q_num, ans in matches}


def _explain_mistake(question: dict[str, Any], user_ans: str) -> str:
    options_str = "\n".join([f"  {k}) {v}" for k, v in question["options"].items()])
    correct_text = question["options"].get(question["correct_option"], "")
    user_text = question["options"].get(user_ans, "Unknown Option")

    try:
        llm = get_llm()
        prompt = ChatPromptTemplate.from_messages([
            ("system",
             "You are an expert AI engineering tutor. The student answered a question incorrectly. "
             "Explain why the correct answer is correct and why the student's chosen answer is incorrect. "
             "Keep it brief (1-2 sentences), direct, and encouraging."),
            ("user",
             "Question: {question}\nOptions:\n{options}\n"
             "Correct Option: {correct_option} - {correct_text}\n"
             "Student Selected: {user_option} - {user_text}"),
        ])
        chain = prompt | llm | StrOutputParser()
        return chain.invoke({
            "question": question["question"],
            "options": options_str,
            "correct_option": question["correct_option"],
            "correct_text": correct_text,
            "user_option": user_ans,
            "user_text": user_text,
        }).strip()
    except Exception as e:
        print(f"Warning: LLM explanation failed: {e}")
        return f"Correct option is '{question['correct_option']}' ({correct_text}). Your option was '{user_ans}' ({user_text})."


@tool
def grade_exam(
    student_answers: str,
    tool_call_id: Annotated[str, InjectedToolCallId] = "",
    state: Annotated[dict, InjectedState] = None,
) -> Command:
    """
    Parse student answers, grade them against the active exam, generate mistake explanations,
    update learner profile and exam history, and return a comprehensive markdown report.

    Args:
        student_answers: Free-text answers, e.g. '1-b, 2-c, 3-a, 4-d, 5-b'.
    """
    active_exam: dict | None = state.get("active_exam") if state else None
    if not active_exam:
        return Command(update={
            "messages": [ToolMessage(
                content="Error: No active exam found. Please generate an exam first before submitting answers.",
                tool_call_id=tool_call_id,
            )]
        })

    questions: list[dict] = active_exam.get("questions", [])
    if not questions:
        return Command(update={
            "messages": [ToolMessage(content="Error: Active exam has no questions.", tool_call_id=tool_call_id)]
        })

    parsed_answers = _parse_student_answers(student_answers)
    if not parsed_answers:
        return Command(update={
            "messages": [ToolMessage(
                content="Could not parse any answers. Please use a format like: '1-b, 2-c, 3-a, 4-d, 5-b'.",
                tool_call_id=tool_call_id,
            )]
        })

    # Grade
    correct_count = 0
    total_questions = len(questions)
    mistakes = []
    weak_topics: set[str] = set()
    graded_questions = []

    for question in questions:
        q_id_str = str(question["id"])
        correct_opt = question["correct_option"].lower()
        student_opt = parsed_answers.get(q_id_str)
        if student_opt:
            student_opt = student_opt.lower()
        is_correct = student_opt == correct_opt
        graded_questions.append((question, is_correct))
        if is_correct:
            correct_count += 1
        else:
            mistakes.append({"question": question, "user_answer": student_opt or "unanswered"})
            weak_topics.add(question["topic"])

    score_percentage = (correct_count / total_questions) * 100

    # Update learner profile
    existing_profile = state.get("learner_profile") or {} if state else {}
    updated_profile = update_learner_profile(existing_profile, graded_questions)

    # Record exam history
    existing_history = state.get("exam_history") or [] if state else []
    updated_history = record_exam(existing_history, score_percentage, total_questions, weak_topics)

    # Adaptive focus for next exam
    next_focus = compute_next_exam_focus(updated_profile)

    # Course search per weak topic
    course_map: dict[str, list[dict]] = {}
    for topic in weak_topics:
        course_map[topic] = search_courses_for_topic(topic)

    # Mistake feedback
    mistakes_feedback = []
    for mistake in mistakes:
        q = mistake["question"]
        user_ans = mistake["user_answer"]
        explanation = _explain_mistake(q, user_ans)
        remediation = format_remediation_note(q["topic"])
        block = (
            f"**Question {q['id']}:** {q['question']}\n"
            f"- *Your Answer:* {user_ans.upper()}\n"
            f"- *Correct Answer:* {q['correct_option'].upper()}\n"
            f"- *Explanation:* {explanation}\n"
        )
        if remediation:
            block += remediation + "\n"
        mistakes_feedback.append(block)

    # Course recommendations (top 3)
    all_courses = []
    for topic in list(weak_topics)[:3]:
        courses = course_map.get(topic, [])
        if courses:
            all_courses.append((topic, courses[0]))
    for topic in weak_topics:
        for course in course_map.get(topic, [])[1:]:
            if len(all_courses) >= 3:
                break
            all_courses.append((topic, course))
        if len(all_courses) >= 3:
            break

    course_recs = [
        f"- **{c['title']}** ({c['source']})\n  Link: {c['url']} *(Topic: {t})*"
        for t, c in all_courses[:3]
    ]

    # Learning path
    sorted_weak = sorted(
        [(t, updated_profile[t]["accuracy"]) for t in weak_topics if t in updated_profile],
        key=lambda x: x[1],
    )
    learning_path = build_learning_path(sorted_weak, course_map)

    # Assemble report
    report = ["## 📝 Exam Grading Report\n"]
    report.append(f"**Score:** {correct_count}/{total_questions} ({score_percentage:.1f}%)\n")

    if correct_count == total_questions:
        report.append("🎉 Perfect score! Excellent understanding of the material.\n")
    else:
        report.append("### 🔍 Incorrect Answers & Explanations\n")
        report.append("\n".join(mistakes_feedback))

    analytics_block = format_analytics_section(updated_profile)
    if analytics_block:
        report.append(analytics_block)

    gaps_block = format_gaps_section(updated_profile)
    if gaps_block:
        report.append(gaps_block)

    trend_block = format_progress_section(updated_history)
    if trend_block:
        report.append(trend_block)

    path_block = format_learning_path_section(learning_path)
    if path_block:
        report.append(path_block)

    if course_recs and correct_count < total_questions:
        report.append("### 📚 Recommended Courses\n")
        report.append("Based on the topics you missed, here are recommended courses to strengthen your knowledge:\n")
        report.append("\n".join(course_recs))

    final_report = "\n\n".join(filter(None, report))

    return Command(update={
        "learner_profile": updated_profile,
        "exam_history": updated_history,
        "next_exam_focus": next_focus,
        "messages": [ToolMessage(content=final_report, tool_call_id=tool_call_id)],
    })
