import argparse
import logging
import time

from src.config.configuracao import carregar_configuracao
from src.config.logging_config import configurar_logging, registrar_etapa
from src.ingestao.leitores import (
    ler_fontes,
    salvar_catalogo,
    salvar_json
)
from src.ingestao.validadores import validar_registros
from src.ingestao.tratamentos import tratar_registros, remover_duplicados
from src.ingestao.resumo import gerar_resumo, salvar_resumo
from src.banco.postgresql import carregar_postgresql
from src.banco.mongodb import carregar_mongodb, demonstrar_consultas
from src.banco.vetorial import gerar_embeddings
from src.recomendacao.busca import buscar_conteudos, exibir_resultados
from src.recomendacao.motor import (
    consultar_recomendacoes_usuario,
    exibir_recomendacoes,
    gerar_recomendacoes
)


def ler_argumentos(argv: list[str] | None = None) -> argparse.Namespace:
    """Lê e valida os argumentos opcionais da linha de comando."""

    parser = argparse.ArgumentParser(
        description=(
            "Pipeline de recomendação de conteúdos educacionais. "
            "Sem argumentos, executa o pipeline completo."
        )
    )

    parser.add_argument(
        "--consulta",
        help="Executa somente a busca semântica para o texto informado."
    )

    parser.add_argument(
        "--top-k",
        type=int,
        help="Quantidade de resultados da busca (padrão: config.yaml)."
    )

    parser.add_argument(
        "--usuario",
        type=int,
        help="Exibe somente as recomendações mais recentes do usuário."
    )

    argumentos = parser.parse_args(argv)

    if argumentos.consulta is not None and not argumentos.consulta.strip():
        parser.error("--consulta não pode ser vazia.")

    if argumentos.top_k is not None:
        if argumentos.consulta is None:
            parser.error("--top-k só pode ser usado junto com --consulta.")

        if argumentos.top_k <= 0:
            parser.error("--top-k deve ser um inteiro positivo.")

    if argumentos.consulta is not None and argumentos.usuario is not None:
        parser.error("use --consulta ou --usuario, não ambos.")

    return argumentos


def executar_consulta(config, consulta: str, quantidade: int | None) -> None:
    """Executa uma busca semântica avulsa."""

    with registrar_etapa("Busca semântica"):
        resultados = buscar_conteudos(config, consulta, quantidade)

    exibir_resultados(consulta, resultados)


