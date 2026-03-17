from __future__ import annotations

import base64
import json
import zlib
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Literal, Optional


ProviderNameLiteral = Literal["defend", "claude", "openai"]
GuardActionLiteral = Literal["block", "flag", "retry_suggested"]


@dataclass
class ProvidersConfig:
    primary: ProviderNameLiteral
    fallback: Optional[ProviderNameLiteral] = None
    # Environment-variable names for API keys; actual keys stay in env.
    anthropic_env: Optional[str] = None
    openai_env: Optional[str] = None


@dataclass
class ModulesConfig:
    input: List[Any] = field(default_factory=list)
    output: List[Any] = field(default_factory=list)


@dataclass
class SettingsConfig:
    session_block_threshold: int = 3
    session_ttl_seconds: int = 300
    confidence_threshold: float = 0.7
    thresholds_block: float = 0.7
    thresholds_flag: float = 0.3
    log_level: str = "info"


@dataclass
class CustomModuleDefinition:
    name: str
    direction: Literal["input", "output"]
    prompt: str
    rules: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PresetConfig:
    """
    Logical configuration model used for compressed config tokens.

    This structure is intentionally decoupled from the on-disk
    `defend.config.yaml` schema but is fully mappable to it.
    """

    providers: ProvidersConfig
    modules: ModulesConfig = field(default_factory=ModulesConfig)
    settings: SettingsConfig = field(default_factory=SettingsConfig)
    custom_modules: List[CustomModuleDefinition] = field(default_factory=list)

    def to_token_payload(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_token_payload(payload: Dict[str, Any]) -> "PresetConfig":
        providers = ProvidersConfig(**payload["providers"])
        modules = ModulesConfig(**payload.get("modules", {}))
        settings = SettingsConfig(**payload.get("settings", {}))
        custom_modules = [
            CustomModuleDefinition(**cm) for cm in payload.get("custom_modules", [])
        ]
        return PresetConfig(
            providers=providers,
            modules=modules,
            settings=settings,
            custom_modules=custom_modules,
        )


def encode_config(config: PresetConfig, *, compress: bool = True) -> str:
    """
    Encode a `PresetConfig` into a URL-safe string.

    Steps:
    - Serialize to JSON with stable key ordering.
    - Optionally zlib-compress.
    - Base64-url encode without padding.
    """

    payload = config.to_token_payload()
    data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if compress:
        data = zlib.compress(data)
    token = base64.urlsafe_b64encode(data).rstrip(b"=")
    return token.decode("ascii")


def decode_config(token: str, *, compressed: bool = True) -> PresetConfig:
    """
    Decode a URL-safe config token into a `PresetConfig`.
    """

    padding = "=" * (-len(token) % 4)
    raw = base64.urlsafe_b64decode(token + padding)
    if compressed:
        raw = zlib.decompress(raw)
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Decoded config token did not produce an object")
    return PresetConfig.from_token_payload(payload)


def render_defend_yaml(config: PresetConfig) -> Dict[str, Any]:
    """
    Render a `PresetConfig` into a dict matching `defend.config.yaml`.
    """

    providers = config.providers
    settings = config.settings

    api_keys: Dict[str, Any] = {}
    if providers.anthropic_env:
        api_keys["anthropic_env"] = providers.anthropic_env
    if providers.openai_env:
        api_keys["openai_env"] = providers.openai_env

    thresholds = {
        "block": settings.thresholds_block,
        "flag": settings.thresholds_flag,
    }

    # Provider-layer modules map directly.
    modules = list(config.modules.input)

    guards_input = {
        "provider": providers.primary,
        "modules": list(config.modules.input),
    }

    guards_output: Dict[str, Any] = {
        "provider": providers.primary if providers.primary in {"claude", "openai"} else "claude",
        "modules": list(config.modules.output),
        "on_fail": "block",
    }

    guards = {
        "input": guards_input,
        "output": guards_output,
        "session_ttl_seconds": settings.session_ttl_seconds,
    }

    return {
        "provider": {
            "primary": providers.primary,
            "fallback": providers.fallback,
        },
        "api_keys": api_keys,
        "modules": modules or None,
        "thresholds": thresholds,
        "confidence_threshold": settings.confidence_threshold,
        "guards": guards,
    }


