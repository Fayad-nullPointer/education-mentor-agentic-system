from app.agents.base import BaseAgent
from app.tools.base import BaseTool

_agents: dict[str, BaseAgent] = {}
_tools: dict[str, BaseTool] = {}


def register_agent(agent: BaseAgent) -> None:
    _agents[agent.name] = agent


def register_tool(tool: BaseTool) -> None:
    _tools[tool.name] = tool


def get_agent(name: str) -> BaseAgent:
    return _agents[name]


def get_tool(name: str) -> BaseTool:
    return _tools[name]


def all_agents() -> list[BaseAgent]:
    return list(_agents.values())


def all_tools() -> list[BaseTool]:
    return list(_tools.values())
