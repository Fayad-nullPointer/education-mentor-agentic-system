"""
Exam generator tool — generates MCQs from Qdrant corpus chunks.
Writes questions + answer key into AgentState.active_exam.
Replaces litellm with langchain-google-genai (Gemini).
"""

from __future__ import annotations

import json
import random
import re
from typing import Annotated, Any

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from qdrant_client import QdrantClient
from qdrant_client.http.models import FieldCondition, Filter, MatchValue

from app.core.config import get_settings
from app.core.llm import get_llm
from app.core.schemas import ExamPayload, LearnerView, MCQQuestion


def _get_exam_client() -> tuple[QdrantClient, str]:
    """Return (QdrantClient, collection_name) for the exam collection, falling back to RAG collection."""
    settings = get_settings()
    url = settings.exam_qdrant_url or settings.qdrant_url
    api_key = settings.exam_qdrant_api_key or settings.qdrant_api_key
    collection = settings.exam_collection_name or settings.collection_name
    return QdrantClient(url=url, api_key=api_key, check_compatibility=False, timeout=10), collection


def _retrieve_chunks(topic: str | None, n_chunks: int, client: QdrantClient, collection_name: str) -> list[str]:
    scroll_filter = None
    if topic:
        scroll_filter = Filter(must=[FieldCondition(key="topic", match=MatchValue(value=topic))])

    results, _ = client.scroll(
        collection_name=collection_name,
        scroll_filter=scroll_filter,
        limit=max(n_chunks * 4, 40),
        with_payload=True,
        with_vectors=False,
    )

    if len(results) < n_chunks:
        results, _ = client.scroll(
            collection_name=collection_name,
            limit=max(n_chunks * 4, 40),
            with_payload=True,
            with_vectors=False,
        )

    chosen = random.sample(results, min(n_chunks, len(results)))

    chunks = []
    for r in chosen:
        if not r.payload:
            continue
        raw = r.payload.get("_node_content") or r.payload.get("text", "")
        if raw and raw.startswith("{"):
            try:
                node = json.loads(raw)
                raw = node.get("text", raw)
            except Exception:
                pass
        if raw:
            chunks.append(raw)
    return chunks


def _generate_mcqs(chunks: list[str], n_questions: int, topic_hint: str | None) -> list[MCQQuestion]:
    context = "\n\n---\n\n".join(chunks)
    topic_line = f"Focus on the topic: {topic_hint}." if topic_hint else "Cover a variety of topics from the text."

    system_prompt = (
        "You are an educational assessment writer. "
        "Generate multiple-choice questions strictly from the provided text. "
        "Do NOT invent facts outside the source material. "
        "Return ONLY a valid JSON array — no markdown, no explanation, no code fences."
    )
    user_prompt = f"""{topic_line}
Generate exactly {n_questions} multiple-choice questions from the text below.

FORMAT (JSON array, each element):
[
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
]

SOURCE TEXT:
{context}
"""

    llm = get_llm()
    response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)])
    raw: str = response.content.strip()

    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    parsed = json.loads(raw)
    if isinstance(parsed, dict):
        for key in ("questions", "mcqs", "items", "data"):
            if key in parsed and isinstance(parsed[key], list):
                parsed = parsed[key]
                break

    if not isinstance(parsed, list):
        raise ValueError(f"Expected JSON array of questions, got: {type(parsed)}")

    return [MCQQuestion(**q) for q in parsed]


def _format_learner_view(questions: list[MCQQuestion]) -> LearnerView:
    lines = []
    for q in questions:
        lines.append(f"**Q{q.id}.** {q.question}")
        for opt in q.options[:4]:
            lines.append(f"  {opt.label}) {opt.text}")
        lines.append("")
    return LearnerView(
        intro=(
            f"Here is your {len(questions)}-question exam. "
            "When you're ready, reply with your answers in the format: `1-a, 2-c, 3-b, …`"
        ),
        questions_text="\n".join(lines).strip(),
    )


def _mcq_to_state_question(q: MCQQuestion) -> dict:
    return {
        "id": q.id,
        "question": q.question,
        "options": {opt.label: opt.text for opt in q.options[:4]},
        "topic": q.topic,
        "correct_option": q.correct_label,
    }


@tool
def generate_exam(
    n_questions: int = 5,
    topic: str | None = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = "",
    state: Annotated[dict, InjectedState] = None,
) -> Command:
    """
    Generate a multiple-choice exam from the study corpus and present it to the student.

    Args:
        n_questions: Number of MCQs to generate (default 5, max 10).
        topic:       Optional topic filter (e.g. 'RAG', 'Transformers').
                     If None, questions span mixed topics.
    """
    n_questions = min(max(n_questions, 1), 10)
    print(f"[generate_exam] called: n_questions={n_questions}, topic={topic}, tool_call_id={tool_call_id!r}")

    try:
        client, collection_name = _get_exam_client()
        print(f"[generate_exam] connecting to collection: {collection_name}")
        chunks = _retrieve_chunks(topic=topic, n_chunks=n_questions * 2, client=client, collection_name=collection_name)
        print(f"[generate_exam] retrieved {len(chunks)} chunks")
    except Exception as e:
        print(f"[generate_exam] QDRANT ERROR: {e}")
        return Command(update={
            "messages": [ToolMessage(
                content=f"⚠️ Could not connect to exam corpus: {e}",
                tool_call_id=tool_call_id,
            )]
        })

    if not chunks:
        print("[generate_exam] no chunks found")
        return Command(update={
            "messages": [ToolMessage(
                content="⚠️ No content found in the corpus. Please check the Qdrant collection.",
                tool_call_id=tool_call_id,
            )]
        })

    try:
        print("[generate_exam] calling LLM to generate MCQs...")
        questions = _generate_mcqs(chunks=chunks, n_questions=n_questions, topic_hint=topic)
        print(f"[generate_exam] generated {len(questions)} questions")
    except Exception as e:
        print(f"[generate_exam] LLM ERROR: {e}")
        return Command(update={
            "messages": [ToolMessage(
                content=f"⚠️ Failed to generate questions: {e}",
                tool_call_id=tool_call_id,
            )]
        })

    state_questions = [_mcq_to_state_question(q) for q in questions]
    active_exam = {
        "questions": state_questions,
        "answer_key": {q.id: q.correct_label for q in questions},
        "topics_covered": list({q.topic for q in questions}),
    }

    learner_view = _format_learner_view(questions)
    full_message = f"{learner_view.intro}\n\n{learner_view.questions_text}"

    return Command(update={
        "active_exam": active_exam,
        "messages": [ToolMessage(content=full_message, tool_call_id=tool_call_id)],
    })
