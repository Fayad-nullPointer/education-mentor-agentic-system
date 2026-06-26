from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Google Gemini
    google_api_key: str

    # Optional: Tavily for course search
    tavily_api_key: str = ""

    # LLM model name
    llm_model: str = "gemini-2.5-flash"

    # RAG collection (used by rag_agent / rag_search tool)
    qdrant_url: str
    qdrant_api_key: str
    collection_name: str

    # Exam collection (used by exam_agent / exam_generator tool)
    # Falls back to RAG collection values if not provided
    exam_qdrant_url: str = ""
    exam_qdrant_api_key: str = ""
    exam_collection_name: str = ""

    # Embedding model for dense retrieval
    embedding_model: str

    # RAG settings
    chunk_size: int = 512
    chunk_overlap: int = 50
    top_k: int = 5

    # Exam settings
    default_n_questions: int = 5

    # App
    app_env: str = "development"
    app_port: int = 8000

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
