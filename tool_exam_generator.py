"""
Tool 2 — Exam Generator
Team: Arwa, Mariam
-------------------------------------------------
Generates MCQs from corpus chunks retrieved via Qdrant.
Writes questions + answer key into AgentState.
Only the question text (no correct-answer flags) is returned to the learner.

LangSmith tracing is enabled automatically via env vars:
    LANGCHAIN_TRACING_V2=true
    LANGCHAIN_API_KEY=<your key>
    LANGCHAIN_PROJECT=EduMentor-AI
"""

from __future__ import annotations

import json
import random
from typing import Any

from langchain_core.tools import tool
from langsmith import traceable
from litellm import completion
from qdrant_client import QdrantClient
from qdrant_client.http.models import FieldCondition, Filter, MatchValue

from config import (
    DEFAULT_N_QUESTIONS,
    MODEL_NAME,
    QDRANT_API_KEY,
    QDRANT_COLLECTION,
    QDRANT_URL,
)
from exam_state import write_exam_to_state
from schemas import ExamPayload, LearnerView, MCQQuestion


@traceable(name="retrieve_chunks_for_exam", run_type="retriever")
def _retrieve_chunks(
    topic: str | None,
    n_chunks: int,
    qdrant_client: QdrantClient,
) -> list[str]:
    scroll_filter = None
    if topic:
        scroll_filter = Filter(
            must=[FieldCondition(key="topic", match=MatchValue(value=topic))]
        )

    results, _ = qdrant_client.scroll(
        collection_name=QDRANT_COLLECTION,
        scroll_filter=scroll_filter,
        limit=max(n_chunks * 4, 40),
        with_payload=True,
        with_vectors=False,
    )

    if len(results) < n_chunks:
        results, _ = qdrant_client.scroll(
            collection_name=QDRANT_COLLECTION,
            limit=max(n_chunks * 4, 40),
            with_payload=True,
            with_vectors=False,
        )

    chosen = random.sample(results, min(n_chunks, len(results)))
    return [r.payload.get("text", "") for r in chosen if r.payload]


@traceable(name="generate_mcqs_from_chunks", run_type="llm")
def _generate_mcqs(
    chunks: list[str],
    n_questions: int,
    topic_hint: str | None,
) -> list[MCQQuestion]:
    context = "\n\n---\n\n".join(chunks)
    topic_line = (
        f"Focus on the topic: {topic_hint}."
        if topic_hint
        else "Cover a variety of topics from the text."
    )

    system_prompt = (
        "You are an educational assessment writer. "
        "Generate multiple-choice questions strictly from the provided text. "
        "Do NOT invent facts outside the source material. "
        "Return ONLY a valid JSON array — no markdown, no explanation."
    )

    user_prompt = f"""
{topic_line}
Generate exactly {n_questions} multiple-choice questions from the text below.

FORMAT (JSON array, each element):
{{
  "id": <int, 1-based>,
  "question": "<question string>",
  "options": [
    {{"label": "a", "text": "<option>"}},
    {{"label": "b", "text": "<option>"}},
    {{"label": "c", "text": "<option>"}},
    {{"label": "d", "text": "<option>"}}
  ],
  "correct_label": "<a|b|c|d>",
  "topic": "<short topic tag, e.g. 'RAG', 'Transformers', 'Fine-tuning'>"
}}

SOURCE TEXT:
{context}
"""

    response = completion(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )

    raw: str = response.choices[0].message.content.strip()

    parsed = json.loads(raw)
    if isinstance(parsed, dict):
        for key in ("questions", "mcqs", "items", "data"):
            if key in parsed and isinstance(parsed[key], list):
                parsed = parsed[key]
                break

    if not isinstance(parsed, list):
        raise ValueError(f"Expected a JSON array of questions, got: {type(parsed)}")

    return [MCQQuestion(**q) for q in parsed]


@traceable(name="format_exam_for_learner", run_type="chain")
def _format_learner_view(questions: list[MCQQuestion]) -> LearnerView:
    lines = []
    for q in questions:
        lines.append(f"**Q{q.id}.** {q.question}")
        for opt in q.options:
            lines.append(f"  {opt.label}) {opt.text}")
        lines.append("")

    questions_text = "\n".join(lines).strip()
    intro = (
        f"Here is your {len(questions)}-question exam. "
        "When you're ready, reply with your answers in the format: "
        "`1-a, 2-c, 3-b, …`"
    )
    return LearnerView(intro=intro, questions_text=questions_text)


@tool
@traceable(name="exam_generator_tool", run_type="tool")
def generate_exam_tool(
    state: dict[str, Any],
    n_questions: int = DEFAULT_N_QUESTIONS,
    topic: str | None = None,
) -> dict[str, Any]:
    """
    Generate a multiple-choice exam from the study corpus.

    Args:
        state:       The current LangGraph AgentState (mutated in-place).
        n_questions: Number of MCQs to generate (default 5).
        topic:       Optional topic filter (e.g. "RAG", "Transformers").
                     If None, questions span mixed topics.

    Returns:
        A dict with "message", "state", and "topics".
    """
    qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

    chunks = _retrieve_chunks(
        topic=topic,
        n_chunks=n_questions * 2,
        qdrant_client=qdrant,
    )

    if not chunks:
        return {
            "message": "⚠️ Could not retrieve content from the corpus. Please check the Qdrant connection.",
            "state": state,
            "topics": [],
        }

    questions = _generate_mcqs(
        chunks=chunks,
        n_questions=n_questions,
        topic_hint=topic,
    )

    answer_key = {q.id: q.correct_label for q in questions}
    topics_found = list({q.topic for q in questions})
    exam_payload = ExamPayload(
        questions=questions,
        answer_key=answer_key,
        topics_covered=topics_found,
    )

    state = write_exam_to_state(state, exam_payload)

    learner_view = _format_learner_view(questions)
    full_message = f"{learner_view.intro}\n\n{learner_view.questions_text}"

    return {
        "message": full_message,
        "state": state,
        "topics": topics_found,
    }
