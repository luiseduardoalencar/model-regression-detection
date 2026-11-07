"""Crafted pairs against the real embedding model: checks the semantic threshold (decision 2.6).

Spends money (well under US$ 0.01): run on purpose with `-m live -s`. The pairs are
written for this test and are never golden cases. The threshold (0.74, decided
2026-11-07) was chosen from these scores, never from the golden set: the highest
value that still catches every paraphrase while no unrelated pair warns.
"""

import pytest

from regression_detector.adapters.openai_client import build_async_openai
from regression_detector.adapters.openai_embeddings import OpenAIEmbeddingClient
from regression_detector.golden.semantic import (
    SEMANTIC_WARN_SCORE,
    cosine_matrix,
    load_embeddings_config,
)

pytestmark = [pytest.mark.live, pytest.mark.asyncio]

# Same request in other words (same category): the layer must warn.
PARAPHRASES = {
    "delivery short": (
        "Meu pedido ainda não chegou. Podem me dizer onde ele está?",
        "Ainda não recebi minha encomenda. Onde ela está?",
    ),
    "delivery long": (
        "Olá, fiz uma compra no dia 3 e o prazo de entrega era até ontem. O rastreio está "
        "parado em 'em trânsito' há cinco dias. Vocês conseguem verificar o que aconteceu "
        "com meu pacote?",
        "Bom dia. Comprei um produto no começo do mês e já passou da data prevista de "
        "entrega. O código de rastreamento não atualiza há quase uma semana. Podem checar "
        "onde está a minha encomenda?",
    ),
    "cancellation": (
        "Quero cancelar o pedido que fiz hoje cedo, me arrependi da compra e ele ainda nem "
        "foi enviado.",
        "Fiz um pedido hoje de manhã e desisti. Como ainda não saiu para entrega, gostaria "
        "de cancelar.",
    ),
    "return_refund long": (
        "Recebi a cafeteira ontem e ela não liga. Já testei em outras tomadas. Quero "
        "devolver e receber o dinheiro de volta.",
        "A cafeteira que chegou ontem veio com defeito: não acende de jeito nenhum, testei "
        "em várias tomadas. Gostaria de fazer a devolução e ser reembolsado.",
    ),
    "payment duplicate": (
        "Fui cobrado duas vezes pela mesma compra no cartão.",
        "A mesma compra apareceu cobrada em dobro na fatura do meu cartão.",
    ),
    "payment pix": (
        "Paguei pelo Pix há duas horas, o dinheiro saiu da minha conta, mas o pedido "
        "continua como aguardando pagamento.",
        "Fiz o Pix faz umas duas horas e o valor já foi debitado do meu banco, só que o "
        "pedido ainda aparece aguardando pagamento.",
    ),
    "account password": (
        "Esqueci minha senha e não consigo entrar na minha conta.",
        "Não consigo acessar minha conta porque esqueci a senha.",
    ),
    "account email": (
        "Preciso trocar o email cadastrado na minha conta, porque não uso mais o antigo.",
        "Gostaria de atualizar o endereço de email da minha conta, o atual eu não acesso mais.",
    ),
    "technical checkout": (
        "Toda vez que clico em finalizar compra aparece uma tela de erro e não consigo "
        "concluir o pedido.",
        "Não consigo fechar a compra: quando aperto o botão de finalizar, o site mostra uma "
        "mensagem de erro.",
    ),
    "general coupon": (
        "Como faço para usar um cupom de desconto no aplicativo? Não encontro onde digitar o "
        "código.",
        "Onde eu coloco o código do cupom no app? Procurei e não achei o campo.",
    ),
}

