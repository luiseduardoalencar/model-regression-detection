"""The exam runner with a fake client: order, concurrency limit, validity, costs, abort, re-run."""

import asyncio
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import pytest

from regression_detector.adapters.caching_client import CachingLLMClient, SQLiteResponseCache
from regression_detector.adapters.noop_tracer import NoopTracer
from regression_detector.eval.records import GoldenRef
from regression_detector.eval.runner import load_golden, run_exam
from regression_detector.eval.validity import RunValidity
from regression_detector.feature.classifier import wrap_email
from regression_detector.feature.models import Category
from regression_detector.feature.prompt_config import PromptConfig
from regression_detector.ports.llm import LLMConfigurationError, LLMStatus
from regression_detector.pricing import PriceTable
from regression_detector.prompts.loader import LoadedPrompt
from tests.factories import edition_data, full_matrix_cases, make_edition, prompt_data
from tests.fakes import FAKE_SERVED_MODEL, FAKE_USAGE, FakeLLMClient, RecordingTracer

PRICES = PriceTable.model_validate(
    {
        "checked_on": "2026-11-07",
        "source": "test",
        "models": {"gpt-6-luna": {"input": 0.10, "cached_input": 0.01, "output": 0.50}},
    }
)
GOLDEN = GoldenRef(edition=1, status="draft", sha256="0" * 64)
EDITION = make_edition(full_matrix_cases())
EMAILS = [case.input_email for case in EDITION.cases]


def prompt(**overrides) -> LoadedPrompt:
    config = PromptConfig.model_validate(prompt_data(**overrides))
    return LoadedPrompt(config=config, path=Path("prompts/classifier/v1.yaml"), sha256="f" * 64)


def run(client, *, tracer=None, concurrency=10, **prompt_overrides):
    return asyncio.run(
        run_exam(
            edition=EDITION,
            golden=GOLDEN,
            prompt=prompt(**prompt_overrides),
            client=client,
            prices=PRICES,
            tracer=tracer or NoopTracer(),
            infra_error_limit_percent=2,
            concurrency=concurrency,
        )
    )


def test_every_case_runs_once_and_results_keep_golden_order():
    # Later cases answer first, so completion order is the reverse of golden order.
    delays = {email: 0.001 * (len(EMAILS) - i) for i, email in enumerate(EMAILS)}
    client = FakeLLMClient(delays=delays)
    record = run(client)
    assert [case.case_id for case in record.cases] == [case.id for case in EDITION.cases]
    assert sorted(map(wrap_email, EMAILS)) == sorted(r.user_input for r in client.requests)
    assert record.validity == RunValidity.VALID
    assert record.infra_errors == 0
    first = record.cases[0]
    assert (first.status, first.category, first.summary) == (
        LLMStatus.COMPLETED,
        Category.GENERAL,
        "Cliente pede ajuda.",
    )
    assert first.served_model == FAKE_SERVED_MODEL


@pytest.mark.parametrize("concurrency", [1, 4, 10])
def test_calls_in_flight_never_exceed_the_limit(concurrency):
    client = FakeLLMClient(default_delay=0.002)
    run(client, concurrency=concurrency)
    assert client.max_in_flight == concurrency


def test_concurrency_below_one_is_rejected():
    with pytest.raises(ValueError):
        run(FakeLLMClient(), concurrency=0)


def test_the_answer_key_never_reaches_the_model():
    expected_summary = "Resumo esperado que só existe no gabarito."
    cases = [dict(case, expected_summary=expected_summary) for case in full_matrix_cases()]
    edition = make_edition(cases)
    client = FakeLLMClient()
    asyncio.run(
        run_exam(
            edition=edition,
            golden=GOLDEN,
            prompt=prompt(),
            client=client,
            prices=PRICES,
            tracer=NoopTracer(),
            infra_error_limit_percent=2,
        )
    )
    for request in client.requests:
        sent = json.dumps(asdict(request), default=str, ensure_ascii=False)
        assert expected_summary not in sent
        assert "expected_category" not in sent and "acceptable_categories" not in sent


