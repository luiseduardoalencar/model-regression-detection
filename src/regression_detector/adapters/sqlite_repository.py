"""Local run history in SQLite (decision 5.2): `runs/runs.sqlite`, gitignored, temporary in CI."""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Self

from regression_detector.adapters.sqlite_support import connect
from regression_detector.eval.records import CaseResult, GoldenRef, RunInfo, RunRecord
from regression_detector.eval.validity import RunValidity
from regression_detector.feature.models import Category
from regression_detector.ports.llm import LLMStatus, Usage
from regression_detector.ports.run_repository import RunAlreadySavedError, RunNotFoundError

DEFAULT_RUNS_PATH = Path("runs/runs.sqlite")

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    prompt_version_id TEXT NOT NULL,
    prompt_sha256 TEXT NOT NULL,
    model TEXT NOT NULL,
    golden_edition INTEGER NOT NULL,
    golden_status TEXT NOT NULL,
    golden_sha256 TEXT NOT NULL,
    validity TEXT NOT NULL,
    infra_errors INTEGER NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS case_results (
    run_id TEXT NOT NULL REFERENCES runs (run_id),
    position INTEGER NOT NULL,
    case_id TEXT NOT NULL,
    status TEXT NOT NULL,
    category TEXT,
    summary TEXT,
    raw_text TEXT,
    requested_model TEXT NOT NULL,
    served_model TEXT,
    input_tokens INTEGER NOT NULL,
    cached_input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    reasoning_tokens INTEGER NOT NULL,
    cost_usd REAL NOT NULL,
    latency_ms REAL NOT NULL,
    provider_request_id TEXT,
    from_local_cache INTEGER NOT NULL CHECK (from_local_cache IN (0, 1)),
    detail TEXT,
    PRIMARY KEY (run_id, case_id)
) STRICT;
"""

CASE_COLUMNS = (
    "position, case_id, status, category, summary, raw_text, requested_model, served_model,"
    " input_tokens, cached_input_tokens, output_tokens, reasoning_tokens, cost_usd, latency_ms,"
    " provider_request_id, from_local_cache, detail"
)


class SQLiteRunRepository:
    """`RunRepository` over a local SQLite file with STRICT tables."""

    def __init__(self, path: Path = DEFAULT_RUNS_PATH) -> None:
        self._connection = connect(path)
        self._connection.row_factory = sqlite3.Row
        with self._connection:
            self._connection.executescript(SCHEMA)

    def save(self, record: RunRecord) -> None:
        """Store the run and its cases in one transaction; an existing run id is refused."""
        info = record.info
        try:
            with self._connection:
                self._connection.execute(
                    "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        info.run_id,
                        info.started_at.isoformat(),
                        record.finished_at.isoformat(),
                        info.prompt_version_id,
                        info.prompt_sha256,
                        info.model,
                        info.golden.edition,
                        info.golden.status,
                        info.golden.sha256,
                        record.validity.value,
                        record.infra_errors,
                    ),
                )
                self._connection.executemany(
                    f"INSERT INTO case_results (run_id, {CASE_COLUMNS})"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        (info.run_id, position, *_case_row(case))
                        for position, case in enumerate(record.cases)
                    ],
                )
        except sqlite3.IntegrityError as error:
            raise RunAlreadySavedError(f"run {info.run_id} is already stored") from error

    def load(self, run_id: str) -> RunRecord:
        row = self._connection.execute(
            "SELECT started_at, finished_at, prompt_version_id, prompt_sha256, model,"
            " golden_edition, golden_status, golden_sha256, validity, infra_errors"
            " FROM runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            raise RunNotFoundError(f"run {run_id} is not stored")
        cases = self._connection.execute(
            f"SELECT {CASE_COLUMNS} FROM case_results WHERE run_id = ? ORDER BY position",
            (run_id,),
        ).fetchall()
        return RunRecord(
            info=RunInfo(
                run_id=run_id,
                started_at=datetime.fromisoformat(row["started_at"]),
                prompt_version_id=row["prompt_version_id"],
                prompt_sha256=row["prompt_sha256"],
                model=row["model"],
                golden=GoldenRef(
                    edition=row["golden_edition"],
                    status=row["golden_status"],
                    sha256=row["golden_sha256"],
                ),
            ),
            finished_at=datetime.fromisoformat(row["finished_at"]),
            validity=RunValidity(row["validity"]),
            infra_errors=row["infra_errors"],
            cases=tuple(_case_from_row(case) for case in cases),
        )

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def _case_row(case: CaseResult) -> tuple[object, ...]:
    usage = case.usage
    return (
        case.case_id,
        case.status.value,
        case.category.value if case.category is not None else None,
        case.summary,
        case.raw_text,
        case.requested_model,
        case.served_model,
        usage.input_tokens,
        usage.cached_input_tokens,
        usage.output_tokens,
        usage.reasoning_tokens,
        case.cost_usd,
        case.latency_ms,
        case.provider_request_id,
        int(case.from_local_cache),
        case.detail,
    )


def _case_from_row(row: sqlite3.Row) -> CaseResult:
    category = row["category"]
    return CaseResult(
        case_id=row["case_id"],
        status=LLMStatus(row["status"]),
        category=Category(category) if category is not None else None,
        summary=row["summary"],
        raw_text=row["raw_text"],
        requested_model=row["requested_model"],
        served_model=row["served_model"],
        usage=Usage(
            input_tokens=row["input_tokens"],
            cached_input_tokens=row["cached_input_tokens"],
            output_tokens=row["output_tokens"],
            reasoning_tokens=row["reasoning_tokens"],
        ),
        cost_usd=row["cost_usd"],
        latency_ms=row["latency_ms"],
        provider_request_id=row["provider_request_id"],
        from_local_cache=bool(row["from_local_cache"]),
        detail=row["detail"],
    )
