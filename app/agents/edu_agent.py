"""
EduMentor unified agent — state machine that handles exam generation,
question-by-question answer collection, and automatic grading in one session.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from app.analytics.knowledge_gap import format_gaps_section
from app.analytics.learner_profile import compute_next_exam_focus, format_remediation_note
from app.analytics.learning_path import build_learning_path, format_learning_path_section
from app.analytics.performance import format_analytics_section, update_learner_profile
from app.analytics.progress_tracker import format_progress_section, record_exam
from app.core.edu_state import EduMentorState
from app.core.llm import get_llm
from app.tools.course_search import search_courses_for_topic
from app.tools.exam_generator import (
    _generate_mcqs,
    _get_exam_client,
    _mcq_to_state_question,
    _retrieve_chunks,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

_EXAM_KEYWORDS = [
    "exam", "quiz", "test", "question", "mcq", "multiple choice",
    "start", "begin", "generate", "create", "give me", "make me",
]


def _get_last_human(state: EduMentorState) -> str:
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage):
            return msg.content
    return ""


def _wants_exam(msg: str) -> bool:
    lower = msg.lower()
    return any(kw in lower for kw in _EXAM_KEYWORDS)


def _extract_exam_params(msg: str) -> tuple[int, Optional[str]]:
    n = 5
    topic = None

    m = re.search(r"(\d+)\s*(?:question|mcq|quiz|q)", msg, re.I)
    if m:
        n = min(max(int(m.group(1)), 1), 10)

    m = re.search(r"(?:on|about|regarding|for)\s+([A-Za-z][A-Za-z0-9\s\-]+?)(?:\s*$|[,\.!\?])", msg, re.I)
    if m:
        topic = m.group(1).strip()

    return n, topic


def _format_question(question: dict, idx: int, total: int) -> str:
    opts = "\n".join(f"  **{k})** {v}" for k, v in question["options"].items())
    return (
        f"**Question {idx + 1} of {total}**\n\n"
        f"{question['question']}\n\n"
        f"{opts}\n\n"
        f"_Reply with a single letter: a, b, c, or d_"
    )


def _grade(state: EduMentorState) -> dict:
    """Pure grading logic — no @tool wrapper needed here."""
    active_exam = state["active_exam"]
    questions: list[dict] = active_exam["questions"]
    collected: dict = state.get("collected_answers", {})

    correct_count = 0
    total = len(questions)
    mistakes = []
    weak_topics: set[str] = set()
    graded_questions = []

    for q in questions:
        q_id_str = str(q["id"])
        correct_opt = q["correct_option"].lower()
        student_opt = collected.get(q_id_str, "unanswered").lower()
        is_correct = student_opt == correct_opt
        graded_questions.append((q, is_correct))
        if is_correct:
            correct_count += 1
        else:
            mistakes.append({"question": q, "user_answer": student_opt})
            weak_topics.add(q["topic"])

    score_pct = (correct_count / total) * 100

    existing_profile = state.get("learner_profile") or {}
    updated_profile = update_learner_profile(existing_profile, graded_questions)

    existing_history = state.get("exam_history") or []
    updated_history = record_exam(existing_history, score_pct, total, weak_topics)

    next_focus = compute_next_exam_focus(updated_profile)

    course_map: dict = {}
    for topic in weak_topics:
        course_map[topic] = search_courses_for_topic(topic)

    # Mistake feedback
    from app.core.llm import get_llm as _llm
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate

    mistakes_feedback = []
    for m in mistakes:
        q = m["question"]
        user_ans = m["user_answer"]
        correct_text = q["options"].get(q["correct_option"], "")
        user_text = q["options"].get(user_ans, "Unknown")
        opts_str = "\n".join(f"  {k}) {v}" for k, v in q["options"].items())
        try:
            chain = ChatPromptTemplate.from_messages([
                ("system", "You are an AI tutor. Explain briefly (1-2 sentences) why the correct answer is right and the student's answer is wrong. Be encouraging."),
                ("user", "Question: {question}\nOptions:\n{options}\nCorrect: {correct} - {correct_text}\nStudent chose: {user} - {user_text}"),
            ]) | _llm() | StrOutputParser()
            explanation = chain.invoke({
                "question": q["question"], "options": opts_str,
                "correct": q["correct_option"], "correct_text": correct_text,
                "user": user_ans, "user_text": user_text,
            }).strip()
        except Exception:
            explanation = f"The correct answer is '{q['correct_option']}' ({correct_text})."

        block = (
            f"**Q{q['id']}:** {q['question']}\n"
            f"- Your answer: **{user_ans.upper()}** — {user_text}\n"
            f"- Correct answer: **{q['correct_option'].upper()}** — {correct_text}\n"
            f"- {explanation}\n"
        )
        remediation = format_remediation_note(q["topic"])
        if remediation:
            block += remediation
        mistakes_feedback.append(block)

    # Course recommendations
    all_courses = []
    for topic in list(weak_topics)[:3]:
        courses = course_map.get(topic, [])
        if courses:
            all_courses.append((topic, courses[0]))
    course_recs = [
        f"- **{c['title']}** ({c['source']}) — [link]({c['url']}) *(Topic: {t})*"
        for t, c in all_courses[:3]
    ]

    sorted_weak = sorted(
        [(t, updated_profile[t]["accuracy"]) for t in weak_topics if t in updated_profile],
        key=lambda x: x[1],
    )
    learning_path = build_learning_path(sorted_weak, course_map)

    # Assemble report
    report = [f"## 📝 Exam Results\n\n**Score: {correct_count}/{total} ({score_pct:.1f}%)**\n"]

    if correct_count == total:
        report.append("🎉 **Perfect score!** Excellent work.\n")
    else:
        report.append("### 🔍 Mistakes & Explanations\n")
        report.append("\n\n".join(mistakes_feedback))

    for block in [
        format_analytics_section(updated_profile),
        format_gaps_section(updated_profile),
        format_progress_section(updated_history),
        format_learning_path_section(learning_path),
    ]:
        if block:
            report.append(block)

    if course_recs and correct_count < total:
        report.append("### 📚 Recommended Courses\n" + "\n".join(course_recs))

    return {
        "learner_profile": updated_profile,
        "exam_history": updated_history,
        "next_exam_focus": next_focus,
        "active_exam": None,
        "exam_phase": "idle",
        "current_q_idx": 0,
        "collected_answers": {},
        "messages": [AIMessage(content="\n\n".join(filter(None, report)))],
    }


# ── Router ────────────────────────────────────────────────────────────────────

def _router(state: EduMentorState) -> str:
    phase = state.get("exam_phase", "idle")
    last = _get_last_human(state).strip().lower()

    if phase == "idle":
        return "generate_exam" if _wants_exam(last) else "idle_chat"

    if phase == "asking":
        if last in ("a", "b", "c", "d"):
            return "record_answer"
        return "off_topic"

    if phase == "exit_confirm":
        if last in ("exit", "yes", "y", "quit", "stop", "cancel"):
            return "do_exit"
        return "do_continue"

    return "idle_chat"


def _after_generate(state: EduMentorState) -> str:
    return "ask_question" if state.get("active_exam") else END


def _after_record(state: EduMentorState) -> str:
    idx = state.get("current_q_idx", 0)
    total = len(state.get("active_exam", {}).get("questions", []))
    return "grade" if idx >= total else "ask_question"


# ── Nodes ─────────────────────────────────────────────────────────────────────

def generate_exam_node(state: EduMentorState) -> dict:
    last_human = _get_last_human(state)
    n_questions, topic = _extract_exam_params(last_human)

    try:
        client, collection_name = _get_exam_client()
        chunks = _retrieve_chunks(topic, n_questions * 2, client, collection_name)
        if not chunks:
            return {
                "exam_phase": "idle",
                "messages": [AIMessage(content="⚠️ Could not find content in the exam corpus. Please try again.")],
            }
        questions = _generate_mcqs(chunks, n_questions, topic)
    except Exception as e:
        return {
            "exam_phase": "idle",
            "messages": [AIMessage(content=f"⚠️ Failed to generate exam: {e}")],
        }

    state_questions = [_mcq_to_state_question(q) for q in questions]
    topic_str = f" on **{topic}**" if topic else ""
    intro = (
        f"I've prepared a **{len(questions)}-question exam{topic_str}** for you.\n\n"
        "Answer each question with just the letter **a**, **b**, **c**, or **d**.\n"
        "Type **exit** at any time to cancel the exam.\n\n"
        "Let's begin! 🎓"
    )
    return {
        "active_exam": {
            "questions": state_questions,
            "answer_key": {q.id: q.correct_label for q in questions},
            "topics_covered": list({q.topic for q in questions}),
        },
        "exam_phase": "asking",
        "current_q_idx": 0,
        "collected_answers": {},
        "messages": [AIMessage(content=intro)],
    }


def ask_question_node(state: EduMentorState) -> dict:
    questions = state["active_exam"]["questions"]
    idx = state.get("current_q_idx", 0)
    total = len(questions)
    q = questions[idx]
    return {"messages": [AIMessage(content=_format_question(q, idx, total))]}


def record_answer_node(state: EduMentorState) -> dict:
    answer = _get_last_human(state).strip().lower()
    idx = state.get("current_q_idx", 0)
    q_id = str(state["active_exam"]["questions"][idx]["id"])
    collected = dict(state.get("collected_answers") or {})
    collected[q_id] = answer
    return {
        "collected_answers": collected,
        "current_q_idx": idx + 1,
    }


def grade_node(state: EduMentorState) -> dict:
    return _grade(state)


def off_topic_node(state: EduMentorState) -> dict:
    idx = state.get("current_q_idx", 0)
    total = len(state.get("active_exam", {}).get("questions", []))
    return {
        "exam_phase": "exit_confirm",
        "messages": [AIMessage(
            content=(
                f"You're currently on **Question {idx + 1} of {total}**.\n\n"
                "Would you like to **exit** the exam (your progress will be lost) "
                "or **continue** answering?\n\n"
                "Type `exit` to quit, or anything else to continue."
            )
        )],
    }


def do_exit_node(state: EduMentorState) -> dict:
    return {
        "exam_phase": "idle",
        "active_exam": None,
        "current_q_idx": 0,
        "collected_answers": {},
        "messages": [AIMessage(content="Exam cancelled. Your progress has been cleared. Feel free to start a new exam whenever you're ready! 😊")],
    }


def do_continue_node(state: EduMentorState) -> dict:
    return {"exam_phase": "asking"}


def idle_chat_node(state: EduMentorState) -> dict:
    msgs = list(state.get("messages", []))
    system = SystemMessage(content=(
        "You are EduMentor AI, an educational assistant. "
        "You help students learn by generating multiple-choice exams and grading their answers. "
        "If the user hasn't started an exam yet, briefly answer their question and encourage them to take an exam. "
        "Suggest they say something like 'Give me 5 questions on RAG' or 'Start a quiz'."
    ))
    response = get_llm().invoke([system] + msgs[-6:])
    return {"messages": [AIMessage(content=response.content)]}


# ── Graph ─────────────────────────────────────────────────────────────────────

def _build_graph():
    g = StateGraph(EduMentorState)

    g.add_node("generate_exam", generate_exam_node)
    g.add_node("ask_question", ask_question_node)
    g.add_node("record_answer", record_answer_node)
    g.add_node("grade", grade_node)
    g.add_node("off_topic", off_topic_node)
    g.add_node("do_exit", do_exit_node)
    g.add_node("do_continue", do_continue_node)
    g.add_node("idle_chat", idle_chat_node)

    g.add_conditional_edges(START, _router, {
        "generate_exam": "generate_exam",
        "idle_chat": "idle_chat",
        "record_answer": "record_answer",
        "off_topic": "off_topic",
        "do_exit": "do_exit",
        "do_continue": "do_continue",
    })

    g.add_conditional_edges("generate_exam", _after_generate, {"ask_question": "ask_question", END: END})
    g.add_edge("ask_question", END)
    g.add_conditional_edges("record_answer", _after_record, {
        "ask_question": "ask_question",
        "grade": "grade",
    })
    g.add_edge("grade", END)
    g.add_edge("off_topic", END)
    g.add_edge("do_exit", END)
    g.add_edge("do_continue", "ask_question")
    g.add_edge("idle_chat", END)

    return g.compile(checkpointer=InMemorySaver())


@lru_cache(maxsize=1)
def _get_graph():
    return _build_graph()


def ask(query: str, thread_id: str = "edu-session") -> str:
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 20}
    result = _get_graph().invoke(
        {"messages": [HumanMessage(content=query)]},
        config=config,
    )
    # Return the last AI message
    for msg in reversed(result["messages"]):
        if isinstance(msg, AIMessage):
            return msg.content
    return ""