# Same context, different request: one pair per tie-break rule (different categories).
# Printed only, never asserted: embeddings measure the topic, not the request, so these
# pairs overlap the paraphrases and no threshold separates them. The ones above the
# threshold warn as label conflicts; the label audit is what checks the rest.
MINIMAL_PAIRS = {
    "cancellation x return_refund": (
        "Quero cancelar meu pedido, ele ainda não chegou.",
        "Quero cancelar meu pedido, mas ele chegou ontem.",
    ),
    "delivery x cancellation": (
        "Meu pedido ainda não chegou. Onde ele está?",
        "Meu pedido ainda não chegou. Quero cancelar a compra.",
    ),
    "delivery x return_refund": (
        "Meu pedido não foi entregue e o rastreio diz que foi extraviado.",
        "Meu pedido foi entregue, mas a caixa chegou amassada e o produto quebrado.",
    ),
    "return_refund x payment": (
        "Cancelei a compra há duas semanas e o reembolso ainda não caiu no cartão.",
        "Não cancelei nada, mas a mesma compra foi cobrada duas vezes no cartão.",
    ),
    "account x payment": (
        "Minha conta foi bloqueada depois que fiz uma compra grande.",
        "Meu pagamento foi recusado quando tentei fazer uma compra grande.",
    ),
    "technical x payment": (
        "Na hora de pagar, o checkout mostra uma tela de erro e não finaliza.",
        "Na hora de pagar, meu cartão foi recusado e a compra não finalizou.",
    ),
    "technical x account": (
        "O aplicativo fecha sozinho quando abro a tela de login.",
        "Não consigo entrar no aplicativo porque minha senha não é aceita.",
    ),
}

# Different topics and requests: the layer must stay quiet.
UNRELATED = {
    "payment x return_refund": (
        "Fui cobrado duas vezes pela mesma compra.",
        "Quero devolver o produto e receber meu dinheiro de volta.",
    ),
    "technical x account": (
        "O aplicativo fecha sozinho quando abro a tela de login.",
        "Minha conta foi bloqueada depois que errei a senha.",
    ),
    "delivery x general": (
        "Onde está meu pedido? Já passou do prazo.",
        "Vocês têm cupom de desconto para a primeira compra?",
    ),
    "return_refund x technical": (
        "Quero trocar o tamanho da camiseta que recebi.",
        "O site não carrega a página de pagamento.",
    ),
    "general x payment": (
        "Parabéns pelo atendimento, resolveram meu problema rápido.",
        "Meu boleto venceu, consigo gerar outro?",
    ),
    "delivery x payment long": (
        "Comprei uma geladeira e a entrega está marcada para sexta, mas vou viajar. Dá para "
        "mudar o endereço de entrega?",
        "Recebi a nota fiscal com o CPF errado. Preciso que emitam outra com os dados "
        "corretos.",
    ),
}

GROUPS = {"paraphrases": PARAPHRASES, "minimal pairs": MINIMAL_PAIRS, "unrelated": UNRELATED}


async def test_threshold_separates_the_crafted_pairs():
    pairs = [
        (group, name, texts) for group, items in GROUPS.items() for name, texts in items.items()
    ]
    texts = [text for _, _, pair in pairs for text in pair]
    model = load_embeddings_config().model

    result = await OpenAIEmbeddingClient(build_async_openai()).embed(model, texts)
    matrix = cosine_matrix(result.vectors)
    scores = {
        (group, name): float(matrix[2 * i, 2 * i + 1]) for i, (group, name, _) in enumerate(pairs)
    }

    print(f"\nmodel={result.served_model} threshold={SEMANTIC_WARN_SCORE}")
    for group in GROUPS:
        print(f"\n{group}:")
        for (pair_group, name), score in sorted(scores.items(), key=lambda item: -item[1]):
            if pair_group == group:
                print(f"  {score:.3f}  {name}")

    paraphrase_scores = [score for (group, _), score in scores.items() if group == "paraphrases"]
    unrelated_scores = [score for (group, _), score in scores.items() if group == "unrelated"]
    assert min(paraphrase_scores) >= SEMANTIC_WARN_SCORE
    assert max(unrelated_scores) < SEMANTIC_WARN_SCORE