from functools import lru_cache
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent

from app.core.llm import get_llm
from app.core.state import AgentState
from app.tools.course_search import search_courses
from app.tools.exam_grader import grade_exam

_SYSTEM_PROMPT = (Path(__file__).parent.parent / "prompts" / "grader_agent.md").read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def _get_agent():
    return create_react_agent(
        model=get_llm(),
        tools=[grade_exam, search_courses],
        prompt=SystemMessage(content=_SYSTEM_PROMPT),
        checkpointer=InMemorySaver(),
        state_schema=AgentState,
    )


def ask(query: str, thread_id: str = "grader-session") -> str:
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 10}
    result = _get_agent().invoke(
        {"messages": [HumanMessage(content=query)]},
        config=config,
    )
    return result["messages"][-1].content
