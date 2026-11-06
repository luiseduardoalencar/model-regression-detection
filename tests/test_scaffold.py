"""Scaffold checks: the package imports and the golden draft has the expected header."""

import json
from pathlib import Path

import regression_detector

ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = {
    "delivery",
    "cancellation",
    "return_refund",
    "payment",
    "account",
    "technical",
    "general",
}


def test_package_imports() -> None:
    assert regression_detector.__version__ == "0.1.0"


def test_golden_draft_header() -> None:
    draft = json.loads((ROOT / "golden" / "drafts" / "edition-1.json").read_text("utf-8"))
    assert draft["edition"] == 1
    assert draft["status"] == "draft"
    assert set(draft["categories"]) == CATEGORIES
    assert isinstance(draft["cases"], list)
