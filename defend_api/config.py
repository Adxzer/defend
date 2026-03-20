from functools import lru_cache
from pathlib import Path
from typing import Any, List, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .schemas import GuardAction, ProviderName


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Service
    DEFEND_API_HOST: str = "0.0.0.0"
    DEFEND_API_PORT: int = 8000

    # Models
    INTENT_MODEL_ID: str = "sentence-transformers/all-MiniLM-L6-v2"
    DEFEND_MODEL_ID: str = "Adaxer/defend"

    # Thresholds
    INTENT_FASTPASS_THRESHOLD: float = 0.85
    INTENT_FASTPASS_ENABLED: bool = True
    REGEX_BLOCK_THRESHOLD: float = 0.9
    REGEX_FLAG_THRESHOLD: float = 0.6
    # If any regex match occurs in one of these categories, block immediately.
    REGEX_BLOCK_CATEGORIES: List[str] = Field(default_factory=lambda: ["system_prompt_extraction"])
    # If total score didn't cross thresholds, still flag when we see multiple independent matches.
    REGEX_FLAG_MIN_MATCHES: int = 2

    # Defend model runtime caps 
    DEFEND_MAX_INPUT_TOKENS: int = 1024
    DEFEND_INJECTION_THRESHOLD: float = 0.5

    # Semantic provider input caps 
    ANTHROPIC_MAX_INPUT_TOKENS: int = 2048
    OPENAI_MAX_INPUT_TOKENS: int = 2048
    
    # Sessions
    SESSION_TTL_SECONDS: int = 1800
    SESSION_BLOCK_THRESHOLD: int = 3


class ProviderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary: ProviderName

    @field_validator("primary")
    @classmethod
    def validate_primary(cls, v: ProviderName) -> ProviderName:
        if v not in {ProviderName.DEFEND, ProviderName.CLAUDE, ProviderName.OPENAI}:
            raise ValueError("provider.primary must be one of 'defend', 'claude', or 'openai'")
        return v


class TopicModuleConfig(BaseModel):
    allowed_topics: List[str] = Field(default_factory=list)


class CustomModuleConfig(BaseModel):
    prompt: str


class ApiKeysConfig(BaseModel):
    anthropic_env: Optional[str] = None
    openai_env: Optional[str] = None


class ModelsConfig(BaseModel):
    """
    Optional provider model overrides.

    When absent, providers use their built-in defaults.
    """

    claude: Optional[str] = None
    openai: Optional[str] = None


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

    @model_validator(mode="after")
    def validate_relationship(self) -> "ThresholdsConfig":
        if not self.flag < self.block:
            raise ValueError("thresholds.flag must be less than thresholds.block")
        return self


class GuardsInputConfig(BaseModel):
    provider: ProviderName = ProviderName.DEFEND
    modules: List[Any] = Field(default_factory=list)


class GuardsOutputConfig(BaseModel):
    enabled: bool = True
    provider: ProviderName = ProviderName.CLAUDE
    modules: List[Any] = Field(default_factory=list)
    on_fail: GuardAction = GuardAction.BLOCK  # block | flag

    @field_validator("provider")
    @classmethod
    def validate_output_provider(cls, v: ProviderName) -> ProviderName:
        # If output guard is disabled, keep provider validation permissive.
        # (The route handler will short-circuit before hitting the provider.)
        #
        # We still keep the enum type for consistent config shape.
        if v not in {ProviderName.CLAUDE, ProviderName.OPENAI}:
            raise ValueError("guards.output.provider must be 'claude', or 'openai'")
        return v

    @field_validator("on_fail")
    @classmethod
    def validate_on_fail(cls, v: GuardAction) -> GuardAction:
        if v not in {GuardAction.BLOCK, GuardAction.FLAG}:
            raise ValueError("guards.output.on_fail must be 'block' or 'flag'")
        return v


class GuardsConfig(BaseModel):
    input: GuardsInputConfig = GuardsInputConfig()
    output: GuardsOutputConfig = GuardsOutputConfig()
    session_ttl_seconds: int = 300


class DefendConfig(BaseModel):
    provider: ProviderConfig
    api_keys: ApiKeysConfig = ApiKeysConfig()
    models: ModelsConfig = ModelsConfig()
    modules: Optional[list[Any]] = None
    thresholds: ThresholdsConfig = ThresholdsConfig()
    confidence_threshold: float = 0.7
    guards: GuardsConfig = GuardsConfig()

    @field_validator("confidence_threshold")
    @classmethod
    def validate_confidence_threshold(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("confidence_threshold must be between 0 and 1 (inclusive)")
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


@lru_cache(maxsize=1)
def get_defend_config() -> DefendConfig:
    config_path = Path("defend.config.yaml")
    if not config_path.exists():
        raise ValueError("defend.config.yaml not found in project root. Run `defend init` to generate it.")

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    try:
        return DefendConfig.model_validate(raw)
    except ValidationError as exc:  # pragma: no cover - defensive
        raise ValueError(f"Invalid defend.config.yaml: {exc}") from exc

