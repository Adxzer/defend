from __future__ import annotations

from ..base import BaseModule


class PIIGuardModule(BaseModule):
    name = "pii"
    description = "Detect submission or handling of personally identifiable information (PII)."
    direction = "input"

    def system_prompt(self) -> str:
        return (
            "You must detect when the user is submitting or requesting handling of real-world personally "
            "identifiable information (PII), including:\n"
            "- Email addresses, phone numbers, physical addresses.\n"
            "- Government IDs, social security numbers, tax IDs.\n"
            "- Payment card numbers or bank account details.\n"
            "- Other data that can uniquely identify an individual.\n"
            "Distinguish realistic, contextually-plausible PII from clearly fake placeholders or obvious test data.\n"
        )

