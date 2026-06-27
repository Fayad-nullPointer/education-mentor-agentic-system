"""
EduMentor deep agent — a planner/executor orchestrator built on ``deepagents``.

The orchestrator (planner) owns no domain tools itself. It plans with the
built-in ``write_todos`` tool and delegates to two specialist subagents via the
``task`` tool:

- ``research-agent``   → RAG-grounded answering   (tools: rag_search)
- ``assessment-agent`` → exams, grading, courses  (tools: generate_exam,
                                                    grade_exam, search_courses)

A shared ``EduDeepState`` (forwarded to the subagents) carries the active exam
and learner analytics, so the assessment subagent can generate an exam on one
turn and grade it on a later turn — the active exam persists in the parent's
checkpointer between turns.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from deepagents import (
    GeneralPurposeSubagentProfile,
    HarnessProfile,
    SubAgent,
    create_deep_agent,
    register_harness_profile,
)
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.core.deep_state import EduDeepState
from app.core.llm import get_agent_llm
from app.tools.course_search import search_courses
from app.tools.exam_generator import generate_exam
from app.tools.exam_grader import grade_exam
from app.tools.rag_search import rag_search

_PROMPTS = Path(__file__).parent.parent / "prompts"

# deepagents ships a Claude-oriented harness: a large base system prompt plus a
# filesystem/shell toolset (ls, read_file, write_file, edit_file, glob, grep,
# execute). None of that is relevant to an education mentor, and the bloated
# tool surface makes Gemini 2.5 Flash return an empty response on its first
# turn. Register a profile (keyed to our model) that strips those tools down to
# just the planner-executor essentials — `write_todos` (planning) and `task`
# (delegation) — and drops the empty auto general-purpose subagent.
_GEMINI_PROFILE_KEY = "google_genai:gemini-2.5-flash"
_EXCLUDED_TOOLS = frozenset(
    {"ls", "read_file", "write_file", "edit_file", "glob", "grep", "execute"}
)

register_harness_profile(
    _GEMINI_PROFILE_KEY,
    HarnessProfile(
        excluded_tools=_EXCLUDED_TOOLS,
        general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
    ),
)


def _prompt(name: str) -> str:
    return (_PROMPTS / name).read_text(encoding="utf-8")


def _build_subagents() -> list[SubAgent]:
    research_agent: SubAgent = {
        "name": "research-agent",
        "description": (
            "Answers conceptual questions, explanations, summaries, and code "
            "requests about Mathematics, AI Engineering, and Computer Science, "
            "grounded in a knowledge base of technical books. Use for anything "
            "the student wants to learn or understand."
        ),
        "system_prompt": _prompt("research_agent.md"),
        "tools": [rag_search],
    }

    assessment_agent: SubAgent = {
        "name": "assessment-agent",
        "description": (
            "Generates multiple-choice exams, grades submitted answers against "
            "the active exam, and recommends courses. Use when the student wants "
            "a quiz/exam, submits answers to grade, or asks for course "
            "recommendations. Pass the student's answer string verbatim when "
            "delegating grading."
        ),
        "system_prompt": _prompt("assessment_agent.md"),
        "tools": [generate_exam, grade_exam, search_courses],
    }

    return [research_agent, assessment_agent]


@lru_cache(maxsize=1)
def _get_agent():
    return create_deep_agent(
        model=get_agent_llm(),
        tools=[],  # the orchestrator delegates; it holds no domain tools itself
        system_prompt=_prompt("deep_agent.md"),
        subagents=_build_subagents(),
        state_schema=EduDeepState,
        checkpointer=InMemorySaver(),
    )


def ask(query: str, thread_id: str = "deep-session") -> str:
    config = {"configurable": {"thread_id": thread_id}}
    result = _get_agent().invoke(
        {"messages": [HumanMessage(content=query)]},
        config=config,
    )
    for msg in reversed(result["messages"]):
        if isinstance(msg, AIMessage) and msg.text:
            return msg.text
    return ""
