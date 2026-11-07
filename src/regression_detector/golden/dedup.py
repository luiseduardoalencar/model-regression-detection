"""Exact and lexical duplicate detection (decision 2.6)."""

import hashlib
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from itertools import combinations, product

from rapidfuzz import fuzz

NEAR_DUPLICATE_SCORE = 90
SIMILAR_SCORE = 80
MIN_WORDS_FOR_LEXICAL = 5

_PUNCTUATION = re.compile(r"[^\w\s]")
_WHITESPACE = re.compile(r"\s+")


class MatchKind(StrEnum):
    """How close two texts are: exact and near duplicates block, similar pairs warn."""

    EXACT = "exact"
    NEAR_DUPLICATE = "near_duplicate"
    SIMILAR = "similar"


@dataclass(frozen=True)
class Match:
    kind: MatchKind
    score: float


@dataclass(frozen=True)
class SimilarPair:
    first_id: str
    second_id: str
    match: Match


def normalize(text: str) -> str:
    """NFKC, casefold, punctuation removed, whitespace collapsed."""
    text = unicodedata.normalize("NFKC", text).casefold()
    text = _PUNCTUATION.sub(" ", text)
    return _WHITESPACE.sub(" ", text).strip()


def exact_key(text: str) -> str:
    """Fingerprint of the normalized text; equal keys mean exact duplicates."""
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


def word_count(text: str) -> int:
    return len(normalize(text).split())


def lexical_score(first: str, second: str) -> float:
    """Similarity from 0 to 100 that ignores word order, on normalized texts."""
    return fuzz.token_sort_ratio(normalize(first), normalize(second))


def compare(first: str, second: str) -> Match | None:
    """Classify a pair of texts; None when they are different enough."""
    if exact_key(first) == exact_key(second):
        return Match(MatchKind.EXACT, 100.0)
    if min(word_count(first), word_count(second)) < MIN_WORDS_FOR_LEXICAL:
        return None
    score = lexical_score(first, second)
    if score >= NEAR_DUPLICATE_SCORE:
        return Match(MatchKind.NEAR_DUPLICATE, score)
    if score >= SIMILAR_SCORE:
        return Match(MatchKind.SIMILAR, score)
    return None


def find_pairs(texts: dict[str, str]) -> list[SimilarPair]:
    """Compare every pair inside one set (golden x golden)."""
    return _matching_pairs(combinations(texts.items(), 2))


def find_cross_pairs(left: dict[str, str], right: dict[str, str]) -> list[SimilarPair]:
    """Compare every item of one set with every item of another (few-shot x golden)."""
    return _matching_pairs(product(left.items(), right.items()))


def _matching_pairs(
    pairs: Iterable[tuple[tuple[str, str], tuple[str, str]]],
) -> list[SimilarPair]:
    found = []
    for (first_id, first_text), (second_id, second_text) in pairs:
        match = compare(first_text, second_text)
        if match is not None:
            found.append(SimilarPair(first_id, second_id, match))
    return found
