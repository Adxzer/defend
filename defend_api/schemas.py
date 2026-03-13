from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class FinalAction(str, Enum):
    PASS = "PASS"
    LOG = "LOG"
    BLOCK = "BLOCK"
    ESCALATE = "ESCALATE"


class NormalizationDiagnostics(BaseModel):
    raw: str
    normalized: str
    transformations: List[str] = Field(default_factory=list)


class IntentDecision(str, Enum):
    PASS_ = "PASS"
    CONTINUE = "CONTINUE"


class IntentDiagnostics(BaseModel):
    label: str
    score: float
    decision: IntentDecision


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


class PerplexityDecision(str, Enum):
    BLOCK = "BLOCK"
    FLAG = "FLAG"
    CONTINUE = "CONTINUE"


class PerplexityDiagnostics(BaseModel):
    value: float
    decision: PerplexityDecision


class SessionDecision(str, Enum):
    BLOCK = "BLOCK"
    ESCALATE = "ESCALATE"
    CONTINUE = "CONTINUE"


class SessionDiagnostics(BaseModel):
    decision: SessionDecision
    session_score: float
    peak_score: float
    turns: int


class DefendDiagnostics(BaseModel):
    is_injection: bool
    probability: float


class LayerDiagnostics(BaseModel):
    normalization: Optional[NormalizationDiagnostics] = None
    intent: Optional[IntentDiagnostics] = None
    regex: Optional[RegexDiagnostics] = None
    perplexity: Optional[PerplexityDiagnostics] = None
    session: Optional[SessionDiagnostics] = None
    defend: Optional[DefendDiagnostics] = None


class ClassificationRequest(BaseModel):
    text: str
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ClassificationResponse(BaseModel):
    is_injection: bool
    final_action: FinalAction
    layers: LayerDiagnostics

