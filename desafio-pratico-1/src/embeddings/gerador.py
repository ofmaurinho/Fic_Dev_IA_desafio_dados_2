import hashlib
import logging
import re
import time
from functools import lru_cache

import numpy as np


logger = logging.getLogger(__name__)


def preparar_texto(titulo: str, descricao: str) -> str:
    """Monta a representação textual do conteúdo a partir de título e descrição.

    O título vem primeiro: o codificador de texto do CLIP considera no máximo
    77 tokens, e o sentence-transformers trunca automaticamente o final de
    descrições longas.
    """

    texto = f"{titulo.strip()}. {descricao.strip()}"

    return re.sub(r"\s+", " ", texto)


def calcular_hash_texto(texto: str) -> str:
    """Calcula o hash SHA-256 do texto usado para gerar o embedding."""

    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def obter_dimensao_modelo(modelo) -> int:
    """Retorna a dimensão dos embeddings gerados pelo modelo."""

    # sentence-transformers 6 renomeou o método; o nome antigo é mantido
    # como alternativa para versões anteriores.
    if hasattr(modelo, "get_embedding_dimension"):
        return modelo.get_embedding_dimension()

    return modelo.get_sentence_embedding_dimension()


@lru_cache(maxsize=None)
def carregar_modelo(nome: str):
    """Carrega o modelo de embeddings (SentenceTransformer) uma vez por processo."""

    from sentence_transformers import SentenceTransformer

    inicio = time.time()

    try:
        modelo = SentenceTransformer(nome)

    except Exception:
        logger.exception("Falha ao carregar o modelo de embeddings %s.", nome)
        raise

    logger.info(
        "Modelo de embeddings carregado: %s (dimensão %d, %.2f segundos)",
        nome,
        obter_dimensao_modelo(modelo),
        time.time() - inicio
    )

    return modelo


def validar_dimensao(modelo, dimensao: int) -> None:
    """Verifica se a dimensão configurada corresponde à do modelo."""

    dimensao_modelo = obter_dimensao_modelo(modelo)

    if dimensao_modelo != dimensao:
        raise ValueError(
            f"Dimensão configurada ({dimensao}) difere da dimensão do "
            f"modelo ({dimensao_modelo}). Ajuste embeddings.dimensao no "
            "config.yaml e a coluna VECTOR do banco."
        )


def gerar_embeddings_textos(
    modelo,
    textos: list[str],
    lote: int
) -> np.ndarray:
    """Gera os embeddings normalizados (norma 1) de uma lista de textos."""

    return modelo.encode(
        textos,
        batch_size=lote,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False
    )


def gerar_embedding(modelo, texto: str) -> np.ndarray:
    """Gera o embedding normalizado de um único texto, como uma consulta."""

    return gerar_embeddings_textos(modelo, [texto], 1)[0]
