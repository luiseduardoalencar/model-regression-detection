"""Crafted text pairs with a known answer check the duplicate thresholds (decision 2.6)."""

import pytest

from regression_detector.golden.dedup import MatchKind, compare, find_cross_pairs, find_pairs


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        pytest.param(
            "Meu pedido 4521 não chegou!",
            "meu pedido 4521 NÃO chegou",
            MatchKind.EXACT,
            id="case and punctuation",
        ),
        pytest.param(
            "Meu pedido não chegou ainda",
            "Meu pedido na\u0303o chegou ainda",
            MatchKind.EXACT,
            id="composed and decomposed accent",
        ),
        pytest.param(
            "Pedido １２３４５ atrasado",
            "Pedido 12345 atrasado",
            MatchKind.EXACT,
            id="full-width digits",
        ),
        pytest.param(
            "O pedido 4521 chegou com a tela quebrada e quero devolver",
            "Quero devolver o pedido 4521 que chegou com a tela quebrada",
            MatchKind.NEAR_DUPLICATE,
            id="reordered words",
        ),
        pytest.param(
            "Comprei uma geladeira no pedido 88123 e ela ainda não chegou, "
            "o rastreio está parado há dez dias",
            "Comprei uma geladeira no pedido 88123 e ela ainda não chegou, "
            "o rastreio está parado há doze dias",
            MatchKind.NEAR_DUPLICATE,
            id="one word changed",
        ),
        pytest.param(
            "Meu pedido 4521 não chegou e o rastreio está parado há uma semana",
            "Meu pedido 7788 não chegou e o rastreio parou faz uma semana",
            MatchKind.SIMILAR,
            id="same scenario reworded",
        ),
        pytest.param(
            "Meu pedido 4521 ainda não chegou e o rastreio está parado faz uma semana inteira",
            "Meu pedido 4521 ainda não foi entregue e o código de rastreio não atualiza",
            None,
            id="same topic different wording",
        ),
        pytest.param(
            "Quero cancelar o pedido 4521 antes do envio",
            "Minha senha não funciona e não consigo entrar na conta",
            None,
            id="unrelated requests",
        ),
        pytest.param(
            "Pacote 123 sumiu",
            "Pacote 124 sumiu",
            None,
            id="short texts only get the exact check",
        ),
    ],
)
def test_compare(first, second, expected):
    match = compare(first, second)
    assert (match.kind if match else None) == expected


def test_find_pairs_reports_each_pair_once():
    texts = {
        "delivery-001": "Meu pedido 4521 não chegou!",
        "delivery-002": "meu pedido 4521 não chegou",
        "account-001": "Esqueci minha senha e não consigo entrar na conta",
    }
    pairs = find_pairs(texts)
    assert [(p.first_id, p.second_id, p.match.kind) for p in pairs] == [
        ("delivery-001", "delivery-002", MatchKind.EXACT)
    ]


def test_cross_pairs_compare_only_across_sets():
    few_shot = {"example-1": "Meu pedido 4521 não chegou e o rastreio está parado"}
    golden = {
        "delivery-001": "meu pedido 4521 não chegou, e o rastreio está parado!",
        "account-001": "Esqueci minha senha e não consigo entrar na conta",
    }
    pairs = find_cross_pairs(few_shot, golden)
    assert [(p.first_id, p.second_id, p.match.kind) for p in pairs] == [
        ("example-1", "delivery-001", MatchKind.EXACT)
    ]
