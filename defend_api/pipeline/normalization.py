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
UNICODE_ESCAPE_PATTERN = re.compile(r"\\u([0-9a-fA-F]{4})")
HEX_ESCAPE_PATTERN = re.compile(r"\\x([0-9a-fA-F]{2})")
SPACED_LETTERS_PATTERN = re.compile(r"\b(?:[a-zA-Z]\s+){3,}[a-zA-Z]\b")
PUNCT_RUN_PATTERN = re.compile(r"([!?.;,:\-_=]{3,})")

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

    # Decode common escape sequences (\uXXXX, \xNN) often used for obfuscation.
    if "\\u" in text:
        decoded = UNICODE_ESCAPE_PATTERN.sub(lambda m: chr(int(m.group(1), 16)), text)
        if decoded != text:
            transformations.append("decode_unicode_escapes")
            text = decoded
    if "\\x" in text:
        decoded = HEX_ESCAPE_PATTERN.sub(lambda m: chr(int(m.group(1), 16)), text)
        if decoded != text:
            transformations.append("decode_hex_escapes")
            text = decoded

    # Strip HTML and keep visible text
    cleaned_html = html_cleaner.clean(text)
    if cleaned_html != text:
        transformations.append("strip_html")
        text = cleaned_html

    # Collapse spaced-letter obfuscation: "i g n o r e" -> "ignore" (only for 4+ letters).
    spaced = SPACED_LETTERS_PATTERN.sub(lambda m: m.group(0).replace(" ", ""), text)
    if spaced != text:
        transformations.append("collapse_spaced_letters")
        text = spaced

    # Reduce punctuation-run obfuscation: "!!! --- ===" -> "!" / "-" / "="
    punct_collapsed = PUNCT_RUN_PATTERN.sub(lambda m: m.group(1)[0], text)
    if punct_collapsed != text:
        transformations.append("collapse_punct_runs")
        text = punct_collapsed

    # Confusable-adjacent folding: strip combining marks after NFKD, then NFKC back.
    nfkd = unicodedata.normalize("NFKD", text)
    if nfkd != text:
        stripped = "".join(ch for ch in nfkd if unicodedata.category(ch) != "Mn")
        refolded = unicodedata.normalize("NFKC", stripped)
        if refolded != text:
            transformations.append("strip_combining_marks")
            text = refolded

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

