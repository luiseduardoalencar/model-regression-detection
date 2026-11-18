"""Format checks: crafted summaries that must pass or fail, and every golden reference passes."""

from pathlib import Path

import pytest

from regression_detector.eval.format_checks import (
    FormatCheckName,
    check_format,
    check_no_category_label,
    check_one_sentence,
    check_portuguese,
    check_starts_with_cliente,
)
from regression_detector.golden.schema import EdgeType, load_edition

GOLDEN_DRAFT = Path(__file__).parents[1] / "golden" / "drafts" / "edition-1.json"


def test_every_golden_reference_passes_every_check():
    # The references are Luis's summaries: if one fails, the check is wrong, not the summary.
    edition = load_edition(GOLDEN_DRAFT)
    failures = {}
    for case in edition.cases:
        result = check_format(
            case.expected_summary, out_of_scope=EdgeType.OUT_OF_SCOPE in case.edge_types
        )
        if not result.passed:
            failures[case.id] = [(c.name.value, c.detail) for c in result.failures]
    assert len(edition.cases) == 140
    assert failures == {}


@pytest.mark.parametrize(
    "summary",
    [
        "Cliente pergunta pelo pedido 12345.",
        "Cliente cobra o estorno de R$ 1.200 pago no dia 03/11.",
        "Cliente pede para trocar o email para joao.silva@email.com no cadastro.",
        "Cliente pergunta se o Sr. Souza pode receber o pedido nº. 77 em seu nome.",
        'Cliente diz que o produto "não funciona" e quer devolver.',
        "Cliente quer saber onde está o pedido 9!",
        "Cliente pergunta se pode cancelar o pedido 4410?",
    ],
)
def test_one_sentence_passes(summary):
    assert check_one_sentence(summary).passed


@pytest.mark.parametrize(
    ("summary", "detail"),
    [
        ("Cliente pergunta pelo pedido 123. Também quer trocar o endereço.", "2 sentences"),
        ("Cliente reclama do atraso! Quer cancelar. E pede reembolso.", "3 sentences"),
        ("Cliente pergunta: onde está o pedido? E quer o rastreio.", "2 sentences"),
        ("Cliente pergunta pelo pedido 123\ne quer o rastreio.", "contains a line break"),
        ("   ", "empty summary"),
    ],
)
def test_one_sentence_fails(summary, detail):
    check = check_one_sentence(summary)
    assert not check.passed
    assert check.detail == detail


def test_starts_with_cliente():
    assert check_starts_with_cliente("Cliente quer cancelar.", out_of_scope=False).passed
    for summary in ["O cliente quer cancelar.", "cliente quer cancelar.", "Clientes reclamam."]:
        check = check_starts_with_cliente(summary, out_of_scope=False)
        assert not check.passed
        assert check.detail.startswith("starts with")


def test_out_of_scope_is_exempt_from_starting_with_cliente():
    check = check_starts_with_cliente("Email de propaganda de fones.", out_of_scope=True)
    assert check.passed
    assert check.detail == "not applied: out_of_scope"


@pytest.mark.parametrize(
    ("summary", "detail"),
    [
        ("Caso de return_refund: devolução do pedido 4521.", "names return_refund"),
        ("Cliente quer return refund do pedido 4521.", "names return refund"),
        ("Cliente tem problema de PAYMENT e de account.", "names account, payment"),
    ],
)
def test_category_labels_are_caught(summary, detail):
    check = check_no_category_label(summary)
    assert not check.passed
    assert check.detail == detail


def test_portuguese_words_close_to_labels_pass():
    summary = "Cliente pergunta pelo pagamento, pela conta e pelo cancelamento do pedido."
    assert check_no_category_label(summary).passed


@pytest.mark.parametrize(
    "summary",
    [
        "Cliente quer cancelar o pedido 77.",
        "Cliente pede segunda via do boleto.",
        "Cliente diz que o notebook Dell XPS e o mouse wireless chegaram com defeito.",
        "Email de propaganda de uma loja oferecendo desconto em fones de ouvido.",
    ],
)
def test_portuguese_passes(summary):
    assert check_portuguese(summary).passed


@pytest.mark.parametrize(
    ("summary", "detail"),
    [
        ("Customer says order 4521 arrived broken and wants a refund.", "detected english"),
        ("Cliente wants a refund for order 9.", "detected english"),
        ("Cliente dice que el pedido llegó roto y quiere un reembolso.", "detected spanish"),
    ],
)
def test_other_languages_fail(summary, detail):
    check = check_portuguese(summary)
    assert not check.passed
    assert check.detail == detail


def test_language_detection_gives_the_same_answer_every_time():
    summary = "Cliente quer cancelar o pedido 77."
    assert len({check_portuguese(summary).passed for _ in range(20)}) == 1


def test_check_format_runs_the_four_checks_in_order():
    result = check_format("Customer wants a refund. Order 9 is payment.", out_of_scope=False)
    assert [check.name for check in result.checks] == list(FormatCheckName)
    assert not result.passed
    assert [check.name for check in result.failures] == list(FormatCheckName)
