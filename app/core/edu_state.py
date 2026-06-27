from typing import Annotated, Optional, Sequence
from typing_extensions import NotRequired, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class EduMentorState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]

    exam_phase: NotRequired[str]          # "idle" | "asking" | "exit_confirm"
    active_exam: NotRequired[Optional[dict]]  # {questions, answer_key, topics_covered}
    current_q_idx: NotRequired[int]       # 0-based index of the question being asked
    collected_answers: NotRequired[dict]  # {str(q_id): letter}

    learner_profile: NotRequired[Optional[dict]]
    exam_history: NotRequired[Optional[list]]
    next_exam_focus: NotRequired[Optional[list]]
