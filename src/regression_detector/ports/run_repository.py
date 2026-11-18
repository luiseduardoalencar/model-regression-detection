"""Port to the local run history (planning §6, decision 5.2): save and load finished runs."""

from typing import Protocol

from regression_detector.eval.records import RunRecord


class RunNotFoundError(LookupError):
    """No run with this id is stored."""


class RunAlreadySavedError(ValueError):
    """A run with this id is already stored; runs are never overwritten."""


class RunRepository(Protocol):
    """Anything that can store finished runs with their per-case results."""

    def save(self, record: RunRecord) -> None: ...

    def load(self, run_id: str) -> RunRecord: ...
