from functools import lru_cache
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent

from app.core.llm import get_llm
from app.tools.rag_search import rag_search

_SYSTEM_PROMPT = (Path(__file__).parent.parent / "prompts" / "rag_agent.md").read_text()


@lru_cache(maxsize=1)
def _get_agent():
    return create_react_agent(
        model=get_llm(),
        tools=[rag_search],
        prompt=SystemMessage(content=_SYSTEM_PROMPT),
        checkpointer=InMemorySaver(),
    )


def ask(query: str, thread_id: str = "default-session") -> str:
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 10}
    result = _get_agent().invoke(
        {"messages": [HumanMessage(content=query)]},
        config=config,
    )
    return result["messages"][-1].content
