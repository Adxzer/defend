from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Service
    DEFEND_API_HOST: str = "0.0.0.0"
    DEFEND_API_PORT: int = 8000

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Intent (L2) – SentenceTransformer backend
    INTENT_MODEL_ID: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Perplexity (L4) – GPT-2 language model
    PERPLEXITY_MODEL_ID: str = "gpt2"

    # Defend (L6) – Adaxer/defend classifier
    DEFEND_MODEL_ID: str = "Adaxer/defend"

    # Thresholds
    INTENT_FASTPASS_THRESHOLD: float = 0.85
    REGEX_BLOCK_THRESHOLD: float = 0.9
    REGEX_FLAG_THRESHOLD: float = 0.6
    PERPLEXITY_BLOCK_THRESHOLD: float = 80.0
    SESSION_BLOCK_THRESHOLD: float = 0.9

    # Hugging Face
    HUGGINGFACE_HUB_TOKEN: Optional[str] = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

