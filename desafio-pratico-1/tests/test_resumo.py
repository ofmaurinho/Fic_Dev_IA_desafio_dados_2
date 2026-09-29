import json

from src.ingestao.resumo import (
    contar_situacoes,
    gerar_resumo,
    salvar_resumo
)


def test_contar_situacoes():
    resultados = [
        {"situacao": "valido"},
        {"situacao": "valido"},
        {"situacao": "invalido"},
        {"situacao": "incompleto"},
        {"situacao": "duplicado"},
        {"situacao": "duplicado"}
    ]

    resultado = contar_situacoes(resultados)

    assert resultado["valido"] == 2
    assert resultado["invalido"] == 1
    assert resultado["incompleto"] == 1
    assert resultado["duplicado"] == 2


def test_contar_situacoes_sem_registros():
    resultado = contar_situacoes([])

    assert resultado["valido"] == 0
    assert resultado["invalido"] == 0
    assert resultado["incompleto"] == 0
    assert resultado["duplicado"] == 0


def test_gerar_resumo():
    resultados_catalogo = [
        {"situacao": "valido"},
        {"situacao": "valido"},
        {"situacao": "invalido"}
    ]

    resultados_interacoes = [
        {"situacao": "valido"},
        {"situacao": "duplicado"}
    ]

    resultados_comentarios = [
        {"situacao": "valido"},
        {"situacao": "incompleto"}
    ]

    registros_carregados = {
        "catalogo": 3,
        "interacoes": 2,
        "comentarios": 2
    }

    registros_corrigidos = {
        "catalogo": 2,
        "interacoes": 0,
        "comentarios": 1
    }

    tempo_processamento = 0.15

    resultado = gerar_resumo(
        resultados_catalogo,
        resultados_interacoes,
        resultados_comentarios,
        registros_carregados,
        registros_corrigidos,
        tempo_processamento
    )

    assert resultado["catalogo"]["valido"] == 2
    assert resultado["catalogo"]["invalido"] == 1

    assert resultado["interacoes"]["valido"] == 1
    assert resultado["interacoes"]["duplicado"] == 1

    assert resultado["comentarios"]["valido"] == 1
    assert resultado["comentarios"]["incompleto"] == 1

    assert resultado["registros_carregados"] == registros_carregados
    assert resultado["registros_corrigidos"] == registros_corrigidos
    assert resultado["tempo_processamento_segundos"] == 0.15


def test_salvar_resumo(tmp_path):
    resumo = {
        "catalogo": {
            "valido": 10,
            "invalido": 0,
            "incompleto": 0,
            "duplicado": 0
        },
        "interacoes": {
            "valido": 10,
            "invalido": 0,
            "incompleto": 0,
            "duplicado": 0
        },
        "comentarios": {
            "valido": 10,
            "invalido": 0,
            "incompleto": 0,
            "duplicado": 0
        },
        "registros_carregados": {
            "catalogo": 10,
            "interacoes": 10,
            "comentarios": 10
        },
        "registros_corrigidos": {
            "catalogo": 10,
            "interacoes": 0,
            "comentarios": 0
        },
        "tempo_processamento_segundos": 0.10
    }

    caminho = tmp_path / "resumo.json"

    salvar_resumo(resumo, caminho)

    with open(caminho, "r", encoding="utf-8") as arquivo:
        resultado = json.load(arquivo)

    assert resultado == resumo