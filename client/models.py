from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class GuardResult(BaseModel):
    action: Literal["pass", "flag", "block", "retry_suggested"]
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

    def error_response(self, message: Optional[str] = None) -> dict:
        return {
            "error": "request_blocked",
            "message": message or "This request was blocked by the content guardrail.",
            "reason": self.reason,
            "modules_triggered": self.modules_triggered,
        }

