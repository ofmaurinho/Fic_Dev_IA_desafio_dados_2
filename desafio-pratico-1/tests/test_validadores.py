from src.ingestao.validadores import (
    validar_campos_obrigatorios,
    validar_identificador,
    validar_data,
    validar_tipo,
    validar_nivel,
    validar_numero_nao_negativo,
    validar_catalogo,
    validar_avaliacao,
    validar_percentual,
    validar_data_hora,
    validar_tipo_interacao,
    validar_interacao,
    validar_comentario,
    gerar_chave_duplicidade,
    identificar_duplicidades,
    validar_registros
)


REGRAS_CATALOGO = {
    "campos_obrigatorios": [
        "conteudo_id",
        "titulo",
        "tipo",
        "categoria",
        "nivel",
        "carga_horaria_min",
        "data_publicacao",
        "descricao",
        "autor"
    ],
    "tipos_permitidos": [
        "Curso",
        "Podcast",
        "Artigo",
        "Vídeo"
    ],
    "niveis_permitidos": [
        "Básico",
        "Intermediário",
        "Avançado"
    ]
}


REGRAS_INTERACOES = {
    "campos_obrigatorios": [
        "usuario_id",
        "conteudo_id",
        "tipo_interacao",
        "data_hora",
        "tempo_consumido",
        "percentual_conclusao"
    ],
    "tipos_permitidos": [
        "início",
        "visualização",
        "curtida",
        "compartilhamento",
        "conclusão",
        "avaliação"
    ],
    "percentual_conclusao": {
        "minimo": 0,
        "maximo": 100
    },
    "avaliacao_atribuida": {
        "minimo": 1,
        "maximo": 5,
        "permite_nulo": True
    }
}


REGRAS_COMENTARIOS = {
    "campos_obrigatorios": [
        "usuario_id",
        "conteudo_id",
        "avaliacao",
        "comentario",
        "tags",
        "data"
    ],
    "avaliacao": {
        "minimo": 1,
        "maximo": 5
    }
}


def criar_catalogo():
    """Cria um registro de catálogo válido para os testes."""

    return {
        "conteudo_id": 1,
        "titulo": "Introdução à Agricultura Digital",
        "tipo": "Curso",
        "categoria": "Agricultura Digital",
        "nivel": "Básico",
        "carga_horaria_min": 60,
        "data_publicacao": "2026-08-20",
        "descricao": "Curso introdutório.",
        "autor": "Autor Teste"
    }


def criar_interacao():
    """Cria um registro de interação válido para os testes."""

    return {
        "usuario_id": 1,
        "conteudo_id": 1,
        "tipo_interacao": "visualização",
        "data_hora": "2026-08-20T10:30:00",
        "tempo_consumido": 30,
        "percentual_conclusao": 50,
        "avaliacao_atribuida": None
    }


def criar_comentario():
    """Cria um registro de comentário válido para os testes."""

    return {
        "usuario_id": 1,
        "conteudo_id": 1,
        "avaliacao": 5,
        "comentario": "Conteúdo muito bom.",
        "tags": ["agricultura", "tecnologia"],
        "data": "2026-08-20"
    }


# ============================================================
# TESTES DOS VALIDADORES BÁSICOS
# ============================================================

def test_validar_campos_obrigatorios():
    registro = {
        "nome": "Teste",
        "idade": ""
    }

    campos = ["nome", "idade", "cidade"]

    resultado = validar_campos_obrigatorios(registro, campos)

    assert resultado == ["idade", "cidade"]


def test_validar_identificador_valido():
    assert validar_identificador(1) is True
    assert validar_identificador("10") is True


def test_validar_identificador_invalido():
    assert validar_identificador(0) is False
    assert validar_identificador(-1) is False
    assert validar_identificador("abc") is False


def test_validar_data_valida():
    assert validar_data("2026-08-20") is True


def test_validar_data_invalida():
    assert validar_data("20/08/2026") is False
    assert validar_data("2026-13-40") is False


def test_validar_tipo():
    tipos = ["Curso", "Podcast"]

    assert validar_tipo("Curso", tipos) is True
    assert validar_tipo("Livro", tipos) is False


def test_validar_nivel():
    niveis = ["Básico", "Intermediário", "Avançado"]

    assert validar_nivel("Básico", niveis) is True
    assert validar_nivel("Especialista", niveis) is False


def test_validar_numero_nao_negativo():
    assert validar_numero_nao_negativo(0) is True
    assert validar_numero_nao_negativo(10) is True
    assert validar_numero_nao_negativo(-1) is False
    assert validar_numero_nao_negativo("abc") is False


def test_validar_avaliacao():
    assert validar_avaliacao(1, 1, 5) is True
    assert validar_avaliacao(5, 1, 5) is True
    assert validar_avaliacao(0, 1, 5) is False
    assert validar_avaliacao(6, 1, 5) is False