def executar_pipeline(config) -> None:
    """Executa a leitura, validação, tratamento, cargas, embeddings e recomendações."""

    logger = logging.getLogger(__name__)

    inicio = time.time()

    logger.info(
        "Arquivos de entrada: %s, %s, %s",
        config["dados"]["catalogo"],
        config["dados"]["interacoes"],
        config["dados"]["comentarios"]
    )

    with registrar_etapa("Leitura das fontes"):
        dados = ler_fontes(config)

    logger.info(
        "Registros lidos: catálogo=%d, interações=%d, comentários=%d",
        len(dados["catalogo"]),
        len(dados["interacoes"]),
        len(dados["comentarios"])
    )

    with registrar_etapa("Validação"):
        resultados_catalogo = validar_registros(
            dados["catalogo"],
            "catalogo",
            config["validacao"]["catalogo"]
        )

        resultados_interacoes = validar_registros(
            dados["interacoes"],
            "interacoes",
            config["validacao"]["interacoes"]
        )

        resultados_comentarios = validar_registros(
            dados["comentarios"],
            "comentarios",
            config["validacao"]["comentarios"]
        )

    logger.info(
        "Registros rejeitados: catálogo=%d, interações=%d, comentários=%d",
        sum(
            1 for resultado in resultados_catalogo
            if resultado["situacao"] != "valido"
        ),
        sum(
            1 for resultado in resultados_interacoes
            if resultado["situacao"] != "valido"
        ),
        sum(
            1 for resultado in resultados_comentarios
            if resultado["situacao"] != "valido"
        )
    )

    with registrar_etapa("Tratamento e remoção de duplicidades"):
        dados["catalogo"], corrigidos_catalogo = tratar_registros(
            dados["catalogo"], "catalogo"
        )

        dados["interacoes"], corrigidos_interacoes = tratar_registros(
            dados["interacoes"], "interacoes"
        )

        dados["comentarios"], corrigidos_comentarios = tratar_registros(
            dados["comentarios"], "comentarios"
        )

        logger.info(
            "Registros corrigidos: catálogo=%d, interações=%d, comentários=%d",
            corrigidos_catalogo,
            corrigidos_interacoes,
            corrigidos_comentarios
        )

        dados["catalogo"] = remover_duplicados(
            dados["catalogo"], "catalogo"
        )

        dados["interacoes"] = remover_duplicados(
            dados["interacoes"], "interacoes"
        )

        dados["comentarios"] = remover_duplicados(
            dados["comentarios"], "comentarios"
        )

    with registrar_etapa("Gravação dos arquivos processados"):
        salvar_catalogo(
            dados["catalogo"],
            config["dados"]["processados"]["catalogo"]
        )

        salvar_json(
            dados["interacoes"],
            config["dados"]["processados"]["interacoes"]
        )

        salvar_json(
            dados["comentarios"],
            config["dados"]["processados"]["comentarios"]
        )

    logger.info("Arquivos processados salvos.")

    with registrar_etapa("Carga PostgreSQL"):
        carregar_postgresql(
            config,
            dados["catalogo"],
            dados["interacoes"]
        )

    with registrar_etapa("Carga MongoDB"):
        comentarios_mongodb = carregar_mongodb(
            config,
            dados["comentarios"],
            dados["catalogo"]
        )

    print(f"MongoDB: {comentarios_mongodb} comentários armazenados.")

    with registrar_etapa("Consultas MongoDB"):
        demonstrar_consultas(config)

    with registrar_etapa("Geração de embeddings"):
        embeddings = gerar_embeddings(config)

    print(
        f"\nEmbeddings: {embeddings['gerados']} gerados, "
        f"{embeddings['reaproveitados']} reaproveitados, "
        f"{embeddings['falhas']} falhas."
    )

    print("\n--- Busca semântica ---")

    for consulta in config["busca"]["consultas_demo"]:
        executar_consulta(config, consulta, None)

    with registrar_etapa("Geração de recomendações"):
        recomendacoes = gerar_recomendacoes(config)

    print("\n--- Recomendações ---")
    print(
        f"{recomendacoes['total']} recomendações geradas para "
        f"{recomendacoes['usuarios']} usuários "
        f"(Positivo: {recomendacoes['por_status']['Positivo']}, "
        f"Estável: {recomendacoes['por_status']['Estável']}, "
        f"usuários sem recomendação: "
        f"{recomendacoes['usuarios_sem_recomendacao']})."
    )

    if dados["interacoes"]:
        usuario_exemplo = dados["interacoes"][0]["usuario_id"]

        exibir_recomendacoes(
            usuario_exemplo,
            consultar_recomendacoes_usuario(config, usuario_exemplo)
        )

    tempo_processamento = time.time() - inicio

    resumo = gerar_resumo(
        resultados_catalogo,
        resultados_interacoes,
        resultados_comentarios,
        {
            "postgresql": {
                "catalogo": len(dados["catalogo"]),
                "interacoes": len(dados["interacoes"])
            },
            "mongodb": {
                "comentarios": comentarios_mongodb
            },
            "pgvector": embeddings,
            "recomendacoes": {
                "data_geracao": recomendacoes["data_geracao"],
                "total": recomendacoes["total"],
                "por_status": recomendacoes["por_status"]
            }
        },
        {
            "catalogo": corrigidos_catalogo,
            "interacoes": corrigidos_interacoes,
            "comentarios": corrigidos_comentarios
        },
        tempo_processamento
    )

    salvar_resumo(
        resumo,
        config["dados"]["processados"]["resumo"]
    )

    logger.info(
        "Tempo total de processamento: %.4f segundos",
        tempo_processamento
    )

    print("\nValidação, tratamento, cargas, embeddings e recomendações concluídos.")
    print(f"Catálogo: {len(dados['catalogo'])} registros")
    print(f"Interações: {len(dados['interacoes'])} registros")
    print(f"Comentários: {len(dados['comentarios'])} registros")
    print(f"Tempo total: {tempo_processamento:.2f} segundos")


def main() -> None:
    """Ponto de entrada da aplicação."""

    argumentos = ler_argumentos()

    configurar_logging()
    logger = logging.getLogger(__name__)

    print("Início do processamento.")
    logger.info("Início do processamento.")

    config = carregar_configuracao()

    try:
        if argumentos.consulta is not None:
            executar_consulta(config, argumentos.consulta, argumentos.top_k)

        elif argumentos.usuario is not None:
            exibir_recomendacoes(
                argumentos.usuario,
                consultar_recomendacoes_usuario(config, argumentos.usuario)
            )

        else:
            executar_pipeline(config)

    except Exception:
        logger.exception("Processamento interrompido por falha.")
        print("Processamento interrompido por falha. Consulte logs/processamento.log.")
        raise

    finally:
        logger.info("Fim do processamento.")
        print("Fim do processamento.")


if __name__ == "__main__":
    main()
