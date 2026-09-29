from src.ingestao.tratamentos import (
    limpar_espacos,
    padronizar_catalogo,
    padronizar_interacao,
    padronizar_comentario,
    tratar_registros,
    remover_duplicados
)


def test_limpar_espacos():
    registro = {
        "titulo": "  Python para IA  ",
        "autor": " João "
    }

    resultado = limpar_espacos(registro)

    assert resultado["titulo"] == "Python para IA"
    assert resultado["autor"] == "João"


def test_padronizar_catalogo():
    registro = {
        "conteudo_id": "10",
        "titulo": "Curso de Python",
        "tipo": "curso",
        "categoria": "Programação",
        "nivel": "básico",
        "carga_horaria_min": "120",
        "data_publicacao": "2026-01-10",
        "descricao": "Curso de Python",
        "autor": "João"
    }

    resultado = padronizar_catalogo(registro)

    assert resultado["conteudo_id"] == 10
    assert resultado["tipo"] == "Curso"
    assert resultado["nivel"] == "Básico"
    assert resultado["carga_horaria_min"] == 120.0


def test_padronizar_interacao():
    registro = {
        "usuario_id": "5",
        "conteudo_id": "10",
        "tipo_interacao": "VISUALIZAÇÃO",
        "data_hora": "2026-01-10T10:30:00",
        "tempo_consumido": "45",
        "percentual_conclusao": "80",
        "avaliacao_atribuida": "5"
    }

    resultado = padronizar_interacao(registro)

    assert resultado["usuario_id"] == 5
    assert resultado["conteudo_id"] == 10
    assert resultado["tipo_interacao"] == "visualização"
    assert resultado["tempo_consumido"] == 45.0
    assert resultado["percentual_conclusao"] == 80.0
    assert resultado["avaliacao_atribuida"] == 5.0


def test_padronizar_interacao_com_avaliacao_nula():
    registro = {
        "usuario_id": "5",
        "conteudo_id": "10",
        "tipo_interacao": "visualização",
        "data_hora": "2026-01-10T10:30:00",
        "tempo_consumido": "45",
        "percentual_conclusao": "80",
        "avaliacao_atribuida": None
    }

    resultado = padronizar_interacao(registro)

    assert resultado["avaliacao_atribuida"] is None


def test_padronizar_comentario():
    registro = {
        "usuario_id": "5",
        "conteudo_id": "10",
        "avaliacao": "4",
        "comentario": "  Excelente curso!  ",
        "tags": ["python", "ia"],
        "data": "2026-01-10"
    }

    resultado = padronizar_comentario(registro)

    assert resultado["usuario_id"] == 5
    assert resultado["conteudo_id"] == 10
    assert resultado["avaliacao"] == 4.0
    assert resultado["comentario"] == "Excelente curso!"
    assert resultado["tags"] == ["python", "ia"]


def test_tratar_registros_catalogo():
    registros = [
        {
            "conteudo_id": "1",
            "titulo": "Curso",
            "tipo": "curso",
            "categoria": "IA",
            "nivel": "básico",
            "carga_horaria_min": "60",
            "data_publicacao": "2026-01-01",
            "descricao": "Descrição",
            "autor": "Autor"
        }
    ]

    resultado, corrigidos = tratar_registros(
        registros,
        "catalogo"
    )

    assert len(resultado) == 1
    assert resultado[0]["conteudo_id"] == 1
    assert resultado[0]["tipo"] == "Curso"
    assert resultado[0]["nivel"] == "Básico"
    assert resultado[0]["carga_horaria_min"] == 60.0
    assert corrigidos == 1


def test_tratar_registros_interacoes():
    registros = [
        {
            "usuario_id": "1",
            "conteudo_id": "2",
            "tipo_interacao": "CURTIDA",
            "data_hora": "2026-01-01T10:00:00",
            "tempo_consumido": "10",
            "percentual_conclusao": "100",
            "avaliacao_atribuida": None
        }
    ]

    resultado, corrigidos = tratar_registros(
        registros,
        "interacoes"
    )

    assert resultado[0]["usuario_id"] == 1
    assert resultado[0]["conteudo_id"] == 2
    assert resultado[0]["tipo_interacao"] == "curtida"
    assert resultado[0]["tempo_consumido"] == 10.0
    assert corrigidos == 1


def test_tratar_registros_comentarios():
    registros = [
        {
            "usuario_id": "1",
            "conteudo_id": "2",
            "avaliacao": "5",
            "comentario": "Ótimo conteúdo",
            "tags": ["python"],
            "data": "2026-01-01"
        }
    ]

    resultado, corrigidos = tratar_registros(
        registros,
        "comentarios"
    )

    assert resultado[0]["usuario_id"] == 1
    assert resultado[0]["conteudo_id"] == 2
    assert resultado[0]["avaliacao"] == 5.0
    assert corrigidos == 1


def test_tratar_registros_origem_invalida():
    registros = [
        {"teste": "valor"}
    ]

    try:
        tratar_registros(registros, "origem_invalida")
        assert False
    except ValueError:
        assert True


def test_remover_duplicados_catalogo():
    registros = [
        {"conteudo_id": 1, "titulo": "Curso A"},
        {"conteudo_id": 1, "titulo": "Curso A"},
        {"conteudo_id": 2, "titulo": "Curso B"}
    ]

    resultado = remover_duplicados(registros, "catalogo")

    assert len(resultado) == 2
    assert resultado[0]["conteudo_id"] == 1
    assert resultado[1]["conteudo_id"] == 2


def test_remover_duplicados_interacoes():
    registros = [
        {
            "usuario_id": 1,
            "conteudo_id": 2,
            "tipo_interacao": "curtida",
            "data_hora": "2026-01-01T10:00:00"
        },
        {
            "usuario_id": 1,
            "conteudo_id": 2,
            "tipo_interacao": "curtida",
            "data_hora": "2026-01-01T10:00:00"
        },
        {
            "usuario_id": 1,
            "conteudo_id": 2,
            "tipo_interacao": "visualização",
            "data_hora": "2026-01-01T10:00:00"
        }
    ]

    resultado = remover_duplicados(registros, "interacoes")

    assert len(resultado) == 2


def test_remover_duplicados_comentarios():
    registros = [
        {
            "usuario_id": 1,
            "conteudo_id": 2,
            "data": "2026-01-01",
            "comentario": "Muito bom"
        },
        {
            "usuario_id": 1,
            "conteudo_id": 2,
            "data": "2026-01-01",
            "comentario": "Muito bom"
        },
        {
            "usuario_id": 1,
            "conteudo_id": 2,
            "data": "2026-01-02",
            "comentario": "Muito bom"
        }
    ]

    resultado = remover_duplicados(registros, "comentarios")

    assert len(resultado) == 2


def test_remover_duplicados_origem_invalida():
    registros = [
        {"teste": "valor"}
    ]

    try:
        remover_duplicados(registros, "origem_invalida")
        assert False
    except ValueError:
        assert True