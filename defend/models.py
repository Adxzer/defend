from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class GuardResult(BaseModel):
    """
    Result returned by the Defend guard endpoints.

    Mirrors the server's `GuardResult` shape returned from:
    - POST /v1/guard/input
    - POST /v1/guard/output
    """

    action: Literal["pass", "flag", "block"]
    session_id: str
    decided_by: str
    direction: Literal["input", "output"]
    score: Optional[float] = None
    reason: Optional[str] = None
    modules_triggered: List[str] = Field(default_factory=list)
    context: Literal["session", "none"] = "none"
    latency_ms: int = 0

    @property
    def blocked(self) -> bool:
        return self.action == "block"

    def error_response(self, message: Optional[str] = None) -> Dict[str, Any]:
        """
        Return a JSON-serializable error payload suitable for returning from web frameworks.
        """

        return {
            "error": "request_blocked",
            "message": message or "This request was blocked by the content guardrail.",
            "reason": self.reason,
            "modules_triggered": self.modules_triggered,
        }


class Session(BaseModel):
    """
    Session state returned by GET /v1/sessions/{session_id}.
    """

    session_id: str
    turns: int
    risk_score: float
    peak_score: float
    history: List[Dict[str, Any]] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """
    Response returned by GET /v1/health.
    """

    status: Literal["ok"]
    providers: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

