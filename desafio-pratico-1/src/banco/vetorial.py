import logging
from collections.abc import Callable
from datetime import datetime

import numpy as np
from pgvector.psycopg2 import register_vector

from src.banco.postgresql import conectar_postgresql
from src.embeddings.gerador import (
    calcular_hash_texto,
    carregar_modelo,
    gerar_embeddings_textos,
    preparar_texto,
    validar_dimensao
)


logger = logging.getLogger(__name__)


def conectar_vetorial(config):
    """Abre uma conexão com o PostgreSQL já preparada para o tipo vector."""

    conexao = conectar_postgresql(config)

    register_vector(conexao)

    return conexao


def obter_conteudos(conexao) -> list[dict]:
    """Retorna os conteúdos persistidos no PostgreSQL."""

    with conexao.cursor() as cursor:
        cursor.execute(
            """
            SELECT conteudo_id, titulo, descricao
            FROM conteudo
            ORDER BY conteudo_id
            """
        )

        registros = cursor.fetchall()

    return [
        {"conteudo_id": conteudo_id, "titulo": titulo, "descricao": descricao}
        for conteudo_id, titulo, descricao in registros
    ]


def obter_embeddings_existentes(conexao) -> dict[int, tuple[str, str]]:
    """Retorna modelo e hash do texto dos embeddings já armazenados."""

    with conexao.cursor() as cursor:
        cursor.execute(
            """
            SELECT conteudo_id, modelo, texto_hash
            FROM conteudo_embedding
            """
        )

        registros = cursor.fetchall()

    return {
        conteudo_id: (modelo, texto_hash)
        for conteudo_id, modelo, texto_hash in registros
    }


def salvar_embedding(
    conexao,
    conteudo_id: int,
    vetor: np.ndarray,
    modelo: str,
    texto_hash: str
) -> None:
    """Insere ou atualiza o embedding de um conteúdo."""

    with conexao.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO conteudo_embedding (
                conteudo_id,
                embedding,
                modelo,
                texto_hash,
                gerado_em
            )
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (conteudo_id) DO UPDATE SET
                embedding = EXCLUDED.embedding,
                modelo = EXCLUDED.modelo,
                texto_hash = EXCLUDED.texto_hash,
                gerado_em = EXCLUDED.gerado_em
            """,
            (conteudo_id, vetor, modelo, texto_hash, datetime.now())
        )


def remover_embedding(conexao, conteudo_id: int) -> None:
    """Remove o embedding de um conteúdo."""

    with conexao.cursor() as cursor:
        cursor.execute(
            "DELETE FROM conteudo_embedding WHERE conteudo_id = %s",
            (conteudo_id,)
        )


def sincronizar_embeddings(
    conexao,
    conteudos: list[dict],
    gerar_vetores: Callable[[list[str]], np.ndarray],
    modelo: str
) -> dict:
    """Gera, atualiza ou remove embeddings sem confirmar a transação.

    Conteúdos cujo modelo e texto não mudaram são reaproveitados; os demais
    têm os vetores gerados em lote por `gerar_vetores`. Quando a geração de
    um conteúdo falha, o embedding anterior dele (se houver) é removido para
    não continuar sendo usado desatualizado.
    """

    existentes = obter_embeddings_existentes(conexao)

    contagem = {"gerados": 0, "reaproveitados": 0, "falhas": 0}
    pendentes = []

    for conteudo in conteudos:
        texto = preparar_texto(conteudo["titulo"], conteudo["descricao"])
        texto_hash = calcular_hash_texto(texto)

        if existentes.get(conteudo["conteudo_id"]) == (modelo, texto_hash):
            contagem["reaproveitados"] += 1
        else:
            pendentes.append((conteudo["conteudo_id"], texto, texto_hash))

    if not pendentes:
        return contagem

    try:
        vetores = gerar_vetores([texto for _, texto, _ in pendentes])

    except Exception:
        logger.exception(
            "Falha na geração do lote de embeddings (%d conteúdos).",
            len(pendentes)
        )
        vetores = [None] * len(pendentes)

    for (conteudo_id, _, texto_hash), vetor in zip(pendentes, vetores):
        if vetor is None or not np.any(vetor):
            contagem["falhas"] += 1
            logger.error(
                "Falha na geração do embedding (conteudo_id=%s): %s",
                conteudo_id,
                "erro no modelo" if vetor is None else "vetor nulo"
            )

            if conteudo_id in existentes:
                remover_embedding(conexao, conteudo_id)
                logger.warning(
                    "Embedding desatualizado removido (conteudo_id=%s).",
                    conteudo_id
                )

            continue

        salvar_embedding(conexao, conteudo_id, vetor, modelo, texto_hash)
        contagem["gerados"] += 1

    return contagem


def gerar_embeddings(config) -> dict:
    """Gera e armazena os embeddings dos conteúdos no pgvector.

    Somente conteúdos sem embedding, ou cujo texto ou modelo mudou, têm o
    vetor gerado novamente. Retorna as quantidades geradas, reaproveitadas
    e com falha.
    """

    parametros = config["embeddings"]

    modelo = carregar_modelo(parametros["modelo"])
    validar_dimensao(modelo, parametros["dimensao"])

    conexao = conectar_vetorial(config)

    try:
        conteudos = obter_conteudos(conexao)

        contagem = sincronizar_embeddings(
            conexao,
            conteudos,
            lambda textos: gerar_embeddings_textos(
                modelo, textos, parametros["lote"]
            ),
            parametros["modelo"]
        )

        conexao.commit()

        logger.info(
            "Embeddings (%s): gerados=%d, reaproveitados=%d, falhas=%d",
            parametros["modelo"],
            contagem["gerados"],
            contagem["reaproveitados"],
            contagem["falhas"]
        )

        return contagem

    except Exception:
        conexao.rollback()
        logger.exception("Falha na persistência dos embeddings no PostgreSQL.")
        raise

    finally:
        conexao.close()
        logger.info("Conexão com PostgreSQL (vetorial) encerrada.")


def obter_modelos_armazenados(conexao) -> list[str]:
    """Retorna os identificadores de modelo presentes nos embeddings."""

    with conexao.cursor() as cursor:
        cursor.execute("SELECT DISTINCT modelo FROM conteudo_embedding")

        return [modelo for (modelo,) in cursor.fetchall()]


def buscar_similares(
    conexao,
    vetor: np.ndarray,
    quantidade: int
) -> list[dict]:
    """Retorna os conteúdos mais próximos do vetor pela distância cosseno."""

    with conexao.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                co.conteudo_id,
                co.titulo,
                ca.nome AS categoria,
                co.tipo,
                ce.embedding <=> %s AS distancia
            FROM conteudo_embedding ce
            JOIN conteudo co
                ON co.conteudo_id = ce.conteudo_id
            JOIN categoria ca
                ON ca.categoria_id = co.categoria_id
            ORDER BY distancia ASC, co.conteudo_id ASC
            LIMIT %s
            """,
            (vetor, quantidade)
        )

        registros = cursor.fetchall()

    return [
        {
            "posicao": posicao,
            "conteudo_id": conteudo_id,
            "titulo": titulo,
            "categoria": categoria,
            "tipo": tipo,
            "distancia": float(distancia),
            "similaridade": 1 - float(distancia)
        }
        for posicao, (conteudo_id, titulo, categoria, tipo, distancia)
        in enumerate(registros, start=1)
    ]
