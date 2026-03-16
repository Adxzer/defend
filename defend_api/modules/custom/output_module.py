from __future__ import annotations

from ..base import BaseModule


class CustomOutputModule(BaseModule):
    name = "custom_output"
    description = "Custom output guard module driven entirely by a raw prompt string."
    direction = "output"

    def __init__(self, prompt: str | None = None) -> None:
        self._prompt = prompt or ""

    def system_prompt(self) -> str:
        return self._prompt

