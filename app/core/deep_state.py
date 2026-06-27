"""
Shared state schema for the deep (planner-executor) agent and its subagents.

Extends deepagents' ``DeepAgentState`` (which already carries ``messages``,
``todos``, and the virtual-filesystem ``files``) with the education-domain
fields the assessment tools read and write via ``InjectedState`` / ``Command``.

Because ``create_deep_agent(state_schema=...)`` forwards this schema to the
declarative subagents, the ``assessment-agent`` subagent sees the same
``active_exam`` / ``learner_profile`` fields as the orchestrator. The
``generate_exam`` tool writes ``active_exam`` into state; that value rides the
parent checkpointer between turns and is passed back into the subagent so
``grade_exam`` can read it on a later turn.
"""

from __future__ import annotations

from typing import Optional

from typing_extensions import NotRequired

from deepagents import DeepAgentState


class EduDeepState(DeepAgentState):
    # Set by generate_exam, consumed by grade_exam: {questions, answer_key, topics_covered}
    active_exam: NotRequired[Optional[dict]]

    # Adaptive-learning analytics, updated by grade_exam
    learner_profile: NotRequired[Optional[dict]]
    exam_history: NotRequired[Optional[list]]
    next_exam_focus: NotRequired[Optional[list]]
