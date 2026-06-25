from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

QDRANT_URL          = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY      = os.getenv("QDRANT_API_KEY")
QDRANT_COLLECTION   = os.getenv("QDRANT_COLLECTION", "edumentor_corpus")
MODEL_NAME          = os.getenv("LLM_MODEL_NAME", "openai/gpt-4o-mini")
DEFAULT_N_QUESTIONS = int(os.getenv("DEFAULT_N_QUESTIONS", "5"))
