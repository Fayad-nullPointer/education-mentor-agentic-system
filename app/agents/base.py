from abc import ABC, abstractmethod


class BaseAgent(ABC):
    name: str
    description: str

    @abstractmethod
    def run(self, query: str, **kwargs) -> str: ...
