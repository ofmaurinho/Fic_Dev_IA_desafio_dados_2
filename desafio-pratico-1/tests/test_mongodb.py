import pytest

from src.banco.mongodb import (
    agregar_por_categoria,
    buscar_por_tag,
    carregar_mongodb,
    conectar_mongodb,
    consultar_comentarios_por_conteudo,
    filtrar_por_nota,
    inserir_documento,
    obter_avaliacoes_positivas,
    obter_colecao,
    preparar_documentos_comentarios
)


CATALOGO = [
    {"conteudo_id": 1, "titulo": "SQL", "tipo": "Curso", "categoria": "Banco de Dados"},
    {"conteudo_id": 2, "titulo": "APIs", "tipo": "Vídeo", "categoria": "Segurança & Governança"}
]

COMENTARIOS = [
    {
        "usuario_id": 10,
        "conteudo_id": 1,
        "avaliacao": 5.0,
        "comentario": "Excelente.",
        "tags": ["sql", "didático"],
        "data": "2026-08-20"
    },
    {
        "usuario_id": 11,
        "conteudo_id": 1,
        "avaliacao": 2.0,
        "comentario": "Confuso.",
        "tags": ["sql"],
        "data": "2026-08-21"
    },
    {
        "usuario_id": 10,
        "conteudo_id": 2,
        "avaliacao": 4.0,
        "comentario": "Bom.",
        "tags": ["api"],
        "data": "2026-08-22"
    }
]


@pytest.fixture
def config():
    return {
        "mongodb": {
            "host": "localhost",
            "porta": 27018,
            "banco": "desafio_dados_teste",
            "colecao_comentarios": "comentarios",
            "timeout_ms": 3000
        }
    }


@pytest.fixture
def colecao(config):
    carregar_mongodb(config, COMENTARIOS, CATALOGO)

    cliente = conectar_mongodb(config)

    yield obter_colecao(cliente, config)

    cliente.drop_database(config["mongodb"]["banco"])
    cliente.close()


def test_preparar_documentos_enriquece_e_rejeita_inexistentes():
    comentarios = COMENTARIOS + [
        {
            "usuario_id": 12,
            "conteudo_id": 999,
            "avaliacao": 3.0,
            "comentario": "Sem conteúdo.",
            "tags": [],
            "data": "2026-08-23"
        }
    ]

    documentos = preparar_documentos_comentarios(comentarios, CATALOGO)

    assert len(documentos) == 3
    assert documentos[0]["categoria"] == "Banco de Dados"
    assert documentos[0]["titulo"] == "SQL"
    assert "categoria" not in COMENTARIOS[0]


def test_carga_idempotente(config, colecao):
    quantidade = carregar_mongodb(config, COMENTARIOS, CATALOGO)

    assert quantidade == 3
    assert colecao.count_documents({}) == 3


def test_inserir_documento(colecao):
    inserir_documento(
        colecao,
        {
            "usuario_id": 20,
            "conteudo_id": 2,
            "avaliacao": 3.0,
            "comentario": "Novo.",
            "tags": ["api"],
            "data": "2026-08-25",
            "categoria": "Segurança & Governança"
        }
    )

    assert colecao.count_documents({"usuario_id": 20}) == 1


def test_consultar_comentarios_por_conteudo(colecao):
    comentarios = consultar_comentarios_por_conteudo(colecao, 1)

    assert [comentario["data"] for comentario in comentarios] == [
        "2026-08-21",
        "2026-08-20"
    ]


def test_buscar_por_tag(colecao):
    assert len(buscar_por_tag(colecao, "sql")) == 2
    assert len(buscar_por_tag(colecao, "inexistente")) == 0


def test_filtrar_por_nota(colecao):
    assert len(filtrar_por_nota(colecao, 4)) == 2
    assert len(filtrar_por_nota(colecao, 1, 2)) == 1


def test_agregar_por_categoria(colecao):
    resultado = {
        item["categoria"]: item
        for item in agregar_por_categoria(colecao)
    }

    assert resultado["Banco de Dados"]["total_comentarios"] == 2
    assert resultado["Banco de Dados"]["avaliacao_media"] == 3.5
    assert resultado["Segurança & Governança"]["total_comentarios"] == 1


def test_obter_avaliacoes_positivas(config, colecao):
    assert obter_avaliacoes_positivas(config, 4) == {10: {1, 2}}
