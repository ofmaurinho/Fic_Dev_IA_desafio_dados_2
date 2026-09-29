import pytest

from src.banco.postgresql import (
    conectar_postgresql,
    inserir_categorias,
    obter_categorias,
    inserir_conteudos,
    inserir_usuarios,
    inserir_interacoes
)


@pytest.fixture
def config():
    return {
        "postgresql": {
            "host": "localhost",
            "porta": 5433,
            "banco": "desafio_dados",
            "usuario": "postgres"
        }
    }


@pytest.fixture
def conexao(config):
    conexao = conectar_postgresql(config)

    yield conexao

    conexao.rollback()
    conexao.close()


def test_conectar_postgresql(config):
    conexao = conectar_postgresql(config)

    assert conexao is not None

    conexao.close()


def test_inserir_categorias(conexao):
    registros = [
        {"categoria": "Teste"}
    ]

    inserir_categorias(conexao, registros)

    categorias = obter_categorias(conexao)

    assert "Teste" in categorias


def test_inserir_conteudos(conexao):
    inserir_categorias(
        conexao,
        [{"categoria": "Teste Conteudo"}]
    )

    categorias = obter_categorias(conexao)

    registros = [
        {
            "conteudo_id": 999999,
            "titulo": "Conteúdo de teste",
            "tipo": "Curso",
            "categoria": "Teste Conteudo",
            "nivel": "Básico",
            "carga_horaria_min": 60,
            "data_publicacao": "2026-01-01",
            "descricao": "Descrição de teste",
            "autor": "Autor de teste"
        }
    ]

    inserir_conteudos(conexao, registros, categorias)

    cursor = conexao.cursor()
    cursor.execute(
        "SELECT titulo FROM conteudo WHERE conteudo_id = 999999"
    )

    resultado = cursor.fetchone()

    assert resultado[0] == "Conteúdo de teste"


def test_inserir_usuarios(conexao):
    registros = [
        {"usuario_id": 999999}
    ]

    inserir_usuarios(conexao, registros)

    cursor = conexao.cursor()
    cursor.execute(
        "SELECT usuario_id FROM usuario WHERE usuario_id = 999999"
    )

    resultado = cursor.fetchone()

    assert resultado[0] == 999999


def test_inserir_interacoes(conexao):
    inserir_usuarios(
        conexao,
        [{"usuario_id": 999998}]
    )

    registros = [
        {
            "usuario_id": 999998,
            "conteudo_id": 1,
            "tipo_interacao": "visualização",
            "data_hora": "2026-01-01T10:00:00",
            "tempo_consumido": 30,
            "percentual_conclusao": 50,
            "avaliacao_atribuida": None
        }
    ]

    inserir_interacoes(conexao, registros)

    cursor = conexao.cursor()
    cursor.execute(
        """
        SELECT usuario_id
        FROM interacao
        WHERE usuario_id = 999998
          AND conteudo_id = 1
          AND tipo_interacao = 'visualização'
          AND data_hora = '2026-01-01T10:00:00'
        """
    )

    resultado = cursor.fetchone()

    assert resultado[0] == 999998