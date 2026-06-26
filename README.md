# EduMentor AI — Adaptive Learning Intelligence Engine
### Team 3 · Feature Branch: `feature/adaptive-learning-intelligence-engine`

> **Branch purpose:** Extends the original grading subsystem into a full *Adaptive Educational Intelligence Layer* that tracks learner progress over time, identifies knowledge gaps, personalises future exams, and integrates with the RAG subsystem (Team 1).
>
> The original `run_demo.py` and every public function signature remain **100% backward-compatible**. No other team needs to change their code to pick up this branch.

---

## Table of Contents

1. [What Changed & Why](#1-what-changed--why)
2. [Repository File Map](#2-repository-file-map)
3. [File-by-File Reference](#3-file-by-file-reference)
   - [state.py](#statepy)
   - [grader_tool.py](#grader_toolpy)
   - [analytics.py](#analyticspy)
   - [progress_tracker.py](#progress_trackerpy)
   - [knowledge_gap.py](#knowledge_gappy)
   - [learning_path.py](#learning_pathpy)
   - [learner_profile.py](#learner_profilepy)
   - [config.py](#configpy) *(unchanged)*
   - [grader_agent.py](#grader_agentpy) *(unchanged)*
   - [run_demo.py](#run_demopy) *(unchanged)*
4. [New AgentState Schema](#4-new-agentstate-schema)
5. [New Report Sections](#5-new-report-sections)
6. [Integration Points — What Each Team Must Do](#6-integration-points--what-each-team-must-do)
   - [Team 1 — RAG (RAG Remediation)](#team-1--rag-remediation-integration)
   - [Team 2 — Exam Generator (Adaptive Focus)](#team-2--exam-generator-adaptive-focus)
7. [Feature Reference](#7-feature-reference)
8. [Running the Demo](#8-running-the-demo)
9. [Design Principles & Non-Functional Notes](#9-design-principles--non-functional-notes)

---

## 1. What Changed & Why

The original subsystem was a **stateless grader**: it received answers, scored them, and returned a report. Every exam was treated in isolation.

This branch adds a **persistent intelligence layer** on top:

| Before | After |
|--------|-------|
| Score + mistakes + 3 course links | All of the above, plus… |
| No memory between exams | Cumulative topic accuracy tracked in `learner_profile` |
| No history | Every exam logged in `exam_history` (capped at 50) |
| Static course list | Ordered learning path, weakest topic first |
| No personalisation signal for Team 2 | `next_exam_focus` tells Team 2 which topics to target |
| No RAG tie-in for wrong answers | Hook for Team 1 to inject remediation passages |
| No big-picture diagnostics | Knowledge gap clusters, mastery levels, readiness score |

All new behaviour is **additive**. If `learner_profile` or `exam_history` are absent in state (e.g. an older state snapshot), every new function degrades gracefully and the original report sections still appear.

---

## 2. Repository File Map

```
team3/
├── state.py              ← MODIFIED  — extended AgentState schema
├── grader_tool.py        ← MODIFIED  — wires all new modules together
│
├── analytics.py          ← NEW — topic tracking, mastery, readiness score
├── progress_tracker.py   ← NEW — exam history & progress trend
├── knowledge_gap.py      ← NEW — foundational gap cluster detection
├── learning_path.py      ← NEW — ordered learning path builder
├── learner_profile.py    ← NEW — adaptive focus + RAG remediation hook
│
├── config.py             ← unchanged
├── grader_agent.py       ← unchanged
└── run_demo.py           ← unchanged (backward-compat smoke test)
```

---

## 3. File-by-File Reference

---

### `state.py`

**Role:** Defines every TypedDict that flows through the LangGraph graph.

**What was added:**

```python
class TopicPerformance(TypedDict):
    attempts: int       # questions seen for this topic (all-time)
    correct:  int       # correct answers (all-time)
    accuracy: float     # (correct / attempts) * 100

class ExamRecord(TypedDict):
    timestamp:       str        # ISO-8601 UTC datetime
    score:           float      # percentage 0–100
    total_questions: int
    weak_topics:     List[str]  # topics with at least one mistake

class AgentState(TypedDict):
    messages:        Annotated[List[BaseMessage], add_messages]
    active_exam:     Optional[List[Question]]       # unchanged
    learner_profile: Optional[Dict[str, TopicPerformance]]  # NEW
    exam_history:    Optional[List[ExamRecord]]             # NEW
    next_exam_focus: Optional[List[str]]                    # NEW
```

**Backward-compatibility guarantee:** All three new fields are `Optional`. Code that builds `AgentState` without them will not crash; the grader checks for `None` before reading any new field.

**Who reads / writes each field:**

| Field | Written by | Read by |
|---|---|---|
| `active_exam` | Team 2 (Exam Generator) | `grader_tool.py` |
| `learner_profile` | `grader_tool.py` | `grader_tool.py`, Team 2 (optional) |
| `exam_history` | `grader_tool.py` | `grader_tool.py` |
| `next_exam_focus` | `grader_tool.py` | **Team 2 (must read)** |

---

### `grader_tool.py`

**Role:** The single `@tool`-decorated entry point that the LangGraph ReAct agent calls. Contains all grading logic and assembles the final markdown report.

**Public API (unchanged):**
```python
@tool
def grade_exam(student_answers: str, state: Annotated[dict, InjectedState]) -> str:
```

**What it does now (execution order):**

```
1.  Read active_exam from state                      (unchanged)
2.  Parse student answers via regex                  (unchanged)
3.  Grade each question                              (unchanged)
4.  update_learner_profile()   → state["learner_profile"]   ← analytics.py
5.  record_exam()              → state["exam_history"]       ← progress_tracker.py
6.  compute_next_exam_focus()  → state["next_exam_focus"]    ← learner_profile.py
7.  search_courses_tavily()    (per-topic, cached)           ← internal (unchanged)
8.  generate_mistake_explanation() per mistake               (unchanged)
9.  format_remediation_note()  per mistake                   ← learner_profile.py
10. build_learning_path()                                    ← learning_path.py
11. format_analytics_section()                               ← analytics.py
12. format_gaps_section()                                    ← knowledge_gap.py
13. format_progress_section()                                ← progress_tracker.py
14. format_learning_path_section()                           ← learning_path.py
15. Assemble & return full markdown report
```

**Tavily caching:** Results are stored in a module-level `_course_cache` dict (keyed by topic string). Repeated calls within the same process for the same topic hit the cache instead of the API, satisfying the "no duplicate Tavily requests" requirement.

---

### `analytics.py`

**Role:** Pure functions for topic-level performance tracking, mastery classification, and overall readiness scoring. No I/O, no side effects — takes data in, returns data or formatted strings.

**Key functions:**

| Function | Purpose |
|---|---|
| `update_learner_profile(profile, graded_questions)` | Merge this exam's results into the cumulative profile dict. Returns updated dict. |
| `get_mastery_level(accuracy: float) → str` | Maps a score to `Beginner / Intermediate / Advanced / Mastered`. |
| `sorted_topics_by_accuracy(profile)` | Returns profile items weakest → strongest. |
| `compute_readiness_score(profile) → float` | Mean accuracy across all tracked topics. |
| `get_readiness_label(score: float) → str` | Maps to `Not Ready / Developing / Ready / Highly Prepared`. |
| `format_analytics_section(profile) → str` | Renders the full `### 📊 Topic Analytics` markdown block. |

**Mastery thresholds:**

| Score | Label |
|---|---|
| 0 – 39 % | Beginner |
| 40 – 69 % | Intermediate |
| 70 – 89 % | Advanced |
| 90 – 100 % | Mastered |

**Readiness thresholds:**

| Score | Label |
|---|---|
| 0 – 39 % | Not Ready |
| 40 – 69 % | Developing |
| 70 – 89 % | Ready |
| 90 + % | Highly Prepared |

**How to extend:** To add a new analytics metric (e.g. "streak"), add a pure function here and call `format_analytics_section` to include it in the rendered block.

---

### `progress_tracker.py`

**Role:** Manages the exam history list and generates trend analysis text.

**Key functions:**

| Function | Purpose |
|---|---|
| `record_exam(history, score_pct, total_questions, weak_topics)` | Appends a new `ExamRecord` (UTC timestamp auto-set). Trims to `MAX_HISTORY = 50`. Returns new list. |
| `compute_trend(history) → dict` | Returns `{has_trend, first_score, latest_score, improvement}`. Returns `{has_trend: False}` if fewer than 2 exams. |
| `format_progress_section(history) → str` | Renders `### 📈 Progress Trend` block. Empty string if no history. |

**Trend formula:**
```python
improvement = latest_score - first_score   # positive = improving
```

---

### `knowledge_gap.py`

**Role:** Rule-based detection of foundational knowledge gaps by clustering weak topics.

**How it works:**

Every topic in the learner profile that has `accuracy < GAP_THRESHOLD (50%)` is considered "at risk." Topics are matched against keyword clusters using **substring matching** (case-insensitive). If at least `MIN_WEAK_IN_CLUSTER = 2` topics from the same cluster are at-risk, the cluster is flagged as a gap.

**Built-in clusters (extend as needed):**

```python
FOUNDATIONAL_GAPS = {
    "RAG Foundations":       ["embedding", "vector search", "vector db", "retrieval", "rag", "chunk", "semantic search"],
    "LangGraph Fundamentals":["agentstate", "agent state", "node", "edge", "workflow", "langgraph", "graph"],
    "LLM & Prompting":       ["prompt", "llm", "language model", "chain", "output parser", "token"],
    "Agentic Systems":       ["agent", "react", "tool", "tool call", "planner", "supervisor", "multi-agent"],
}
```

**How to add a new cluster:** Add a key + keyword list to `FOUNDATIONAL_GAPS`. No other changes needed.

**Key functions:**

| Function | Purpose |
|---|---|
| `detect_knowledge_gaps(profile) → List[str]` | Returns sorted list of detected cluster names. |
| `format_gaps_section(profile) → str` | Renders `### 🧩 Knowledge Gaps Detected` block. Empty string if no gaps. |

---

### `learning_path.py`

**Role:** Builds an ordered, step-by-step learning roadmap from the weakest topics, reusing course data already fetched by `grader_tool.py` (no extra API calls).

**Key functions:**

| Function | Purpose |
|---|---|
| `build_learning_path(weak_topics_sorted, course_map)` | Returns a list of step dicts `{step, topic, accuracy, course_title, course_url, course_source}`. Capped at `MAX_STEPS = 4`. Deduplicates course URLs across steps. |
| `format_learning_path_section(path) → str` | Renders `### 🗺️ Recommended Learning Path` block. |

**Input contract:**
- `weak_topics_sorted`: list of `(topic_str, accuracy_float)` tuples, **already sorted weakest first** — the caller (`grader_tool.py`) is responsible for sorting.
- `course_map`: `Dict[str, List[course_dict]]` — same dict built from `search_courses_tavily()` calls. Keys are topic strings.

---

### `learner_profile.py`

**Role:** Two responsibilities kept in one module because they both concern the "learner as a person":

1. **Adaptive Exam Focus (Feature 5):** Derives `next_exam_focus` so Team 2 can bias the next exam toward weak areas.
2. **RAG Remediation Integration (Feature 9):** Provides the `get_remediation_material()` hook for Team 1 to implement.

#### Adaptive Exam Focus

```python
def compute_next_exam_focus(profile: Dict[str, TopicPerformance]) -> List[str]:
```

- Filters topics with `accuracy < FOCUS_THRESHOLD (70%)` and at least 1 attempt.
- Returns up to `MAX_FOCUS_TOPICS = 3` topic strings, weakest first.
- Written into `state["next_exam_focus"]` by `grader_tool.py` after every exam.

#### RAG Remediation Hook — **Team 1 integration point**

```python
def get_remediation_material(topic: str) -> Optional[Dict]:
    """
    Returns:
        {
            "title":   str,   # e.g. "Vector Embeddings — Chapter 3"
            "source":  str,   # e.g. "Foundations of LLMs, p. 47"
            "excerpt": str,   # short passage, ≤ 2 sentences
        }
    or None if unavailable.
    """
    return None  # ← REPLACE THIS with a Qdrant retrieval call
```

Currently returns `None` (graceful fallback). When Team 1 replaces the body with a real Qdrant lookup, every wrong-answer block in the report will automatically gain a *"Recommended Reading"* citation with no other code changes required.

```python
def format_remediation_note(topic: str) -> str:
```

Called once per mistake in `grader_tool.py`. Returns an empty string if `get_remediation_material` returns `None`.

---

### `config.py`

*(Unchanged)* Loads `.env`, exposes `TAVILY_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, `LLM_MODEL`, and the `get_model()` factory.

---

### `grader_agent.py`

*(Unchanged)* Wraps `grade_exam` in a `deepagents` LangChain agent. Called during the Day 3 integration phase by the main graph coordinator.

---

### `run_demo.py`

*(Unchanged — must stay this way)* Standalone smoke test that simulates a 5-question exam without running the full graph. Calls `grade_exam.func(...)` directly to bypass schema validation. Confirms that mock fallbacks work when no API keys are configured.

Run at any time to verify nothing is broken:
```bash
python run_demo.py
```

---

## 4. New AgentState Schema

```python
# state.py — full schema after this branch

class AgentState(TypedDict):
    # ── Original fields (Team 2 writes, Team 3 reads) ─────────────────
    messages:        Annotated[List[BaseMessage], add_messages]
    active_exam:     Optional[List[Question]]

    # ── New fields (Team 3 writes, others may read) ───────────────────
    learner_profile: Optional[Dict[str, TopicPerformance]]
    #   Cumulative per-topic accuracy, updated after every graded exam.
    #   Team 2 MAY read this to weight topic selection in MCQ generation.

    exam_history:    Optional[List[ExamRecord]]
    #   Ordered log of completed exams (max 50). Private to Team 3 — no
    #   other team currently reads this.

    next_exam_focus: Optional[List[str]]
    #   Up to 3 topic strings, weakest first. Team 2 MUST read this
    #   when generating the next exam (see integration section below).
```

---

## 5. New Report Sections

The grading report now follows this exact structure:

```
## 📝 Exam Grading Report

**Score:** X/Y (Z%)

### 🔍 Incorrect Answers & Explanations
  (LLM explanation + optional RAG remediation note per mistake)

### 📊 Topic Analytics
  (per-topic accuracy bar + mastery label + strongest/weakest call-out)

  ### 🎯 Readiness Score
  (mean accuracy + label)

### 🧩 Knowledge Gaps Detected          ← only shown when gaps exist
  (cluster name list)

### 📈 Progress Trend                    ← only shown after ≥1 exam on record
  (exam-by-exam score list + improvement delta)

### 🗺️ Recommended Learning Path        ← only shown when mistakes exist
  (ordered steps, weakest topic first, course link per step)

### 📚 Recommended Courses              ← original section, preserved
  (up to 3 links, same Tavily results reused from learning path)
```

Sections that have nothing to show (empty profile, no gaps, first exam) return empty strings and are silently omitted from the report — no ugly "N/A" blocks.

---

## 6. Integration Points — What Each Team Must Do

### Team 1 — RAG Remediation Integration

**File to edit:** `learner_profile.py`

**Function to implement:** `get_remediation_material(topic: str) -> Optional[Dict]`

**Current stub:**
```python
def get_remediation_material(topic: str) -> Optional[Dict]:
    return None  # graceful fallback
```

**Replace with a Qdrant retrieval call. Example:**
```python
def get_remediation_material(topic: str) -> Optional[Dict]:
    from rag_tool import retrieve          # Team 1's retrieval function
    results = retrieve(query=topic, top_k=1)
    if not results:
        return None
    hit = results[0]
    return {
        "title":   hit.get("title", topic),
        "source":  hit.get("source", "Course Materials"),
        "excerpt": hit.get("text", "")[:300],   # 1–2 sentences
    }
```

**What happens automatically once you do this:**

Every incorrect answer in the grading report will gain a block like:

```
- *Explanation:* The correct answer is 'b' because...

  📌 **Recommended Reading:** Vector Embeddings — Chapter 3
  *Source: Foundations of LLMs, p. 47*
  > Embeddings convert tokens into dense float vectors...
```

No other file needs to change.

---

### Team 2 — Exam Generator (Adaptive Focus)

**Where to read:** `state["next_exam_focus"]`

**When to read it:** At the start of your MCQ generation function, before selecting topics.

**Contract:**
- `next_exam_focus` is a `List[str]` of up to 3 topic strings, weakest first.
- It is `None` (or absent) on the very first exam — your code must handle that.
- On subsequent exams it is populated by Team 3 after every grade call.

**Recommended implementation pattern:**
```python
def generate_exam(state: AgentState, n_questions: int = 5) -> List[Question]:
    focus_topics = state.get("next_exam_focus") or []

    if focus_topics:
        # Bias question selection: pull more questions from focus topics
        # e.g. 60 % from focus, 40 % from general pool
        n_focus   = min(len(focus_topics), round(n_questions * 0.6))
        n_general = n_questions - n_focus
        questions  = generate_from_topics(focus_topics, n_focus)
        questions += generate_from_general_pool(n_general)
    else:
        # First exam — generate from general pool as usual
        questions = generate_from_general_pool(n_questions)

    return questions
```

This creates the adaptive learning loop:
```
Exam → Grade → Weaknesses detected → next_exam_focus set
→ Next Exam biased toward weaknesses → Grade → ...
```

---

## 7. Feature Reference

| # | Feature | Module | State field written |
|---|---|---|---|
| 1 | Topic Performance Analytics | `analytics.py` | `learner_profile` |
| 2 | Learning Analytics Report Section | `analytics.py` | — |
| 3 | Exam History | `progress_tracker.py` | `exam_history` |
| 4 | Progress Trend Analysis | `progress_tracker.py` | — |
| 5 | Adaptive Exam Targeting | `learner_profile.py` | `next_exam_focus` |
| 6 | Mastery Level Classification | `analytics.py` | — |
| 7 | Knowledge Gap Detection | `knowledge_gap.py` | — |
| 8 | Learning Path Generation | `learning_path.py` | — |
| 9 | RAG Remediation Integration | `learner_profile.py` | — (Team 1 hook) |
| 10 | Readiness Score | `analytics.py` | — |

---

## 8. Running the Demo

```bash
# 1. Install dependencies (if not already installed)
pip install langchain-core langgraph langchain-google-genai

# 2. (Optional) Add API keys to .env
cp .env.example .env
# Edit .env and fill in TAVILY_API_KEY, GEMINI_API_KEY or OPENAI_API_KEY

# 3. Run the smoke test — works without any API keys (mock fallback)
python run_demo.py
```

**Expected output (no API keys, mock mode):**
- Full grading report for a 5-question exam where Q3 and Q4 are wrong.
- Topic Analytics section with mastery labels.
- Readiness Score.
- Progress Trend (one exam, so "not enough history").
- Recommended Learning Path (2 steps for the 2 missed topics).
- Recommended Courses (mock URLs).

---

## 9. Design Principles & Non-Functional Notes

**Backward compatibility is non-negotiable.** The public function signature of `grade_exam` and the `Question` schema are frozen. All additions go through new optional state fields or new modules.

**Graceful degradation everywhere.** Every new function checks for `None` / empty inputs and returns safe defaults. The system never raises an exception because `learner_profile` is missing.

**No duplicate Tavily calls.** Course data is fetched once per topic per process invocation and stored in `_course_cache`. The learning path builder receives the same `course_map` dict instead of triggering new searches.

**O(n) complexity.** All profile updates, gap detection, and path building iterate over questions or topics at most once. No nested loops over the full history.

**Modular by design.** Each new file has one clear responsibility. Adding a new analytics metric means editing `analytics.py` only. Adding a new gap cluster means editing `knowledge_gap.py` only. `grader_tool.py` is the only file that imports from multiple modules — it is the assembly point, not the logic point.

**SOLID alignment:**
- *Single Responsibility* — each module owns one concern.
- *Open/Closed* — extend gap clusters or mastery thresholds without touching callers.
- *Dependency Inversion* — `grader_tool.py` depends on module interfaces, not implementations. Team 1 can swap the RAG backend without touching the grader.