def test_validar_avaliacao_nula_permitida():
    assert validar_avaliacao(
        None,
        1,
        5,
        permite_nulo=True
    ) is True


def test_validar_avaliacao_nula_nao_permitida():
    assert validar_avaliacao(
        None,
        1,
        5,
        permite_nulo=False
    ) is False


def test_validar_percentual():
    assert validar_percentual(0, 0, 100) is True
    assert validar_percentual(100, 0, 100) is True
    assert validar_percentual(50, 0, 100) is True
    assert validar_percentual(-1, 0, 100) is False
    assert validar_percentual(101, 0, 100) is False


def test_validar_data_hora():
    assert validar_data_hora(
        "2026-08-20T10:30:00"
    ) is True


def test_validar_data_hora_invalida():
    assert validar_data_hora(
        "20/08/2026 10:30"
    ) is False


def test_validar_tipo_interacao():
    tipos = [
        "início",
        "visualização",
        "curtida",
        "compartilhamento",
        "conclusão",
        "avaliação"
    ]

    assert validar_tipo_interacao(
        "visualização",
        tipos
    ) is True

    assert validar_tipo_interacao(
        "download",
        tipos
    ) is False


# ============================================================
# TESTES DO CATÁLOGO
# ============================================================

def test_catalogo_valido():
    registro = criar_catalogo()

    situacao, motivos = validar_catalogo(
        registro,
        REGRAS_CATALOGO
    )

    assert situacao == "valido"
    assert motivos == []


def test_catalogo_incompleto():
    registro = criar_catalogo()

    del registro["titulo"]

    situacao, motivos = validar_catalogo(
        registro,
        REGRAS_CATALOGO
    )

    assert situacao == "incompleto"
    assert "titulo" in motivos[0]


def test_catalogo_invalido():
    registro = criar_catalogo()

    registro["conteudo_id"] = -1

    situacao, motivos = validar_catalogo(
        registro,
        REGRAS_CATALOGO
    )

    assert situacao == "invalido"
    assert "conteudo_id inválido." in motivos


def test_catalogo_tipo_invalido():
    registro = criar_catalogo()

    registro["tipo"] = "Livro"

    situacao, motivos = validar_catalogo(
        registro,
        REGRAS_CATALOGO
    )

    assert situacao == "invalido"
    assert "tipo inválido." in motivos


def test_catalogo_nivel_invalido():
    registro = criar_catalogo()

    registro["nivel"] = "Especialista"

    situacao, motivos = validar_catalogo(
        registro,
        REGRAS_CATALOGO
    )

    assert situacao == "invalido"
    assert "nivel inválido." in motivos


def test_catalogo_carga_horaria_negativa():
    registro = criar_catalogo()

    registro["carga_horaria_min"] = -10

    situacao, motivos = validar_catalogo(
        registro,
        REGRAS_CATALOGO
    )

    assert situacao == "invalido"
    assert "carga_horaria_min inválida." in motivos


def test_catalogo_data_invalida():
    registro = criar_catalogo()

    registro["data_publicacao"] = "20/08/2026"

    situacao, motivos = validar_catalogo(
        registro,
        REGRAS_CATALOGO
    )

    assert situacao == "invalido"
    assert "data_publicacao inválida." in motivos


# ============================================================
# TESTES DE INTERAÇÕES
# ============================================================

def test_interacao_valida():
    registro = criar_interacao()

    situacao, motivos = validar_interacao(
        registro,
        REGRAS_INTERACOES
    )

    assert situacao == "valido"
    assert motivos == []


def test_interacao_incompleta():
    registro = criar_interacao()

    del registro["usuario_id"]

    situacao, motivos = validar_interacao(
        registro,
        REGRAS_INTERACOES
    )

    assert situacao == "incompleto"
    assert "usuario_id" in motivos[0]


def test_interacao_id_invalido():
    registro = criar_interacao()

    registro["usuario_id"] = -1

    situacao, motivos = validar_interacao(
        registro,
        REGRAS_INTERACOES
    )

    assert situacao == "invalido"
    assert "usuario_id inválido." in motivos


def test_interacao_tipo_invalido():
    registro = criar_interacao()

    registro["tipo_interacao"] = "download"

    situacao, motivos = validar_interacao(
        registro,
        REGRAS_INTERACOES
    )

    assert situacao == "invalido"
    assert "tipo_interacao inválido." in motivos


def test_interacao_percentual_invalido():
    registro = criar_interacao()

    registro["percentual_conclusao"] = 101

    situacao, motivos = validar_interacao(
        registro,
        REGRAS_INTERACOES
    )

    assert situacao == "invalido"
    assert "percentual_conclusao inválido." in motivos


