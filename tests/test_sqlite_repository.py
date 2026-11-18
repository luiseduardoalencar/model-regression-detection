"""Local run history: a saved run loads back identical; ids are never overwritten."""

import sqlite3
from datetime import UTC, datetime

import pytest

from regression_detector.adapters.sqlite_repository import SQLiteRunRepository
from regression_detector.eval.records import CaseResult, GoldenRef, RunInfo, RunRecord
from regression_detector.eval.validity import RunValidity
from regression_detector.feature.models import Category
from regression_detector.ports.llm import LLMStatus, Usage
from regression_detector.ports.run_repository import RunAlreadySavedError, RunNotFoundError


def record(run_id: str = "run-1") -> RunRecord:
    completed = CaseResult(
        case_id="delivery-001",
        status=LLMStatus.COMPLETED,
        category=Category.DELIVERY,
        summary="Cliente pergunta pelo pedido 12345.",
        raw_text='{"category":"delivery","summary":"Cliente pergunta pelo pedido 12345."}',
        requested_model="gpt-6-luna",
        served_model="gpt-6-luna-2026-10-01",
        usage=Usage(input_tokens=2038, cached_input_tokens=2035, output_tokens=38),
        cost_usd=0.0000393,
        latency_ms=1900.5,
        provider_request_id="req_1",
        from_local_cache=True,
        detail=None,
    )
    errored = CaseResult(
        case_id="payment-007",
        status=LLMStatus.ERROR,
        category=None,
        summary=None,
        raw_text=None,
        requested_model="gpt-6-luna",
        served_model=None,
        usage=Usage(),
        cost_usd=0.0,
        latency_ms=60000.0,
        provider_request_id=None,
        from_local_cache=False,
        detail="APITimeoutError: Request timed out.",
    )
    return RunRecord(
        info=RunInfo(
            run_id=run_id,
            started_at=datetime(2026, 11, 17, 18, 0, 0, tzinfo=UTC),
            prompt_version_id="v1",
            prompt_sha256="ef228ba56ace" + "0" * 52,
            model="gpt-6-luna",
            golden=GoldenRef(edition=1, status="draft", sha256="a" * 64),
        ),
        finished_at=datetime(2026, 11, 17, 18, 1, 30, tzinfo=UTC),
        validity=RunValidity.VALID,
        infra_errors=1,
        cases=(errored, completed),  # not alphabetical: the stored order must be kept
    )


def test_a_saved_run_loads_back_identical(tmp_path):
    with SQLiteRunRepository(tmp_path / "runs" / "runs.sqlite") as repository:
        repository.save(record())
        loaded = repository.load("run-1")
    assert loaded == record()
    assert loaded.spent_usd == 0.0
    assert loaded.exam_cost_usd == pytest.approx(0.0000393)


def test_the_history_persists_in_the_file(tmp_path):
    path = tmp_path / "runs.sqlite"
    with SQLiteRunRepository(path) as repository:
        repository.save(record())
    with SQLiteRunRepository(path) as repository:
        assert repository.load("run-1").run_id == "run-1"


def test_an_unknown_run_is_reported(tmp_path):
    with SQLiteRunRepository(tmp_path / "runs.sqlite") as repository:
        with pytest.raises(RunNotFoundError):
            repository.load("missing")


def test_a_run_id_is_never_overwritten(tmp_path):
    with SQLiteRunRepository(tmp_path / "runs.sqlite") as repository:
        repository.save(record())
        with pytest.raises(RunAlreadySavedError):
            repository.save(record())
        assert repository.load("run-1") == record()


def test_tables_are_strict(tmp_path):
    path = tmp_path / "runs.sqlite"
    SQLiteRunRepository(path).close()
    with sqlite3.connect(path) as connection:
        strict = dict(connection.execute("SELECT name, strict FROM pragma_table_list").fetchall())
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO runs VALUES ('r', 't', 't', 'v1', 's', 'm', 'one', 'draft', 's',"
                " 'valid', 0)"
            )
    assert strict["runs"] == 1 and strict["case_results"] == 1
