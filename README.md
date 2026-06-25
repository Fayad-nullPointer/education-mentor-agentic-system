# Tool 2 — Exam Generator
**Team: Arwa, Mariam**

Generates MCQs from the study corpus (Qdrant), enforces JSON schema output, and persists the answer key inside `AgentState` so Tool 3 (Grader) can retrieve it on the next turn.

---

## Quick Start

```bash
pip install -r requirements.txt

# Required env vars
export OPENAI_API_KEY="sk-..."
export QDRANT_URL="http://localhost:6333"       # default
export QDRANT_COLLECTION="edumentor_corpus"     # default

# LangSmith tracing (optional but recommended)
export LANGCHAIN_TRACING_V2="true"
export LANGCHAIN_API_KEY="ls__..."
export LANGCHAIN_PROJECT="EduMentor-AI"

# Run tests
pytest tests/ -v

# Run integration smoke-test (needs live Qdrant + OpenAI key)
python integration_example.py
```

---

## Files

| File | Purpose |
|---|---|
| `tool.py` | **Main file** — all schemas, helpers, and the LangGraph tool |
| `integration_example.py` | Shows how to wire the tool into the shared agent |
| `tests/test_exam_generator.py` | Unit tests with mocked Qdrant + LLM |
| `requirements.txt` | Dependencies |

---

## What Other Teams Import

```python
from tool import (
    generate_exam_tool,   # register with the ReAct agent (ALL teams)
    read_exam_from_state, # Tool 3 (Grader) uses this to get the answer key
    write_exam_to_state,  # internal, but exported for tests
    ExamPayload,          # type hint for the grader
)
```

### AgentState contract

Tool 2 writes one key into the shared state:

```python
state["active_exam"] = {
    "questions": [...],         # list of MCQQuestion dicts
    "answer_key": {1: "b", ...},
    "topics_covered": ["RAG", "Transformers"],
}
```

Tool 3 reads it back with `read_exam_from_state(state)`.

---

## Tool Signature (for the system prompt)

```
generate_exam_tool(state, n_questions=5, topic=None)
```

- `n_questions` — defaults to 5; the agent passes a number if the learner specifies one.
- `topic` — optional filter (e.g. `"RAG"`, `"Transformers"`); pass `None` for mixed topics.

---

## LangSmith Traces

With `LANGCHAIN_TRACING_V2=true` each exam generation produces a nested trace:

```
exam_generator_tool
  ├── retrieve_chunks_for_exam   [retriever]
  ├── generate_mcqs_from_chunks  [llm]
  └── format_exam_for_learner    [chain]
```

This makes it easy to debug which step fails and inspect the raw LLM JSON.

---

## Env Vars Reference

| Variable | Default | Notes |
|---|---|---|
| `QDRANT_URL` | `http://localhost:6333` | Set to your hosted Qdrant URL |
| `QDRANT_COLLECTION` | `edumentor_corpus` | Must match Team 1's collection name |
| `LITELLM_MODEL` | `gpt-4o-mini` | Any LiteLLM-supported model string |
| `LANGCHAIN_TRACING_V2` | — | Set to `"true"` to enable LangSmith |
| `LANGCHAIN_API_KEY` | — | Your LangSmith API key |
| `LANGCHAIN_PROJECT` | — | LangSmith project name (e.g. `EduMentor-AI`) |
