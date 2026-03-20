from __future__ import annotations

from typing import Any, Dict

from ..base import BaseModule
from ..fragments import build_system_prompt


class GuardModule(BaseModule):
    name = "sensitive_topics"
    description = "sensitive_topics guard module"
    direction = "input"

    def __init__(self, **kwargs: Any) -> None:
        self._cfg: Dict[str, Any] = dict(kwargs)

    def system_prompt(self) -> str:
        return build_system_prompt(self.name, self._cfg)

