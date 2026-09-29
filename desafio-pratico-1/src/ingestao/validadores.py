from datetime import datetime


def validar_campos_obrigatorios(registro, campos) -> list:
    """Retorna os campos obrigatórios que estão ausentes ou vazios."""

    ausentes = []

    for campo in campos:
        valor = registro.get(campo)

        if valor is None or str(valor).strip() == "":
            ausentes.append(campo)

    return ausentes


def validar_identificador(valor) -> bool:
    """Verifica se o identificador é um número inteiro positivo."""

    try:
        return int(valor) > 0
    except (TypeError, ValueError):
        return False


def validar_data(valor) -> bool:
    """Verifica se a data está no formato YYYY-MM-DD."""

    try:
        datetime.strptime(str(valor), "%Y-%m-%d")
        return True
    except (TypeError, ValueError):
        return False


def validar_tipo(valor, tipos_permitidos) -> bool:
    """Verifica se o tipo pertence aos valores configurados."""

    return valor in tipos_permitidos


def validar_nivel(valor, niveis_permitidos) -> bool:
    """Verifica se o nível pertence aos valores configurados."""

    return valor in niveis_permitidos


def validar_numero_nao_negativo(valor) -> bool:
    """Verifica se o valor é numérico e não negativo."""

    try:
        return float(valor) >= 0
    except (TypeError, ValueError):
        return False


def validar_catalogo(registro, regras) -> tuple:
    """Valida os campos e valores de um registro do catálogo."""

    erros = []

    campos_obrigatorios = regras["campos_obrigatorios"]

    ausentes = validar_campos_obrigatorios(registro, campos_obrigatorios)

    if ausentes:
        return "incompleto", [
            f"Campos obrigatórios ausentes: {', '.join(ausentes)}"
        ]

    if not validar_identificador(registro["conteudo_id"]):
        erros.append("conteudo_id inválido.")

    if not validar_tipo(
        registro["tipo"],
        regras["tipos_permitidos"]
    ):
        erros.append("tipo inválido.")

    if not validar_nivel(
        registro["nivel"],
        regras["niveis_permitidos"]
    ):
        erros.append("nivel inválido.")

    if not validar_numero_nao_negativo(
        registro["carga_horaria_min"]
    ):
        erros.append("carga_horaria_min inválida.")

    if not validar_data(registro["data_publicacao"]):
        erros.append("data_publicacao inválida.")

    if erros:
        return "invalido", erros

    return "valido", []


def validar_avaliacao(
    valor,
    minimo,
    maximo,
    permite_nulo=False
) -> bool:
    """Verifica se uma avaliação está dentro do intervalo configurado."""

    if valor is None and permite_nulo:
        return True

    try:
        valor = float(valor)
        return minimo <= valor <= maximo
    except (TypeError, ValueError):
        return False


def validar_percentual(valor, minimo, maximo) -> bool:
    """Verifica se um percentual está dentro do intervalo configurado."""

    try:
        valor = float(valor)
        return minimo <= valor <= maximo
    except (TypeError, ValueError):
        return False


def validar_data_hora(valor) -> bool:
    """Verifica se o valor possui uma data e hora válidas."""

    try:
        datetime.fromisoformat(str(valor))
        return True
    except (TypeError, ValueError):
        return False


def validar_tipo_interacao(valor, tipos_permitidos) -> bool:
    """Verifica se o tipo de interação está configurado."""

    return valor in tipos_permitidos


