"""
Course search tool — queries Tavily for course recommendations on a topic.
Falls back to a curated mock database when no Tavily API key is provided.
"""

from typing import Any

import requests
from langchain_core.tools import tool

from app.core.config import get_settings

_course_cache: dict[str, list[dict[str, Any]]] = {}

_MOCK_DB: dict[str, list[dict[str, Any]]] = {
    "rag": [
        {"title": "Retrieval-Augmented Generation (RAG) Specialization", "url": "https://www.coursera.org/specializations/rag-systems", "source": "Coursera"},
        {"title": "Vector Databases & Embeddings for RAG", "url": "https://www.deeplearning.ai/short-courses/vector-databases-embeddings", "source": "DeepLearning.AI"},
        {"title": "Mastering RAG with LangChain and LlamaIndex", "url": "https://www.udemy.com/course/mastering-rag", "source": "Udemy"},
    ],
    "langgraph": [
        {"title": "AI Agents in LangGraph", "url": "https://www.deeplearning.ai/short-courses/ai-agents-langgraph", "source": "DeepLearning.AI"},
        {"title": "Building Multi-Agent Systems", "url": "https://www.coursera.org/learn/multi-agent-systems", "source": "Coursera"},
    ],
    "agent": [
        {"title": "AI Agents in LangGraph", "url": "https://www.deeplearning.ai/short-courses/ai-agents-langgraph", "source": "DeepLearning.AI"},
        {"title": "Building AI Agents with Python", "url": "https://www.udemy.com/course/building-ai-agents", "source": "Udemy"},
    ],
    "transformer": [
        {"title": "Attention is All You Need — Explained", "url": "https://www.deeplearning.ai/short-courses/attention-mechanism", "source": "DeepLearning.AI"},
        {"title": "Hugging Face NLP Course", "url": "https://huggingface.co/learn/nlp-course", "source": "Hugging Face"},
    ],
    "llm": [
        {"title": "Large Language Models with Semantic Search", "url": "https://www.deeplearning.ai/short-courses/large-language-models-semantic-search", "source": "DeepLearning.AI"},
        {"title": "Fine-tuning Large Language Models", "url": "https://www.deeplearning.ai/short-courses/finetuning-large-language-models", "source": "DeepLearning.AI"},
    ],
}


def search_courses_for_topic(topic: str) -> list[dict[str, Any]]:
    """Search Tavily for courses on a topic, with in-process caching and mock fallback."""
    if topic in _course_cache:
        return _course_cache[topic]

    settings = get_settings()
    if not settings.tavily_api_key:
        topic_lower = topic.lower()
        result = next(
            (courses for key, courses in _MOCK_DB.items() if key in topic_lower),
            [
                {"title": f"Introduction to {topic}", "url": "https://www.coursera.org", "source": "Coursera"},
                {"title": f"Advanced {topic} Guide", "url": "https://www.deeplearning.ai", "source": "DeepLearning.AI"},
            ],
        )
        _course_cache[topic] = result
        return result

    payload = {
        "api_key": settings.tavily_api_key,
        "query": f"{topic} course",
        "include_domains": ["coursera.org", "udemy.com", "deeplearning.ai", "huggingface.co"],
        "max_results": 3,
    }
    try:
        response = requests.post("https://api.tavily.com/search", json=payload, timeout=10)
        response.raise_for_status()
        items = response.json().get("results", [])
        result = [
            {
                "title": item.get("title", "Course link"),
                "url": item.get("url", ""),
                "source": item.get("url", "").split("/")[2] if "/" in item.get("url", "") else "Course Platform",
            }
            for item in items
        ]
    except Exception as e:
        print(f"Warning: Tavily search failed ({e}). Using fallback.")
        result = [{"title": f"{topic} Course", "url": f"https://www.coursera.org/search?query={topic.replace(' ', '+')}", "source": "Coursera"}]

    _course_cache[topic] = result
    return result


@tool
def search_courses(topic: str) -> str:
    """
    Search for online courses to help the student improve on a specific topic.

    Args:
        topic: The subject area to search courses for (e.g. 'RAG', 'Transformers', 'LangGraph').
    """
    courses = search_courses_for_topic(topic)
    if not courses:
        return f"No courses found for topic: {topic}"
    lines = [f"**Courses for '{topic}':**"]
    for c in courses:
        lines.append(f"- [{c['title']}]({c['url']}) *({c['source']})*")
    return "\n".join(lines)
