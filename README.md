# EduMentor AI

A chat-based study assistant for **Mathematics, AI Engineering, and Computer
Science**, grounded in a corpus of technical books. One chat handles everything:
ask a concept, get a grounded explanation, take a multiple-choice exam, and get
graded with feedback and course recommendations.

## Architecture

A **deep agent (planner-executor)** built on [`deepagents`](https://github.com/langchain-ai/deepagents).
An orchestrator plans the request and delegates to two specialist subagents:

| Subagent | Tools | Handles |
|---|---|---|
| `research-agent` | `rag_search` | Explanations, summaries, Q&A, code — grounded with sources |
| `assessment-agent` | `generate_exam`, `grade_exam`, `search_courses` | Exam generation, grading, course recommendations |

The active exam and learner analytics live in shared state, so an exam generated
on one turn can be graded on a later turn.

**LLM:** Gemini 2.5 Flash (via `langchain-google-genai`). **Vector DB:** Qdrant.
**Course search:** Tavily (optional; falls back to a built-in list).

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12.

```bash
uv sync
cp .env.example .env   # then fill in your keys
```

Set in `.env`:

- `GOOGLE_API_KEY` — Gemini. Required.
- `QDRANT_URL`, `QDRANT_API_KEY`, `COLLECTION_NAME` — your Qdrant corpus.
- `EMBEDDING_MODEL` — e.g. `sentence-transformers/all-MiniLM-L6-v2`.
- `TAVILY_API_KEY` — optional, for live course search.

## Run

```bash
uv run python main.py
```

Open **http://127.0.0.1:7860**.

**Try:**
- `Explain retrieval-augmented generation`
- `Give me 5 questions on Transformers`
- then answer with `1-a, 2-c, 3-b, 4-d, 5-a`

## Note on the Gemini free tier

This agent makes several LLM calls per turn, and the Gemini free tier allows only
~20 requests/day (a few turns). For sustained use, use a paid Gemini key.
