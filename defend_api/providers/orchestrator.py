from __future__ import annotations

from typing import Optional

from ..config import get_defend_config, get_settings
from ..modules import build_modules_from_specs
from ..schemas import GuardAction, ProviderName
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
        if primary in {ProviderName.CLAUDE, ProviderName.OPENAI}:
            configured = build_modules_from_specs(self._config.modules or [])
            # Core provider-layer modules are input-oriented.
            modules = [m for m in configured if m.direction in ("input", "both")]

        # Both-active mode: defend as gate in front of LLM provider.
        if fallback is ProviderName.DEFEND and primary in {ProviderName.CLAUDE, ProviderName.OPENAI}:
            defend = get_provider(ProviderName.DEFEND)
            defend_result = await defend.evaluate(text=text, session_id=session_id, modules=[])

            if defend_result.action is GuardAction.BLOCK:
                # Hard block from defend - do not call LLM provider.
                return defend_result

            # Defend passed - run LLM provider for final decision.
            llm = get_provider(primary)
            try:
                return await llm.evaluate(text=text, session_id=session_id, modules=modules)
            except ProviderUnavailableError:
                # LLM call failed - fall back to defend's pass result.
                return defend_result

        # Single-provider mode.
        provider = get_provider(primary)
        return await provider.evaluate(text=text, session_id=session_id, modules=modules)


_orchestrator: Optional[ProviderOrchestrator] = None


def get_provider_orchestrator(reset: bool = False) -> ProviderOrchestrator:
    global _orchestrator
    if reset or _orchestrator is None:
        _orchestrator = ProviderOrchestrator()
    return _orchestrator


