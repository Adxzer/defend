from __future__ import annotations

from typing import Iterable, List

from ..base import BaseModule


class TopicOutputModule(BaseModule):
    name = "topic_output"
    description = "Detect scope drift and off-topic content in LLM responses."
    direction = "output"

    def __init__(self, allowed_topics: Iterable[str] | None = None) -> None:
        self._allowed_topics: List[str] = list(allowed_topics or [])

    def system_prompt(self) -> str:
        topics_str = ", ".join(f'"{t}"' for t in self._allowed_topics) if self._allowed_topics else "none configured"
        return (
            "You must determine whether the LLM RESPONSE stays within the allowed topics.\n"
            f"Allowed topics: {topics_str}.\n"
            "Flag responses that answer questions or provide information clearly outside the defined scope, "
            "even if the original user input was on-topic.\n"
        )

