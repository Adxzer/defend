from functools import lru_cache
from pathlib import Path
from typing import Any, List, Optional

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Service
    DEFEND_API_HOST: str = "0.0.0.0"
    DEFEND_API_PORT: int = 8000

    # Models
    INTENT_MODEL_ID: str = "sentence-transformers/all-MiniLM-L6-v2"
    PERPLEXITY_MODEL_ID: str = "gpt2"
    DEFEND_MODEL_ID: str = "Adaxer/defend"

    # Thresholds
    INTENT_FASTPASS_THRESHOLD: float = 0.85
    REGEX_BLOCK_THRESHOLD: float = 0.9
    REGEX_FLAG_THRESHOLD: float = 0.6
    PERPLEXITY_BLOCK_THRESHOLD: float = 80.0
    SESSION_BLOCK_THRESHOLD: float = 0.9


class ProviderConfig(BaseModel):
    primary: str
    fallback: Optional[str] = None

    @field_validator("primary")
    @classmethod
    def validate_primary(cls, v: str) -> str:
        if v not in {"defend", "claude", "openai"}:
            raise ValueError("provider.primary must be one of 'defend', 'claude', or 'openai'")
        return v

    @field_validator("fallback")
    @classmethod
    def validate_fallback(cls, v: Optional[str], info: Any) -> Optional[str]:
        if v is None:
            return v
        if v != "defend":
            raise ValueError("provider.fallback, when set, must be 'defend'")
        primary = info.data.get("primary")
        if primary not in {"claude", "openai"}:
            raise ValueError("provider.fallback is only valid when provider.primary is 'claude' or 'openai'")
        return v


class TopicModuleConfig(BaseModel):
    allowed_topics: List[str] = Field(default_factory=list)


class CustomModuleConfig(BaseModel):
    prompt: str


class ApiKeysConfig(BaseModel):
    anthropic_env: Optional[str] = None
    openai_env: Optional[str] = None


class ThresholdsConfig(BaseModel):
    block: float = 0.7
    flag: float = 0.3

    @field_validator("block", "flag")
    @classmethod
    def validate_range(cls, v: float) -> float:
        if not (0.0 < v < 1.0):
            raise ValueError("thresholds.block and thresholds.flag must be between 0 and 1 (exclusive)")
        return v

    @field_validator("block")
    @classmethod
    def validate_order(cls, v: float, info: Any) -> float:
        flag = info.data.get("flag")
        if flag is not None and not flag < v:
            raise ValueError("thresholds.flag must be less than thresholds.block")
        return v


class GuardsInputConfig(BaseModel):
    provider: str = "defend"
    modules: List[Any] = Field(default_factory=list)


class GuardsOutputConfig(BaseModel):
    provider: str = "claude"
    modules: List[Any] = Field(default_factory=list)
    on_fail: str = "block"  # block | flag | retry_suggested

    @field_validator("provider")
    @classmethod
    def validate_output_provider(cls, v: str) -> str:
        if v not in {"claude", "openai"}:
            raise ValueError("guards.output.provider must be 'claude' or 'openai'")
        return v

    @field_validator("on_fail")
    @classmethod
    def validate_on_fail(cls, v: str) -> str:
        if v not in {"block", "flag", "retry_suggested"}:
            raise ValueError("guards.output.on_fail must be 'block', 'flag', or 'retry_suggested'")
        return v


class GuardsConfig(BaseModel):
    input: GuardsInputConfig = GuardsInputConfig()
    output: GuardsOutputConfig = GuardsOutputConfig()
    session_ttl_seconds: int = 300


class DefendConfig(BaseModel):
    provider: ProviderConfig
    api_keys: ApiKeysConfig = ApiKeysConfig()
    modules: Optional[list[Any]] = None
    thresholds: ThresholdsConfig = ThresholdsConfig()
    guards: GuardsConfig = GuardsConfig()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


@lru_cache(maxsize=1)
def get_defend_config() -> DefendConfig:
    config_path = Path("defend.config.yaml")
    if not config_path.exists():
        raise ValueError("defend.config.yaml not found in project root")

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    try:
        return DefendConfig.model_validate(raw)
    except ValidationError as exc:  # pragma: no cover - defensive
        raise ValueError(f"Invalid defend.config.yaml: {exc}") from exc

