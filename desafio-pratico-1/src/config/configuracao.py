import os

import yaml
from dotenv import load_dotenv


def carregar_configuracao(caminho="config.yaml"):
    """Carrega as configurações da aplicação a partir de um arquivo YAML."""

    load_dotenv()

    with open(caminho, "r", encoding="utf-8") as arquivo:
        config = yaml.safe_load(arquivo)

    config["postgresql"]["senha"] = os.getenv("POSTGRES_PASSWORD")

    if "mongodb" in config:
        config["mongodb"]["usuario"] = os.getenv("MONGO_USER") or None
        config["mongodb"]["senha"] = os.getenv("MONGO_PASSWORD") or None

    validar_configuracao(config)

    return config


def validar_configuracao(config):
    """Verifica se as configurações obrigatórias estão presentes."""

    secoes_obrigatorias = [
        "dados",
        "validacao",
        "postgresql",
        "mongodb",
        "embeddings",
        "busca",
        "recomendacao"
    ]

    for secao in secoes_obrigatorias:
        if secao not in config:
            raise ValueError(
                f"Configuração obrigatória ausente: {secao}"
            )

    arquivos_obrigatorios = [
        "catalogo",
        "interacoes",
        "comentarios"
    ]

    for arquivo in arquivos_obrigatorios:
        if arquivo not in config["dados"]:
            raise ValueError(
                f"Caminho obrigatório ausente: {arquivo}"
            )

    regras_catalogo = config["validacao"].get("catalogo")

    if not regras_catalogo:
        raise ValueError(
            "Regras de validação do catálogo não configuradas."
        )

    campos_obrigatorios = regras_catalogo.get(
        "campos_obrigatorios"
    )

    if not campos_obrigatorios:
        raise ValueError(
            "Campos obrigatórios do catálogo não configurados."
        )

    if not regras_catalogo.get("tipos_permitidos"):
        raise ValueError(
            "Tipos permitidos não configurados."
        )

    if not regras_catalogo.get("niveis_permitidos"):
        raise ValueError(
            "Níveis permitidos não configurados."
        )

    if int(config["embeddings"].get("dimensao", 0)) <= 0:
        raise ValueError(
            "Dimensão dos embeddings deve ser um inteiro positivo."
        )

    if int(config["embeddings"].get("lote", 0)) <= 0:
        raise ValueError(
            "Tamanho do lote de embeddings deve ser um inteiro positivo."
        )

    if int(config["busca"].get("top_k", 0)) <= 0:
        raise ValueError(
            "Quantidade de resultados da busca (top_k) deve ser positiva."
        )

    recomendacao = config["recomendacao"]

    if int(recomendacao.get("top_n", 0)) <= 0:
        raise ValueError(
            "Quantidade de recomendações (top_n) deve ser positiva."
        )

    if not (
        0 <= recomendacao["limiar_negativo"]
        < recomendacao["limiar_positivo"] <= 100
    ):
        raise ValueError(
            "Limiares de recomendação inválidos: "
            "esperado 0 <= negativo < positivo <= 100."
        )