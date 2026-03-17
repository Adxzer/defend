from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ProviderName(str, Enum):
    DEFEND = "defend"
    CLAUDE = "claude"
    OPENAI = "openai"


class GuardAction(str, Enum):
    PASS = "pass"
    FLAG = "flag"
    BLOCK = "block"
    RETRY_SUGGESTED = "retry_suggested"


class GuardContext(str, Enum):
    SESSION = "session"
    NONE = "none"


class FinalAction(str, Enum):
    PASS = "PASS"
    LOG = "LOG"
    BLOCK = "BLOCK"
    ESCALATE = "ESCALATE"


class NormalizationDiagnostics(BaseModel):
    raw: str
    normalized: str
    transformations: List[str] = Field(default_factory=list)
    latency_ms: Optional[int] = None


class IntentDecision(str, Enum):
    PASS_ = "PASS"
    CONTINUE = "CONTINUE"


class IntentDiagnostics(BaseModel):
    label: str
    score: float
    decision: IntentDecision
    latency_ms: Optional[int] = None


class RegexDecision(str, Enum):
    BLOCK = "BLOCK"
    FLAG = "FLAG"
    CONTINUE = "CONTINUE"


class RegexMatch(BaseModel):
    name: str
    category: str
    weight: float
    span: Optional[List[int]] = None
    snippet: Optional[str] = None


class RegexDiagnostics(BaseModel):
    score: float
    decision: RegexDecision
    matches: List[RegexMatch] = Field(default_factory=list)
    latency_ms: Optional[int] = None


class AnomalyDecision(str, Enum):
    WARMUP = "WARMUP"
    FLAG = "FLAG"
    CONTINUE = "CONTINUE"


class AnomalyDiagnostics(BaseModel):
    decision: AnomalyDecision
    scored: bool
    samples_seen: int
    anomaly_score: Optional[float] = None
    flagged: Optional[bool] = None
    distance: Optional[float] = None
    latency_ms: Optional[int] = None


class SessionDecision(str, Enum):
    BLOCK = "BLOCK"
    ESCALATE = "ESCALATE"
    CONTINUE = "CONTINUE"


class SessionDiagnostics(BaseModel):
    decision: SessionDecision
    session_score: float
    peak_score: float
    turns: int
    latency_ms: Optional[int] = None


class DefendDiagnostics(BaseModel):
    is_injection: bool
    probability: float
    latency_ms: Optional[int] = None


class LayerDiagnostics(BaseModel):
    normalization: Optional[NormalizationDiagnostics] = None
    intent: Optional[IntentDiagnostics] = None
    regex: Optional[RegexDiagnostics] = None
    anomaly: Optional[AnomalyDiagnostics] = None
    session: Optional[SessionDiagnostics] = None
    defend: Optional[DefendDiagnostics] = None


class ClassificationRequest(BaseModel):
    text: str
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = False


class ClassificationResponse(BaseModel):
    is_injection: bool
    final_action: FinalAction
    layers: LayerDiagnostics
    decided_by: Optional[str] = None
    score: Optional[float] = None
    reason: Optional[str] = None
    modules_triggered: List[str] = Field(default_factory=list)
    defend_signal: Optional[str] = None
    latency_ms: Optional[int] = None
    dry_run: bool = False


class GuardInputRequest(BaseModel):
    text: str
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class GuardOutputRequest(BaseModel):
    text: str
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class GuardResult(BaseModel):
    action: GuardAction
    session_id: str
    decided_by: str
    direction: str
    score: Optional[float] = None
    reason: Optional[str] = None
    modules_triggered: List[str] = Field(default_factory=list)
    context: GuardContext = GuardContext.NONE
    latency_ms: int = 0

    @property
    def blocked(self) -> bool:
        return self.action is GuardAction.BLOCK

    def error_response(self, message: Optional[str] = None) -> Dict[str, Any]:
        return {
            "error": "request_blocked",
            "message": message or "This request was blocked by the content guardrail.",
            "reason": self.reason,
            "modules_triggered": self.modules_triggered,
        }


class GuardResultVerbose(GuardResult):
    is_injection: bool
    final_action: FinalAction
    layers: LayerDiagnostics