def test_interacao_tempo_negativo():
    registro = criar_interacao()

    registro["tempo_consumido"] = -10

    situacao, motivos = validar_interacao(
        registro,
        REGRAS_INTERACOES
    )

    assert situacao == "invalido"
    assert "tempo_consumido inválido." in motivos


def test_interacao_avaliacao_invalida():
    registro = criar_interacao()

    registro["avaliacao_atribuida"] = 6

    situacao, motivos = validar_interacao(
        registro,
        REGRAS_INTERACOES
    )

    assert situacao == "invalido"
    assert "avaliacao_atribuida inválida." in motivos


# ============================================================
# TESTES DE COMENTÁRIOS
# ============================================================

def test_comentario_valido():
    registro = criar_comentario()

    situacao, motivos = validar_comentario(
        registro,
        REGRAS_COMENTARIOS
    )

    assert situacao == "valido"
    assert motivos == []


def test_comentario_incompleto():
    registro = criar_comentario()

    del registro["comentario"]

    situacao, motivos = validar_comentario(
        registro,
        REGRAS_COMENTARIOS
    )

    assert situacao == "incompleto"
    assert "comentario" in motivos[0]


def test_comentario_avaliacao_invalida():
    registro = criar_comentario()

    registro["avaliacao"] = 6

    situacao, motivos = validar_comentario(
        registro,
        REGRAS_COMENTARIOS
    )

    assert situacao == "invalido"
    assert "avaliacao inválida." in motivos


def test_comentario_data_invalida():
    registro = criar_comentario()

    registro["data"] = "20/08/2026"

    situacao, motivos = validar_comentario(
        registro,
        REGRAS_COMENTARIOS
    )

    assert situacao == "invalido"
    assert "data inválida." in motivos


def test_comentario_tags_invalidas():
    registro = criar_comentario()

    registro["tags"] = "agricultura"

    situacao, motivos = validar_comentario(
        registro,
        REGRAS_COMENTARIOS
    )

    assert situacao == "invalido"
    assert "tags deve ser uma lista." in motivos


# ============================================================
# TESTES DE DUPLICIDADE
# ============================================================

def test_chave_duplicidade_catalogo():
    registro = criar_catalogo()

    chave = gerar_chave_duplicidade(
        registro,
        "catalogo"
    )

    assert chave == 1


def test_chave_duplicidade_interacao():
    registro = criar_interacao()

    chave = gerar_chave_duplicidade(
        registro,
        "interacoes"
    )

    assert chave == (
        1,
        1,
        "visualização",
        "2026-08-20T10:30:00"
    )


def test_chave_duplicidade_comentario():
    registro = criar_comentario()

    chave = gerar_chave_duplicidade(
        registro,
        "comentarios"
    )

    assert chave == (
        1,
        1,
        "2026-08-20",
        "Conteúdo muito bom."
    )


def test_catalogo_duplicado():
    registro1 = criar_catalogo()
    registro2 = criar_catalogo()

    registros = [registro1, registro2]

    resultados = validar_registros(
        registros,
        "catalogo",
        REGRAS_CATALOGO
    )

    assert resultados[0]["situacao"] == "duplicado"
    assert resultados[1]["situacao"] == "duplicado"


def test_interacao_duplicada():
    registro1 = criar_interacao()
    registro2 = criar_interacao()

    registros = [registro1, registro2]

    resultados = validar_registros(
        registros,
        "interacoes",
        REGRAS_INTERACOES
    )

    assert resultados[0]["situacao"] == "duplicado"
    assert resultados[1]["situacao"] == "duplicado"


def test_comentario_duplicado():
    registro1 = criar_comentario()
    registro2 = criar_comentario()

    registros = [registro1, registro2]

    resultados = validar_registros(
        registros,
        "comentarios",
        REGRAS_COMENTARIOS
    )

    assert resultados[0]["situacao"] == "duplicado"
    assert resultados[1]["situacao"] == "duplicado"


# ============================================================
# TESTES DA PRIORIDADE DA CLASSIFICAÇÃO
# ============================================================

def test_registro_incompleto_nao_deve_ser_classificado_como_duplicado():
    registro1 = criar_catalogo()
    registro2 = criar_catalogo()

    del registro2["titulo"]

    resultados = validar_registros(
        [registro1, registro2],
        "catalogo",
        REGRAS_CATALOGO
    )

    assert resultados[1]["situacao"] == "incompleto"


def test_registro_invalido_nao_deve_ser_classificado_como_duplicado():
    registro1 = criar_catalogo()
    registro2 = criar_catalogo()

    registro2["tipo"] = "Livro"

    resultados = validar_registros(
        [registro1, registro2],
        "catalogo",
        REGRAS_CATALOGO
    )

    assert resultados[1]["situacao"] == "invalido"