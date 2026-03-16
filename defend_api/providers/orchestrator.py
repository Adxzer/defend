from __future__ import annotations

from typing import Optional

from ..config import get_defend_config, get_settings
from ..modules import get_active_modules
from . import get_provider
from .base import ProviderResult, ProviderUnavailableError


class ProviderOrchestrator:
    """Dispatch to the configured provider(s) for the L6 decision.

    Phase 2: support defend, claude, and openai as single providers.
    Both-active gate logic and modules arrive in later phases.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._config = get_defend_config()

    async def evaluate(self, text: str, session_id: Optional[str] = None) -> ProviderResult:
        primary = self._config.provider.primary
        fallback = self._config.provider.fallback

        modules = []

        # Both-active mode: defend as gate in front of LLM provider.
        if fallback == "defend" and primary in {"claude", "openai"}:
            defend = get_provider("defend")
            defend_result = await defend.evaluate(text=text, session_id=session_id, modules=[])

            if defend_result.action == "block":
                # Hard block from defend — do not call LLM provider.
                return defend_result

            # Defend passed — run LLM provider for final decision.
            llm = get_provider(primary)
            if llm.supports_modules:
                modules = list(get_active_modules().values())

            try:
                return await llm.evaluate(text=text, session_id=session_id, modules=modules)
            except ProviderUnavailableError:
                # LLM call failed — fall back to defend's pass result.
                return defend_result

        # Single-provider mode.
        provider = get_provider(primary)
        if provider.supports_modules:
            modules = list(get_active_modules().values())

        return await provider.evaluate(text=text, session_id=session_id, modules=modules)


_orchestrator: Optional[ProviderOrchestrator] = None


def get_provider_orchestrator() -> ProviderOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ProviderOrchestrator()
    return _orchestrator


