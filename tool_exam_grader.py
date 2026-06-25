"""
Tool 3 — Exam Grader
Team: Arwa, Mariam
-------------------------------------------------
Grades learner's answers against the stored answer key in AgentState.
Clears the active exam from state after grading.

LangSmith tracing is enabled automatically via env vars:
    LANGCHAIN_TRACING_V2=true
    LANGCHAIN_API_KEY=<your key>
    LANGCHAIN_PROJECT=EduMentor-AI
"""

from __future__ import annotations

import re
from typing import Any

from langchain_core.tools import tool
from langsmith import traceable

from exam_state import read_exam_from_state


@tool
@traceable(name="grade_answers_tool", run_type="tool")
def grade_answers_tool(
    answers: str,
    state: dict[str, Any],
) -> dict[str, Any]:
    """
    Use when the learner replies with answers in the format '1-b, 2-c, 3-a, ...'.
    Compares the student's answers with the active exam's answer key and returns a detailed report.

    Args:
        answers: The raw string containing student answers.
        state:   The current LangGraph AgentState.
    """
    exam_payload = read_exam_from_state(state)

    if not exam_payload:
        return {
            "message": "⚠️ No active exam found. Please request a new exam first using 'generate_exam_tool'.",
            "state": state,
        }

    answer_key = exam_payload.answer_key

    parsed_student_answers = {
        int(q_id): ans
        for q_id, ans in re.findall(r"(\d+)\s*[-:]\s*([a-d])", answers.lower())
    }

    if not parsed_student_answers:
        return {
            "message": "⚠️ I couldn't parse your answers. Please reply using the format: `1-a, 2-c, 3-b`.",
            "state": state,
        }

    correct_count = 0
    total_questions = len(answer_key)
    detailed_feedback = []

    for q_id, correct_label in answer_key.items():
        student_ans = parsed_student_answers.get(q_id)

        if student_ans == correct_label.lower():
            correct_count += 1
            detailed_feedback.append(f"✅ **Q{q_id}: Correct!** (Your answer: {student_ans.upper()})")
        elif student_ans is None:
            detailed_feedback.append(f"❌ **Q{q_id}: No answer provided.** (Correct: {correct_label.upper()})")
        else:
            detailed_feedback.append(
                f"❌ **Q{q_id}: Incorrect.** Your answer: {student_ans.upper()} | Correct: {correct_label.upper()}"
            )

    score_percentage = (correct_count / total_questions) * 100 if total_questions > 0 else 0

    report_lines = [
        "📊 **Exam Results Report**",
        "═" * 40,
        f"🎯 **Final Score:** {correct_count}/{total_questions} ({score_percentage:.1f}%)",
        "─" * 40,
    ]
    report_lines.extend(detailed_feedback)
    report_lines.append("═" * 40)

    if score_percentage == 100:
        report_lines.append("🎉 **Perfect score! Outstanding job!** 🌟")
    elif score_percentage >= 70:
        report_lines.append("👍 **Good job! You passed the exam.**")
    else:
        report_lines.append("📚 **Keep reviewing the material and try again!**")

    state["active_exam"] = None

    return {
        "message": "\n".join(report_lines),
        "state": state,
    }
