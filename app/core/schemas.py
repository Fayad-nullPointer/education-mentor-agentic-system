from pydantic import BaseModel, Field


class MCQOption(BaseModel):
    label: str
    text: str


class MCQQuestion(BaseModel):
    id: int
    question: str
    options: list[MCQOption] = Field(min_length=2)
    correct_label: str
    topic: str


class ExamPayload(BaseModel):
    questions: list[MCQQuestion]
    answer_key: dict[int, str]
    topics_covered: list[str]


class LearnerView(BaseModel):
    intro: str
    questions_text: str
