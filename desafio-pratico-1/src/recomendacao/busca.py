import logging

from src.banco.vetorial import (
    buscar_similares,
    conectar_vetorial,
    obter_modelos_armazenados
)
from src.embeddings.gerador import (
    carregar_modelo,
    gerar_embedding,
    validar_dimensao
)


logger = logging.getLogger(__name__)


def buscar_conteudos(
    config,
    consulta: str,
    quantidade: int | None = None
) -> list[dict]:
    """Retorna os conteúdos semanticamente mais próximos da consulta."""

    parametros = config["embeddings"]

    if quantidade is None:
        quantidade = config["busca"]["top_k"]

    if quantidade <= 0:
        raise ValueError(
            f"Quantidade de resultados deve ser positiva: {quantidade}"
        )

    modelo = carregar_modelo(parametros["modelo"])
    validar_dimensao(modelo, parametros["dimensao"])

    vetor = gerar_embedding(modelo, consulta)

    conexao = conectar_vetorial(config)

    try:
        modelos = obter_modelos_armazenados(conexao)

        if modelos != [parametros["modelo"]]:
            logger.warning(
                "Modelo da consulta (%s) difere dos embeddings armazenados "
                "(%s). Execute o pipeline para regenerá-los.",
                parametros["modelo"],
                ", ".join(modelos) or "nenhum"
            )

        resultados = buscar_similares(conexao, vetor, quantidade)

    finally:
        conexao.close()

    logger.info(
        "Busca semântica executada: consulta='%s', resultados=%d",
        consulta,
        len(resultados)
    )

    return resultados


def exibir_resultados(consulta: str, resultados: list[dict]) -> None:
    """Exibe os resultados da busca semântica em formato de tabela."""

    print(f"\nConsulta: {consulta}")

    if not resultados:
        print("  Nenhum conteúdo encontrado.")
        return

    print(
        f"  {'Pos':>3} | {'ID':>4} | {'Similaridade':>12} | "
        f"{'Tipo':<8} | {'Categoria':<24} | Título"
    )

    for resultado in resultados:
        print(
            f"  {resultado['posicao']:>3} | "
            f"{resultado['conteudo_id']:>4} | "
            f"{resultado['similaridade']:>12.4f} | "
            f"{resultado['tipo']:<8} | "
            f"{resultado['categoria']:<24} | "
            f"{resultado['titulo']}"
        )
