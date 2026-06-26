from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API Keys
    google_api_key: str

    # Vector Store
    qdrant_url: str
    qdrant_api_key: str
    collection_name: str

    # Embedding Model
    embedding_model: str

    # RAG Settings
    chunk_size: int = 512
    chunk_overlap: int = 50
    top_k: int = 5

    # App
    app_env: str = "development"
    app_port: int = 8000

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
