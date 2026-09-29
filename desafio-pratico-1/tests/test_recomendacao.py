import pytest

from src.recomendacao.motor import (
    ESTAVEL,
    NEGATIVO,
    POSITIVO,
    calcular_pontuacao,
    classificar_status,
    limitar_indice,
    normalizar_indices,
    selecionar_recomendacoes
)


@pytest.mark.parametrize(
    "i_vis, i_cur, i_conc, esperado",
    [
        (1.0, 1.0, 1, 100.0),
        (0.5, 0.3, 1, 40.0),
        (0.8, 0.0, 1, 40.0),
        (1.0, 1.0, 0, 0.0),
        (0.0, 0.0, 1, 0.0)
    ]
)
def test_calcular_pontuacao(i_vis, i_cur, i_conc, esperado):
    assert calcular_pontuacao(i_vis, i_cur, i_conc) == esperado


@pytest.mark.parametrize(
    "pontuacao, i_conc, esperado",
    [
        (100.0, 1, POSITIVO),
        (70.0, 1, POSITIVO),
        (69.99, 1, ESTAVEL),
        (40.01, 1, ESTAVEL),
        (40.0, 1, NEGATIVO),
        (0.0, 1, NEGATIVO),
        (90.0, 0, NEGATIVO)
    ]
)
def test_classificar_status(pontuacao, i_conc, esperado):
    assert classificar_status(pontuacao, i_conc, 70, 40) == esperado


def test_limitar_indice():
    assert limitar_indice(-0.2) == 0.0
    assert limitar_indice(0.35) == 0.35
    assert limitar_indice(1.3) == 1.0


def test_normalizar_indices():
    assert normalizar_indices([0.1, 0.3, 0.5]) == pytest.approx([0.0, 0.5, 1.0])


def test_normalizar_indices_valores_iguais_ou_vazios():
    assert normalizar_indices([0.2, 0.2]) == [0.0, 0.0]
    assert normalizar_indices([]) == []


def test_selecionar_recomendacoes_descarta_negativos_e_ordena():
    candidatos = [
        {"conteudo_id": 1, "pontuacao": 55.0, "status": ESTAVEL},
        {"conteudo_id": 2, "pontuacao": 95.0, "status": NEGATIVO},
        {"conteudo_id": 3, "pontuacao": 80.0, "status": POSITIVO},
        {"conteudo_id": 4, "pontuacao": 55.0, "status": ESTAVEL},
        {"conteudo_id": 5, "pontuacao": 20.0, "status": NEGATIVO}
    ]

    resultado = selecionar_recomendacoes(candidatos, 2)

    assert [item["conteudo_id"] for item in resultado] == [3, 1]
    assert [item["posicao"] for item in resultado] == [1, 2]
