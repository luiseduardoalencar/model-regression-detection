"""The validate-golden command: what it prints and its exit code."""

import json
from pathlib import Path
from typing import Any

from regression_detector.golden.cli import main
from tests.factories import case_data, edition_data, full_matrix_cases


def write_edition(folder: Path, data: dict[str, Any]) -> str:
    path = folder / "edition.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def test_complete_edition_exits_zero(tmp_path, capsys):
    path = write_edition(tmp_path, edition_data(full_matrix_cases()))
    assert main([path]) == 0
    assert "0 flags, 0 blocking" in capsys.readouterr().out


def test_matrix_gap_exits_one(tmp_path, capsys):
    path = write_edition(tmp_path, edition_data([case_data()]))
    assert main([path]) == 1
    assert "matrix_gap" in capsys.readouterr().out


def test_schema_error_exits_one(tmp_path, capsys):
    path = write_edition(tmp_path, edition_data([case_data(expected_category="shipping")]))
    assert main([path]) == 1
    assert "expected_category" in capsys.readouterr().out