@pytest.mark.parametrize(
    ("errors", "expected"), [(2, RunValidity.VALID), (3, RunValidity.INCONCLUSIVE)]
)
def test_infrastructure_errors_decide_validity(errors, expected):
    client = FakeLLMClient(outcomes={email: LLMStatus.ERROR for email in EMAILS[:errors]})
    record = run(client)
    assert record.validity == expected
    assert record.infra_errors == errors
    failed = record.cases[0]
    assert failed.status == LLMStatus.ERROR
    assert failed.category is None and failed.summary is None
    assert failed.cost_usd == 0


def test_model_outcomes_are_not_infrastructure_errors():
    statuses = [LLMStatus.REFUSAL, LLMStatus.INCOMPLETE, LLMStatus.INVALID_OUTPUT] * 3
    client = FakeLLMClient(outcomes=dict(zip(EMAILS, statuses, strict=False)))
    record = run(client)
    assert record.validity == RunValidity.VALID
    assert record.infra_errors == 0
    assert [case.status for case in record.cases[:9]] == statuses


def test_costs_separate_the_exam_from_what_the_run_spent():
    record = run(FakeLLMClient())
    per_call = PRICES.cost_usd("gpt-6-luna", FAKE_USAGE)
    assert record.cases[0].cost_usd == pytest.approx(per_call)
    assert record.exam_cost_usd == pytest.approx(per_call * len(EMAILS))
    assert record.spent_usd == pytest.approx(record.exam_cost_usd)


def test_a_configuration_error_stops_the_whole_run():
    client = FakeLLMClient(config_error={EMAILS[0]}, default_delay=0.01)
    tracer = RecordingTracer()
    with pytest.raises(LLMConfigurationError):
        run(client, tracer=tracer, concurrency=2)
    assert len(client.requests) < len(EMAILS)
    assert tracer.finished == []


def test_a_model_without_a_price_stops_before_any_call():
    client = FakeLLMClient()
    with pytest.raises(LLMConfigurationError, match="no price"):
        run(client, model="gpt-unpriced")
    assert client.requests == []


def test_the_tracer_sees_the_run_and_every_case():
    tracer = RecordingTracer()
    record = run(FakeLLMClient(), tracer=tracer)
    (info,) = tracer.started
    assert info == record.info
    assert info.prompt_version_id == "v1"
    assert info.prompt_sha256 == "f" * 64
    assert info.model == "gpt-6-luna"
    assert info.golden == GOLDEN
    assert sorted(case_id for case_id, _, _ in tracer.cases) == sorted(c.id for c in EDITION.cases)
    assert tracer.finished == [record]


def test_a_rerun_through_the_cache_only_spends_calls_on_failed_cases(tmp_path):
    failing = set(EMAILS[:3])
    clock = lambda: datetime(2026, 11, 17, tzinfo=UTC)  # noqa: E731
    with SQLiteResponseCache(tmp_path / "cache.sqlite") as cache:
        first_client = FakeLLMClient(outcomes={email: LLMStatus.ERROR for email in failing})
        first = run(CachingLLMClient(first_client, cache, clock=clock))
        assert first.validity == RunValidity.INCONCLUSIVE

        second_client = FakeLLMClient()  # the outage is over
        second = run(CachingLLMClient(second_client, cache, clock=clock))

    assert len(first_client.requests) == len(EMAILS)
    assert sorted(map(wrap_email, failing)) == sorted(r.user_input for r in second_client.requests)
    assert second.validity == RunValidity.VALID
    assert sum(case.from_local_cache for case in second.cases) == len(EMAILS) - 3
    assert second.spent_usd == pytest.approx(3 * PRICES.cost_usd("gpt-6-luna", FAKE_USAGE))
    assert second.exam_cost_usd == pytest.approx(first.exam_cost_usd + second.spent_usd)


def test_load_golden_records_the_file_identity(tmp_path):
    path = tmp_path / "edition-1.json"
    path.write_text(json.dumps(edition_data(full_matrix_cases())), encoding="utf-8")
    edition, ref = load_golden(path)
    assert len(edition.cases) == 140
    assert (ref.edition, ref.status) == (1, "draft")
    assert len(ref.sha256) == 64
