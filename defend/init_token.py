from __future__ import annotations

import base64
import json
import zlib
from dataclasses import dataclass
from typing import Any, Dict, Optional


TOKEN_PREFIX = "defend_v1_"


class InitTokenError(ValueError):
    pass


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(s: str) -> bytes:
    padded = s + "=" * ((4 - (len(s) % 4)) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _canonical_json(obj: Any) -> bytes:
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode("utf-8")


@dataclass(frozen=True)
class InitTokenPayload:
    v: int
    data: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {"v": self.v, **self.data}


def encode_init_token(payload: Dict[str, Any]) -> str:
    """
    Encode a shareable init token.

    - Prefix: defend_v1_
    - Body: zlib-compressed canonical JSON, base64url (no padding)
    """
    v = int(payload.get("v") or 1)
    if v != 1:
        raise InitTokenError(f"Unsupported token version: v={v}")

    blob = _canonical_json(payload)
    compressed = zlib.compress(blob, level=9)
    return TOKEN_PREFIX + _b64url_encode(compressed)


def decode_init_token(token: str) -> Dict[str, Any]:
    if not isinstance(token, str) or not token:
        raise InitTokenError("Token must be a non-empty string")

    if token.startswith(TOKEN_PREFIX):
        token = token[len(TOKEN_PREFIX) :]
    else:
        raise InitTokenError(f"Token must start with '{TOKEN_PREFIX}'")

    try:
        compressed = _b64url_decode(token)
    except Exception as exc:  # pragma: no cover
        raise InitTokenError(f"Invalid base64url token: {exc}") from exc

    try:
        raw = zlib.decompress(compressed)
    except Exception as exc:  # pragma: no cover
        raise InitTokenError(f"Invalid compressed token: {exc}") from exc

    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:  # pragma: no cover
        raise InitTokenError(f"Invalid JSON payload: {exc}") from exc

    if not isinstance(payload, dict):
        raise InitTokenError("Token payload must be a JSON object")

    v = payload.get("v")
    if v != 1:
        raise InitTokenError(f"Unsupported token version: v={v!r}")

    return payload


def payload_to_defend_config_dict(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a v1 token payload into a `defend.config.yaml` dict.

    This intentionally contains no secrets; API key values are expected to come
    from environment variables.
    """
    if payload.get("v") != 1:
        raise InitTokenError("payload_to_defend_config_dict expects v1 payload")

    providers = payload.get("providers") or {}
    guards = payload.get("guards") or {}
    models = payload.get("models") or None

    cfg: Dict[str, Any] = {
        "provider": {
            "primary": (providers.get("primary") or "defend"),
        },
        "api_keys": {
            "anthropic_env": "ANTHROPIC_API_KEY",
            "openai_env": "OPENAI_API_KEY",
        },
        "modules": payload.get("modules") or [],
        "thresholds": payload.get("thresholds") or {"block": 0.7, "flag": 0.3},
        "confidence_threshold": payload.get("confidence_threshold", 0.7),
        "guards": {
            "input": guards.get("input") or {"provider": "defend", "modules": []},
            "output": guards.get("output") or {"enabled": True, "provider": "claude", "modules": [], "on_fail": "block"},
            "session_ttl_seconds": int((guards.get("session_ttl_seconds") or 300)),
        },
    }

    if isinstance(models, dict) and models:
        cfg["models"] = {k: v for k, v in models.items() if isinstance(v, str) and v}

    # If output is explicitly disabled in the token, keep a valid provider value anyway.
    out = cfg.get("guards", {}).get("output") or {}
    if out.get("enabled") is False:
        out.setdefault("provider", "claude")

    return cfg


def defend_config_dict_to_payload(config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert an existing `defend.config.yaml` dict into a v1 token payload.
    """
    provider = config_dict.get("provider") or {}
    guards = config_dict.get("guards") or {}

    payload: Dict[str, Any] = {
        "v": 1,
        "providers": {
            "primary": provider.get("primary") or "defend",
        },
        "modules": config_dict.get("modules") or [],
        "thresholds": config_dict.get("thresholds") or {"block": 0.7, "flag": 0.3},
        "confidence_threshold": config_dict.get("confidence_threshold", 0.7),
        "guards": {
            "input": guards.get("input") or {"provider": "defend", "modules": []},
            "output": guards.get("output") or {"enabled": True, "provider": "claude", "modules": [], "on_fail": "block"},
            "session_ttl_seconds": guards.get("session_ttl_seconds", 300),
        },
    }

    models = config_dict.get("models")
    if isinstance(models, dict) and models:
        payload["models"] = {k: v for k, v in models.items() if isinstance(v, str) and v}

    return payload


def safe_round_trip(token: str) -> str:
    payload = decode_init_token(token)
    return encode_init_token(payload)

