import json


def contar_situacoes(resultados: list) -> dict:
    """Conta os registros classificados em cada situação."""

    contagem = {
        "valido": 0,
        "invalido": 0,
        "incompleto": 0,
        "duplicado": 0
    }

    for resultado in resultados:
        situacao = resultado["situacao"]
        contagem[situacao] += 1

    return contagem


def gerar_resumo(
    resultados_catalogo: list,
    resultados_interacoes: list,
    resultados_comentarios: list,
    registros_carregados: dict,
    registros_corrigidos: dict,
    tempo_processamento: float
) -> dict:
    """Gera o resumo final do processamento."""

    contagem_catalogo = contar_situacoes(resultados_catalogo)
    contagem_interacoes = contar_situacoes(resultados_interacoes)
    contagem_comentarios = contar_situacoes(resultados_comentarios)

    return {
        "catalogo": contagem_catalogo,
        "interacoes": contagem_interacoes,
        "comentarios": contagem_comentarios,
        "registros_carregados": registros_carregados,
        "registros_corrigidos": registros_corrigidos,
        "tempo_processamento_segundos": tempo_processamento
    }


def salvar_resumo(resumo: dict, caminho: str) -> None:
    """Salva o resumo do processamento em um arquivo JSON."""

    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(
            resumo,
            arquivo,
            ensure_ascii=False,
            indent=4
        )