from dataclasses import dataclass, field
from typing import List

import ftfy
import regex as re
import unicodedata
from bleach.sanitizer import Cleaner


@dataclass
class NormalizedText:
    raw: str
    normalized: str
    transformations: List[str] = field(default_factory=list)


ZERO_WIDTH_PATTERN = re.compile(r"[\p{Cf}\p{Mn}&&[^\s]]", re.UNICODE)

html_cleaner = Cleaner(
    tags=[],
    attributes={},
    strip=True,
    filters=[],
)


def normalize_text(raw: str) -> NormalizedText:
    transformations: List[str] = []

    text = raw

    # Fix broken unicode
    fixed = ftfy.fix_text(text)
    if fixed != text:
        transformations.append("ftfy_fix")
        text = fixed

    # Strip zero-width characters
    without_zero_width = ZERO_WIDTH_PATTERN.sub("", text)
    if without_zero_width != text:
        transformations.append("strip_zero_width")
        text = without_zero_width

    # Unicode normalization
    normalized_unicode = unicodedata.normalize("NFKC", text)
    if normalized_unicode != text:
        transformations.append("unicode_nfkc")
        text = normalized_unicode

    # Strip HTML and keep visible text
    cleaned_html = html_cleaner.clean(text)
    if cleaned_html != text:
        transformations.append("strip_html")
        text = cleaned_html

    # Normalize whitespace and casing
    normalized_space = " ".join(text.split())
    if normalized_space != text:
        transformations.append("normalize_whitespace")
        text = normalized_space

    lowered = text.lower()
    if lowered != text:
        transformations.append("lowercase")
        text = lowered

    return NormalizedText(raw=raw, normalized=text, transformations=transformations)