def validar_interacao(registro, regras) -> tuple:
    """Valida um registro de interação conforme as regras configuradas."""

    erros = []

    ausentes = validar_campos_obrigatorios(
        registro,
        regras["campos_obrigatorios"]
    )

    if ausentes:
        return "incompleto", [
            f"Campos obrigatórios ausentes: {', '.join(ausentes)}"
        ]

    if not validar_identificador(registro["usuario_id"]):
        erros.append("usuario_id inválido.")

    if not validar_identificador(registro["conteudo_id"]):
        erros.append("conteudo_id inválido.")

    if not validar_tipo_interacao(
        registro["tipo_interacao"],
        regras["tipos_permitidos"]
    ):
        erros.append("tipo_interacao inválido.")

    if not validar_data_hora(registro["data_hora"]):
        erros.append("data_hora inválida.")

    if not validar_numero_nao_negativo(
        registro["tempo_consumido"]
    ):
        erros.append("tempo_consumido inválido.")

    percentual = regras["percentual_conclusao"]

    if not validar_percentual(
        registro["percentual_conclusao"],
        percentual["minimo"],
        percentual["maximo"]
    ):
        erros.append("percentual_conclusao inválido.")

    avaliacao = regras["avaliacao_atribuida"]

    if not validar_avaliacao(
        registro["avaliacao_atribuida"],
        avaliacao["minimo"],
        avaliacao["maximo"],
        avaliacao["permite_nulo"]
    ):
        erros.append("avaliacao_atribuida inválida.")

    if erros:
        return "invalido", erros

    return "valido", []


def validar_comentario(registro, regras) -> tuple:
    """Valida um registro de comentário conforme as regras configuradas."""

    erros = []

    ausentes = validar_campos_obrigatorios(
        registro,
        regras["campos_obrigatorios"]
    )

    if ausentes:
        return "incompleto", [
            f"Campos obrigatórios ausentes: {', '.join(ausentes)}"
        ]

    if not validar_identificador(registro["usuario_id"]):
        erros.append("usuario_id inválido.")

    if not validar_identificador(registro["conteudo_id"]):
        erros.append("conteudo_id inválido.")

    avaliacao = regras["avaliacao"]

    if not validar_avaliacao(
        registro["avaliacao"],
        avaliacao["minimo"],
        avaliacao["maximo"]
    ):
        erros.append("avaliacao inválida.")

    if not validar_data(registro["data"]):
        erros.append("data inválida.")

    if not isinstance(registro["tags"], list):
        erros.append("tags deve ser uma lista.")

    if erros:
        return "invalido", erros

    return "valido", []


def gerar_chave_duplicidade(registro, origem) -> tuple:
    """Gera a chave utilizada para identificar registros duplicados."""

    if origem == "catalogo":
        return registro.get("conteudo_id")

    if origem == "interacoes":
        return (
            registro.get("usuario_id"),
            registro.get("conteudo_id"),
            registro.get("tipo_interacao"),
            registro.get("data_hora")
        )

    if origem == "comentarios":
        return (
            registro.get("usuario_id"),
            registro.get("conteudo_id"),
            registro.get("data"),
            registro.get("comentario")
        )

    return None


def identificar_duplicidades(registros, origem) -> set:
    """Identifica registros duplicados conforme a regra da fonte."""

    chaves_existentes = set()
    duplicados = set()

    for registro in registros:
        chave = gerar_chave_duplicidade(registro, origem)

        if chave in chaves_existentes:
            duplicados.add(chave)
        else:
            chaves_existentes.add(chave)

    return duplicados


def validar_registros(registros, origem, regras) -> list:
    """Valida os registros de uma fonte e identifica duplicidades."""

    duplicados = identificar_duplicidades(registros, origem)

    resultados = []

    for registro in registros:

        if origem == "catalogo":
            situacao, motivos = validar_catalogo(
                registro,
                regras
            )

        elif origem == "interacoes":
            situacao, motivos = validar_interacao(
                registro,
                regras
            )

        elif origem == "comentarios":
            situacao, motivos = validar_comentario(
                registro,
                regras
            )

        else:
            situacao = "invalido"
            motivos = ["Origem não reconhecida."]

        chave = gerar_chave_duplicidade(
            registro,
            origem
        )

        if situacao == "valido" and chave in duplicados:
            situacao = "duplicado"
            motivos.append("Registro duplicado conforme a regra da fonte.")

        resultados.append({
            "registro": registro,
            "situacao": situacao,
            "motivos": motivos
        })

    return resultados