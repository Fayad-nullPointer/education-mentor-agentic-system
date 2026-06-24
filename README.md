# EduMentor AI — Grader & Recommender Subsystem (Team 3)

Welcome to the implementation repository for **Sub-Team 3 (Ahmed & Ali)**. This subsystem handles answer parsing, exam grading, LLM-generated mistake explanations, and domain-restricted course recommendations.

This document serves as an integration guide for the remaining sub-teams (**Team 1: RAG** and **Team 2: MCQ Generator**) to wire their modules into the unified LangGraph ReAct agent.

---

## 🏗️ Architectural Overview & Integration Flow

Our subsystem bridges the exam generation phase with course recommendations by reading from the shared `AgentState` and querying Tavily.

```mermaid
graph TD
    subgraph Team 2: Exam Generator
        MCQ[Generate MCQs] -->|Write to State| State[(AgentState: active_exam)]
    end

    subgraph Team 3: Grader & Recommender (This Subsystem)
        State -->|Read Questions| Grader[grade_exam Tool]
        UserAns[User Answers: '1-b, 2-c'] -->|Parsed via Regex| Grader
        Grader -->|Incorrect Topics| Tavily[Tavily Search API]
        Grader -->|Mistake Analysis| LLM[LLM Explainer]
        Tavily -->|Restrict to Coursera, Udemy, DeepLearning.AI| Recommendations[Markdown Report]
        LLM --> Recommendations
    end

    subgraph Team 1 & Main Integration
        Recommendations -->|Render in Chat| Learner((Learner Chat Interface))
    end
```

---

## 🗃️ The Integration Contract (AgentState Schema)

To ensure seamless integration, all sub-teams must adhere to the shared `AgentState` schema defined in `state.py`.

### 1. Questions Schema (`Question` TypedDict)
When the **Exam Generator (Team 2)** creates multiple-choice questions, it must write them into `AgentState["active_exam"]` as a list conforming to the following structure:

```python
class Question(TypedDict):
    id: int                   # Question number (1, 2, 3, etc.)
    question: str             # The text of the question
    options: Dict[str, str]   # MCQ options, mapping choice key to text (e.g. {"a": "Choice A", "b": "Choice B"})
    topic: str                # Topic category (e.g., "RAG Embeddings", "Vector Search")
    correct_option: str       # Correct choice key (e.g., "b")
```

### 2. State Schema (`AgentState` TypedDict)
The unified LangGraph graph runs on this state:

```python
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages] # Chat history
    active_exam: Optional[List[Question]]                 # List of active exam questions
```

---

## 🛠️ The Grader Tool

Defined in `grader_tool.py`, the core tool is `grade_exam`. 

- **Input:** `student_answers: str` (e.g., `"1-b, 2-c, 3-a"`)
- **State Injection:** Binds to `InjectedState` to automatically pull the `active_exam` questions from the active thread memory.
- **Output:** Returns a comprehensive markdown report including:
  1. Score percentage (e.g. `3/5 (60.0%)`).
  2. Mistakes section, illustrating the question, the student's answer, the correct answer, and an LLM-generated explanation of the mistake.
  3. Up to **3 recommended courses** fetched dynamically from approved domains (`coursera.org`, `udemy.com`, `deeplearning.ai`) matching the missed topics.

---

## ⚙️ Configuration & Installation

This branch follows a **zero-additional-library installation policy** and reads variables from `.env` manually via `config.py`.

### 1. Environment Setup
Create a `.env` file in the root folder (a template is provided at `.env`):

```env
# Tavily API Key for course recommendations
TAVILY_API_KEY=your_tavily_api_key_here

# LLM Keys (Gemini is preferred, but OpenAI is supported)
GEMINI_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here

# Chosen Model (Format: provider/model-name)
LLM_MODEL=gemini/gemini-1.5-flash
```
*(If no API keys are supplied, the subsystem gracefully falls back to mock courses and static template explanation text so your code runs error-free during local testing).*

---

## 🚀 Verification & Live Demo

We have provided a standalone simulation script `run_demo.py` to verify the grading logic without needing to run the full graph. It simulates a 5-question exam and a student submitting `"1-b, 2-c, 3-a, 4-d, 5-b"`.

### Run the demo:
```bash
python run_demo.py
```

---

## 🔗 How to Wire Our Subsystem into the Unified Agent

On **Day 2/3 Integration Phase**, the coordinator can instantiate our agent or import our tool and add it to the primary ReAct agent list.

### Importing the Tool:
```python
from grader_tool import grade_exam

# Add 'grade_exam' to the list of tools passed to the ReAct agent / ToolNode
tools = [rag_tool, exam_generator_tool, grade_exam]
```

### Importing our Deep Agent Wrapper:
If initializing individual agent nodes in a supervisor-agent structure:
```python
from grader_agent import get_grader_agent

grader_agent = get_grader_agent()
# grader_agent is a prebuilt LangChain Deep Agent loaded with the grading prompt and tools
```
