import logging
import os

import psycopg2
from dotenv import load_dotenv


load_dotenv()

logger = logging.getLogger(__name__)


def conectar_postgresql(config) -> psycopg2.extensions.connection:
    """Cria e retorna uma conexão com o PostgreSQL."""

    postgresql = config["postgresql"]

    try:
        conexao = psycopg2.connect(
            host=postgresql["host"],
            port=postgresql["porta"],
            dbname=postgresql["banco"],
            user=postgresql["usuario"],
            password=os.getenv("POSTGRES_PASSWORD")
        )

        logger.info("Conexão com PostgreSQL estabelecida.")

        return conexao

    except Exception:
        logger.exception("Falha na conexão com PostgreSQL.")
        raise


def inserir_categorias(
    conexao,
    registros: list[dict]
) -> None:
    """Insere as categorias distintas do catálogo."""

    categorias = set()

    for registro in registros:
        categorias.add(registro["categoria"])

    with conexao.cursor() as cursor:
        for categoria in categorias:
            cursor.execute(
                """
                INSERT INTO categoria (nome)
                VALUES (%s)
                ON CONFLICT (nome) DO NOTHING
                """,
                (categoria,)
            )

    logger.info("Categorias processadas: %d", len(categorias))


def obter_categorias(conexao) -> dict:
    """Retorna um dicionário relacionando nome e ID das categorias."""

    with conexao.cursor() as cursor:
        cursor.execute(
            """
            SELECT categoria_id, nome
            FROM categoria
            """
        )

        registros = cursor.fetchall()

    return {
        nome: categoria_id
        for categoria_id, nome in registros
    }


def inserir_conteudos(
    conexao,
    registros: list[dict],
    categorias: dict
) -> None:
    """Insere os conteúdos do catálogo."""

    with conexao.cursor() as cursor:
        for registro in registros:
            cursor.execute(
                """
                INSERT INTO conteudo (
                    conteudo_id,
                    titulo,
                    tipo,
                    categoria_id,
                    nivel,
                    carga_horaria_min,
                    data_publicacao,
                    descricao,
                    autor
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
                ON CONFLICT (conteudo_id) DO NOTHING
                """,
                (
                    registro["conteudo_id"],
                    registro["titulo"],
                    registro["tipo"],
                    categorias[registro["categoria"]],
                    registro["nivel"],
                    registro["carga_horaria_min"],
                    registro["data_publicacao"],
                    registro["descricao"],
                    registro["autor"]
                )
            )

    logger.info("Conteúdos processados: %d", len(registros))


def inserir_usuarios(
    conexao,
    registros: list[dict]
) -> None:
    """Insere os usuários distintos encontrados nas interações."""

    usuarios = set()

    for registro in registros:
        usuarios.add(registro["usuario_id"])

    with conexao.cursor() as cursor:
        for usuario_id in usuarios:
            cursor.execute(
                """
                INSERT INTO usuario (usuario_id)
                VALUES (%s)
                ON CONFLICT (usuario_id) DO NOTHING
                """,
                (usuario_id,)
            )

    logger.info("Usuários processados: %d", len(usuarios))


def inserir_interacoes(
    conexao,
    registros: list[dict]
) -> None:
    """Insere as interações dos usuários."""

    with conexao.cursor() as cursor:
        for registro in registros:
            cursor.execute(
                """
                INSERT INTO interacao (
                    usuario_id,
                    conteudo_id,
                    tipo_interacao,
                    data_hora,
                    tempo_consumido,
                    percentual_conclusao,
                    avaliacao_atribuida
                )
                VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s
                )
                ON CONFLICT (
                    usuario_id,
                    conteudo_id,
                    tipo_interacao,
                    data_hora
                ) DO NOTHING
                """,
                (
                    registro["usuario_id"],
                    registro["conteudo_id"],
                    registro["tipo_interacao"],
                    registro["data_hora"],
                    registro["tempo_consumido"],
                    registro["percentual_conclusao"],
                    registro["avaliacao_atribuida"]
                )
            )

    logger.info("Interações processadas: %d", len(registros))


def carregar_postgresql(
    config,
    catalogo: list[dict],
    interacoes: list[dict]
) -> None:
    """Carrega catálogo e interações no PostgreSQL em uma transação."""

    conexao = conectar_postgresql(config)

    try:
        inserir_categorias(conexao, catalogo)

        categorias = obter_categorias(conexao)

        inserir_conteudos(
            conexao,
            catalogo,
            categorias
        )

        inserir_usuarios(
            conexao,
            interacoes
        )

        inserir_interacoes(
            conexao,
            interacoes
        )

        conexao.commit()

        logger.info("Transação PostgreSQL concluída com sucesso.")

    except Exception:
        conexao.rollback()
        logger.exception("Falha na persistência dos dados no PostgreSQL.")
        raise

    finally:
        conexao.close()
        logger.info("Conexão com PostgreSQL encerrada.")