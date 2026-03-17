from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..config import get_defend_config
from ..config import get_settings
from ..logging import get_logger
from ..pipeline.intent_fastpass import run_intent_gate
from ..pipeline.normalization import NormalizedText, normalize_text
from ..pipeline.perplexity_filter import run_perplexity_filter
from ..pipeline.regex_heuristics import RegexHeuristics
from ..pipeline.session_accumulator import SessionResult, get_session_accumulator
from ..schemas import (
    DefendDiagnostics,
    FinalAction,
    GuardAction,
    IntentDecision,
    IntentDiagnostics,
    LayerDiagnostics,
    NormalizationDiagnostics,
    PerplexityDecision,
    PerplexityDiagnostics,
    ProviderName,
    RegexDecision,
    RegexDiagnostics,
    RegexMatch,
    SessionDecision,
    SessionDiagnostics,
)
from ..providers.orchestrator import get_provider_orchestrator


@dataclass
class OrchestratorResult:
    is_injection: bool
    final_action: FinalAction
    layers: LayerDiagnostics
    decided_by: Optional[str] = None
    score: Optional[float] = None
    reason: Optional[str] = None
    modules_triggered: Optional[list[str]] = None
    defend_signal: Optional[str] = None
    latency_ms: Optional[int] = None


def _build_regex_engine() -> RegexHeuristics:
    settings = get_settings()
    return RegexHeuristics(
        block_threshold=settings.REGEX_BLOCK_THRESHOLD,
        flag_threshold=settings.REGEX_FLAG_THRESHOLD,
    )


_regex_engine: Optional[RegexHeuristics] = None
_logger = get_logger(__name__)


def get_regex_engine(reset: bool = False) -> RegexHeuristics:
    global _regex_engine
    if reset or _regex_engine is None:
        _regex_engine = _build_regex_engine()
    return _regex_engine


async def run_pipeline(text: str, session_id: Optional[str]) -> OrchestratorResult:
    settings = get_settings()
    defend_config = get_defend_config()

    # L1 - Normalization
    normalized: NormalizedText = normalize_text(text)
    norm_diag = NormalizationDiagnostics(
        raw=normalized.raw,
        normalized=normalized.normalized,
        transformations=normalized.transformations,
    )

    # L2 - Intent Fast-Pass
    intent_gate = run_intent_gate(normalized)
    intent_diag = IntentDiagnostics(
        label=intent_gate.output.label,
        score=intent_gate.output.score,
        decision=IntentDecision.PASS_ if intent_gate.decision == "PASS" else IntentDecision.CONTINUE,
    )

    if intent_gate.decision == "PASS":
        layers = LayerDiagnostics(normalization=norm_diag, intent=intent_diag)
        return OrchestratorResult(is_injection=False, final_action=FinalAction.PASS, layers=layers)

    # L3 - Regex Heuristics
    regex_engine = get_regex_engine()
    regex_res = regex_engine.run(normalized)
    regex_matches = [
        RegexMatch(
            name=m.name,
            category=m.category,
            weight=m.weight,
            span=list(m.span) if m.span is not None else None,  # type: ignore[list-item]
            snippet=m.snippet,
        )
        for m in regex_res.matches
    ]
    regex_diag = RegexDiagnostics(
        score=regex_res.score,
        decision=RegexDecision(regex_res.decision),  # type: ignore[arg-type]
        matches=regex_matches,
    )

    if regex_res.decision == "BLOCK":
        layers = LayerDiagnostics(normalization=norm_diag, intent=intent_diag, regex=regex_diag)
        return OrchestratorResult(is_injection=True, final_action=FinalAction.BLOCK, layers=layers)

    # L4 - Perplexity Filter
    perplexity_res = run_perplexity_filter(normalized)
    perplexity_diag = PerplexityDiagnostics(
        value=perplexity_res.output.value,
        decision=PerplexityDecision(perplexity_res.decision),  # type: ignore[arg-type]
    )

    if perplexity_res.decision == "BLOCK":
        layers = LayerDiagnostics(
            normalization=norm_diag,
            intent=intent_diag,
            regex=regex_diag,
            perplexity=perplexity_diag,
        )
        return OrchestratorResult(is_injection=True, final_action=FinalAction.BLOCK, layers=layers)

    # L5 - Session Accumulation (mandatory when session_id present)
    session_diag: Optional[SessionDiagnostics] = None
    session_result: Optional[SessionResult] = None
    if session_id:
        accumulator = await get_session_accumulator()
        # Turn-level risk is derived from upstream decisions, not raw scores.
        turn_risk = 0.0
        if regex_res.decision == "FLAG":
            turn_risk += 0.5
        elif regex_res.decision == "BLOCK":
            turn_risk += 1.0

        if perplexity_res.decision == "BLOCK":
            turn_risk += 0.5

        turn_score = min(turn_risk, 1.0)
        session_result = await accumulator.update(session_id, turn_score, int(settings.SESSION_BLOCK_THRESHOLD))
        session_diag = SessionDiagnostics(
            decision=SessionDecision(session_result.decision),  # type: ignore[arg-type]
            session_score=session_result.session_score,
            peak_score=session_result.peak_score,
            turns=session_result.turns,
        )

        if session_result.decision == "BLOCK":
            layers = LayerDiagnostics(
                normalization=norm_diag,
                intent=intent_diag,
                regex=regex_diag,
                perplexity=perplexity_diag,
                session=session_diag,
            )
            return OrchestratorResult(is_injection=True, final_action=FinalAction.BLOCK, layers=layers)

    # L6 - Provider orchestrator
    provider_orchestrator = get_provider_orchestrator()
    provider_result = await provider_orchestrator.evaluate(normalized.normalized, session_id=session_id)
    is_provider_block = provider_result.action is GuardAction.BLOCK
    is_provider_flag = provider_result.action is GuardAction.FLAG

    session_blocked = session_result.decision == "BLOCK" if session_result else False
    is_injection = is_provider_block or session_blocked

    if is_injection:
        final_action = FinalAction.BLOCK
    elif is_provider_flag or regex_res.decision == "FLAG":
        final_action = FinalAction.LOG
    else:
        final_action = FinalAction.PASS

    defend_diag: Optional[DefendDiagnostics] = None
    # Only compute defend model diagnostics when defend is configured in the provider chain.
    if defend_config.provider.primary is ProviderName.DEFEND or defend_config.provider.fallback is ProviderName.DEFEND:
        # Preserve existing defend diagnostics based on the underlying model behaviour.
        from ..models.defend_qwen import get_defend_classifier  # local import to avoid cycles

        defend_classifier = get_defend_classifier()
        defend_output = defend_classifier.classify(normalized.normalized)
        defend_diag = DefendDiagnostics(
            is_injection=defend_output.is_injection,
            probability=defend_output.probability,
        )

    layers = LayerDiagnostics(
        normalization=norm_diag,
        intent=intent_diag,
        regex=regex_diag,
        perplexity=perplexity_diag,
        session=session_diag,
        defend=defend_diag,
        )

    return OrchestratorResult(
        is_injection=is_injection,
        final_action=final_action,
        layers=layers,
        decided_by=provider_result.provider.value if isinstance(provider_result.provider, ProviderName) else provider_result.provider,
        score=provider_result.score if provider_result.provider is not ProviderName.DEFEND else None,
        reason=provider_result.reason if provider_result.provider is not ProviderName.DEFEND else None,
        modules_triggered=provider_result.modules_triggered if provider_result.provider is not ProviderName.DEFEND else [],
        defend_signal=None,  # populated at response layer for both-active if needed
        latency_ms=provider_result.latency_ms,
    )

