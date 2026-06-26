from typing import Annotated, Optional, Sequence
from typing_extensions import NotRequired, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from langgraph.prebuilt.chat_agent_executor import RemainingSteps


class TopicPerformance(TypedDict):
    attempts: int
    correct: int
    accuracy: float


class ExamRecord(TypedDict):
    timestamp: str
    score: float
    total_questions: int
    weak_topics: list[str]


class Question(TypedDict):
    id: int
    question: str
    options: dict[str, str]
    topic: str
    correct_option: str


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    remaining_steps: NotRequired[RemainingSteps]
    active_exam: NotRequired[Optional[dict]]
    learner_profile: NotRequired[Optional[dict[str, TopicPerformance]]]
    exam_history: NotRequired[Optional[list[ExamRecord]]]
    next_exam_focus: NotRequired[Optional[list[str]]]
