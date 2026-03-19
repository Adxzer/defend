from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
import yaml


@dataclass
class StubIntentOutput:
    label: str
    score: float


class StubIntentClassifier:
    def classify(self, text: str) -> StubIntentOutput:  # noqa: ARG002
        # Always fast-pass as benign so safe-pass only triggers when regex sees CONTINUE.
        return StubIntentOutput(label="benign", score=1.0)


class StubDefendClassifier:
    def classify(self, text: str) -> SimpleNamespace:  # noqa: ARG002
        # Always non-injection; session accumulation is driven by regex decisions in tests.
        return SimpleNamespace(is_injection=False, probability=0.0)


@dataclass
class StubProviderResult:
    action: str
    provider: str
    score: float | None = None
    reason: str | None = None
    modules_triggered: list[str] | None = None
    latency_ms: int | None = None


class StubOutputProvider:
    supports_modules = True
    name = "stub-llm"

    def __init__(self) -> None:
        self.last_text: str | None = None
        self.last_session_id: str | None = None
        self.last_modules: list[object] | None = None

    async def evaluate(self, text: str, session_id: str | None = None, modules: list[object] | None = None):  # noqa: ANN001
        self.last_text = text
        self.last_session_id = session_id
        self.last_modules = modules or []
        return StubProviderResult(
            action="pass",
            provider=self.name,
            score=0.0,
            reason=None,
            modules_triggered=[],
            latency_ms=1,
        )


@pytest.fixture(scope="session", autouse=True)
def enable_output_guard() -> None:
    """
    The service reads config from a fixed path: `defend.config.yaml`.
    For E2E tests we enable `guards.output.enabled` so `POST /v1/guard/output`
    is exercised end-to-end.
    """

    repo_root = Path(__file__).resolve().parents[1]
    config_path = repo_root / "defend.config.yaml"

    original = config_path.read_text(encoding="utf-8")
    data = yaml.safe_load(original) or {}
    guards = data.setdefault("guards", {})
    output = guards.setdefault("output", {})
    output["enabled"] = True
    output["provider"] = "claude"  # required by config schema

    config_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    # Clear cached config after rewriting.
    from defend_api import config as config_mod

    config_mod.get_defend_config.cache_clear()
    config_mod.get_settings.cache_clear()

    try:
        yield
    finally:
        config_path.write_text(original, encoding="utf-8")
        config_mod.get_defend_config.cache_clear()
        config_mod.get_settings.cache_clear()


@pytest.fixture(autouse=True)
def patch_models(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Prevent heavy ML model initialization (transformers / sentence-transformers)
    during FastAPI startup and during pipeline execution.
    """

    stub_intent = StubIntentClassifier()
    stub_defend = StubDefendClassifier()

    # Bound imports used by main.py startup event.
    import defend_api.main as main_mod
    monkeypatch.setattr(main_mod, "get_intent_classifier", lambda: stub_intent)
    monkeypatch.setattr(main_mod, "get_defend_classifier", lambda: stub_defend)

    # Bound imports used by pipeline components.
    monkeypatch.setattr(
        "defend_api.pipeline.intent_fastpass.get_intent_classifier",
        lambda: stub_intent,
        raising=True,
    )
    monkeypatch.setattr(
        "defend_api.routers.health.get_defend_classifier",
        lambda: stub_defend,
        raising=False,
    )
    monkeypatch.setattr("defend_api.models.defend_qwen.get_defend_classifier", lambda: stub_defend, raising=True)
    monkeypatch.setattr(
        "defend_api.providers.defend.provider.get_defend_classifier",
        lambda: stub_defend,
        raising=True,
    )


@pytest.fixture
def output_provider_stub() -> StubOutputProvider:
    return StubOutputProvider()


@pytest.fixture(autouse=True)
def patch_output_provider(monkeypatch: pytest.MonkeyPatch, output_provider_stub: StubOutputProvider) -> None:
    import defend_api.routers.guard as guard_router

    # guard_output uses the locally imported `get_provider` symbol; patch it directly.
    monkeypatch.setattr(guard_router, "get_provider", lambda *_args, **_kwargs: output_provider_stub)


@pytest.fixture(autouse=True)
def reset_in_memory_state() -> None:
    import defend_api.guard_session as guard_session_mod
    import defend_api.session as session_mod
    import defend_api.providers.orchestrator as provider_orch_mod
    import defend_api.guard_session as guard_store_mod

    guard_session_mod._GUARD_SESSIONS.clear()

    session_mod._IN_MEMORY_SESSIONS.clear()
    session_mod._IN_MEMORY_EXPIRES_AT.clear()
    session_mod.get_session_backend.cache_clear()

    provider_orch_mod.get_provider_orchestrator(reset=True)

    # Force GuardSessionStore recreation on next request.
    guard_store_mod._guard_store = None


@pytest.fixture
def client(output_provider_stub: StubOutputProvider) -> TestClient:  # noqa: ARG001
    # Creating the TestClient runs FastAPI startup events, which our fixtures patch/stub.
    from defend_api.main import app

    with TestClient(app) as c:
        yield c

