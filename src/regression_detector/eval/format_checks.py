"""Code checks on a generated summary (decisions 3.2 and 3.4, summary guide rules 1, 5 and 9).

Four checks, all deterministic, so `format_pass` may block a PR:
one sentence, starts with "Cliente", no category label, Portuguese.
"""

import re
from dataclasses import dataclass
from enum import StrEnum
from functools import cache

from lingua import Language, LanguageDetector, LanguageDetectorBuilder

from regression_detector.feature.models import Category


class FormatCheckName(StrEnum):
    ONE_SENTENCE = "one_sentence"
    STARTS_WITH_CLIENTE = "starts_with_cliente"
    NO_CATEGORY_LABEL = "no_category_label"
    PORTUGUESE = "portuguese"


@dataclass(frozen=True)
class FormatCheck:
    """One check: whether it passed and, when it did not, why."""

    name: FormatCheckName
    passed: bool
    detail: str | None = None


@dataclass(frozen=True)
class FormatResult:
    """The four checks of one summary; `passed` only when all of them pass."""

    checks: tuple[FormatCheck, ...]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def failures(self) -> tuple[FormatCheck, ...]:
        return tuple(check for check in self.checks if not check.passed)


# Abbreviations whose final period does not end a sentence (lowercase, without the period).
ABBREVIATIONS = frozenset(
    {"sr", "sra", "srta", "dr", "dra", "prof", "profa", "nº", "n°", "núm", "tel", "av", "ref"}
)

# A sentence ends at . ! ? or … (optionally followed by a closing quote or bracket) when
# whitespace and more text come after it. "1.200" and "joao@email.com" have no space
# after the period, so they never end a sentence.
_SENTENCE_END = re.compile(r"(\S*?)[.!?…]+[\"'”’)\]]*\s+(?=\S)")

_CATEGORY_LABEL = re.compile(
    r"\b("
    + "|".join(sorted({value for c in Category for value in (c.value, c.value.replace("_", " "))}))
    + r")\b",
    re.IGNORECASE,
)

_STARTS_WITH_CLIENTE = re.compile(r"^Cliente\b")

# Compared only among the languages a wrong summary could plausibly be written in.
_DETECTED_LANGUAGES = (Language.PORTUGUESE, Language.ENGLISH, Language.SPANISH)


@cache
def _language_detector() -> LanguageDetector:
    """Built once per process: loading the language models is the slow part."""
    return LanguageDetectorBuilder.from_languages(*_DETECTED_LANGUAGES).build()


def check_one_sentence(summary: str) -> FormatCheck:
    """One sentence: no line break and no sentence end before the last one."""
    text = summary.strip()
    if not text:
        return FormatCheck(FormatCheckName.ONE_SENTENCE, False, "empty summary")
    if "\n" in text:
        return FormatCheck(FormatCheckName.ONE_SENTENCE, False, "contains a line break")
    breaks = [
        match
        for match in _SENTENCE_END.finditer(text)
        if match.group(1).lower() not in ABBREVIATIONS
    ]
    if breaks:
        return FormatCheck(FormatCheckName.ONE_SENTENCE, False, f"{len(breaks) + 1} sentences")
    return FormatCheck(FormatCheckName.ONE_SENTENCE, True)


def check_starts_with_cliente(summary: str, *, out_of_scope: bool) -> FormatCheck:
    """Starts with "Cliente", except out-of-scope emails (summary guide rule 9)."""
    if out_of_scope:
        return FormatCheck(FormatCheckName.STARTS_WITH_CLIENTE, True, "not applied: out_of_scope")
    if _STARTS_WITH_CLIENTE.match(summary.strip()):
        return FormatCheck(FormatCheckName.STARTS_WITH_CLIENTE, True)
    start = " ".join(summary.split()[:2])
    return FormatCheck(FormatCheckName.STARTS_WITH_CLIENTE, False, f"starts with {start!r}")


def check_no_category_label(summary: str) -> FormatCheck:
    """No category name in the summary (summary guide rule 5)."""
    found = sorted({match.group(1).lower() for match in _CATEGORY_LABEL.finditer(summary)})
    if found:
        return FormatCheck(FormatCheckName.NO_CATEGORY_LABEL, False, f"names {', '.join(found)}")
    return FormatCheck(FormatCheckName.NO_CATEGORY_LABEL, True)


def check_portuguese(summary: str) -> FormatCheck:
    """Detected as Portuguese among Portuguese, English and Spanish (summary guide rule 10)."""
    detected = _language_detector().detect_language_of(summary)
    if detected == Language.PORTUGUESE:
        return FormatCheck(FormatCheckName.PORTUGUESE, True)
    name = detected.name.lower() if detected is not None else "undetermined"
    return FormatCheck(FormatCheckName.PORTUGUESE, False, f"detected {name}")


def check_format(summary: str, *, out_of_scope: bool) -> FormatResult:
    """All four checks, in a fixed order."""
    return FormatResult(
        checks=(
            check_one_sentence(summary),
            check_starts_with_cliente(summary, out_of_scope=out_of_scope),
            check_no_category_label(summary),
            check_portuguese(summary),
        )
    )
