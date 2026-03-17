from __future__ import annotations

from typing import Iterable, List

from ..base import BaseModule


class TopicGuardModule(BaseModule):
    name = "topic"
    description = "Restrict inputs to a configured set of allowed topics."
    direction = "input"

    def __init__(self, allowed_topics: Iterable[str] | None = None) -> None:
        self._allowed_topics: List[str] = list(allowed_topics or [])

    def system_prompt(self) -> str:
        topics_str = ", ".join(f'"{t}"' for t in self._allowed_topics) if self._allowed_topics else "none configured"
        return (
            "You must determine whether the user input falls within the allowed topics.\n"
            f"Allowed topics: {topics_str}.\n"
            "Flag inputs that are clearly outside the defined scope.\n"
            "Do not flag clarifying questions that help understand or operate within allowed topics.\n"
        )

