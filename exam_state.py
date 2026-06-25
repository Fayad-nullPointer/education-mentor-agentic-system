from __future__ import annotations

from typing import Any

from schemas import ExamPayload


def write_exam_to_state(state: dict[str, Any], exam: ExamPayload) -> dict[str, Any]:
    state["active_exam"] = exam.model_dump()
    return state


def read_exam_from_state(state: dict[str, Any]) -> ExamPayload | None:
    raw = state.get("active_exam")
    if not raw:
        return None
    return ExamPayload(**raw)
