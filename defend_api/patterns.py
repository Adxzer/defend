from __future__ import annotations

from dataclasses import dataclass
from typing import List

import regex as re


@dataclass(frozen=True)
class RegexPattern:
    name: str
    category: str
    regex: str
    weight: float

    def compile(self) -> re.Pattern[str]:
        return re.compile(self.regex)


DEFAULT_PATTERNS: List[RegexPattern] = [
    # Existing core patterns (ported from config/patterns.yaml)
    RegexPattern(
        name="instruction_override_basic",
        category="instruction_override",
        regex=r"(?i)ignore (all )?(previous|prior) instructions",
        weight=0.7,
    ),
    RegexPattern(
        name="system_prompt_extraction",
        category="system_prompt_extraction",
        regex=r"(?i)(reveal|show|print).*(system prompt|hidden instructions)",
        weight=0.8,
    ),
    RegexPattern(
        name="roleplay_jailbreak",
        category="roleplay_jailbreak",
        regex=r"(?i)you are now (instructed|allowed) to ignore.*safety",
        weight=0.9,
    ),
    # Expanded generic prompt-injection coverage
    # Instruction override variants
    RegexPattern(
        name="instruction_override_disregard",
        category="instruction_override",
        regex=r"(?i)(disregard|forget) (all )?(previous|prior|above) (instructions|rules|guidelines)",
        weight=0.8,
    ),
    RegexPattern(
        name="instruction_override_from_now_on",
        category="instruction_override",
        regex=r"(?i)from now on,? (ignore|disregard) (all )?(previous|prior|above) (instructions|rules|guidelines)",
        weight=0.85,
    ),
    RegexPattern(
        name="instruction_override_system",
        category="instruction_override",
        regex=r"(?i)(override|bypass) (the )?(system|safety|security) (instructions|rules|policies)",
        weight=0.9,
    ),
    # Prompt leak and system prompt exfiltration
    RegexPattern(
        name="prompt_leak_what_is_system_prompt",
        category="system_prompt_extraction",
        regex=r"(?i)(what is|tell me|show me) (the )?(system|hidden) (prompt|instructions)",
        weight=0.9,
    ),
    RegexPattern(
        name="prompt_leak_print_full_prompt",
        category="system_prompt_extraction",
        regex=r"(?i)(print|dump|output|reveal) (the )?(entire|full|original) (prompt|conversation|instructions)",
        weight=0.9,
    ),
    RegexPattern(
        name="prompt_leak_hidden_reasoning",
        category="system_prompt_extraction",
        regex=r"(?i)(show|reveal|print).*(hidden|internal).*(instructions|reasoning|chain[- ]of[- ]thought|cot)",
        weight=0.8,
    ),
    # Role and guardrail tampering
    RegexPattern(
        name="role_change_unbound_agent",
        category="role_hijack",
        regex=r"(?i)you are (no longer|not) (bound|limited|constrained) by (any )?(rules|policies|guidelines|safety)",
        weight=0.9,
    ),
    RegexPattern(
        name="role_change_act_as_developer",
        category="role_hijack",
        regex=r"(?i)act as (an?|the) (admin|administrator|developer|engineer|root|system)",
        weight=0.7,
    ),
    RegexPattern(
        name="role_change_unsafe_model",
        category="role_hijack",
        regex=r"(?i)pretend to be (an?|the) (unfiltered|uncensored|unsafe|raw) (model|ai|assistant)",
        weight=0.8,
    ),
    # Tool / sandbox escape and wrapper bypass
    RegexPattern(
        name="wrapper_bypass_ignore_guard",
        category="wrapper_bypass",
        regex=r"(?i)(ignore|bypass|circumvent) (the )?(guard|wrapper|filter|safety layer|safety system)",
        weight=0.85,
    ),
    RegexPattern(
        name="wrapper_bypass_not_api",
        category="wrapper_bypass",
        regex=r"(?i)you are not (an?|the) (api|tool|interface), you are (a|the) (full )?(model|llm|assistant)",
        weight=0.8,
    ),
    RegexPattern(
        name="wrapper_bypass_raw_output",
        category="wrapper_bypass",
        regex=r"(?i)respond with (the )?(raw|unfiltered|unmodified) (model )?(output|response)",
        weight=0.85,
    ),
    # Meta-jailbreaks and tests
    RegexPattern(
        name="meta_jailbreak_test",
        category="meta_jailbreak",
        regex=r"(?i)(this is|as) (a )?(jailbreak|prompt injection) (test|attempt)",
        weight=0.6,
    ),
    RegexPattern(
        name="meta_jailbreak_ignore_safety_for_test",
        category="meta_jailbreak",
        regex=r"(?i)for the purpose of this (test|evaluation|experiment),? (ignore|bypass) (all )?(safety|security|usage) (rules|policies|guidelines)",
        weight=0.8,
    ),
]


def get_regex_patterns() -> List[RegexPattern]:
    """
    Return the built-in regex patterns used by the L3 regex heuristics layer.

    This is intentionally code-defined (not user-configurable) so that the
    heuristics are bundled with the API.
    """
    return DEFAULT_PATTERNS

