def limpar_espacos(registro: dict) -> dict:
    """Remove espaços extras no início e no fim dos valores textuais."""

    registro_tratado = registro.copy()

    for campo, valor in registro_tratado.items():
        if isinstance(valor, str):
            registro_tratado[campo] = valor.strip()

    return registro_tratado


def padronizar_catalogo(registro: dict) -> dict:
    """Padroniza os campos textuais e numéricos do catálogo."""

    registro = limpar_espacos(registro)

    registro["tipo"] = registro["tipo"].capitalize()
    registro["nivel"] = registro["nivel"].capitalize()

    registro["conteudo_id"] = int(registro["conteudo_id"])
    registro["carga_horaria_min"] = float(registro["carga_horaria_min"])

    return registro


def padronizar_interacao(registro: dict) -> dict:
    """Padroniza os campos da interação."""

    registro = limpar_espacos(registro)

    registro["tipo_interacao"] = registro["tipo_interacao"].lower()

    registro["usuario_id"] = int(registro["usuario_id"])
    registro["conteudo_id"] = int(registro["conteudo_id"])
    registro["tempo_consumido"] = float(registro["tempo_consumido"])
    registro["percentual_conclusao"] = float(
        registro["percentual_conclusao"]
    )

    if registro["avaliacao_atribuida"] is not None:
        registro["avaliacao_atribuida"] = float(
            registro["avaliacao_atribuida"]
        )

    return registro


def padronizar_comentario(registro: dict) -> dict:
    """Padroniza os campos do comentário."""

    registro = limpar_espacos(registro)

    registro["usuario_id"] = int(registro["usuario_id"])
    registro["conteudo_id"] = int(registro["conteudo_id"])
    registro["avaliacao"] = float(registro["avaliacao"])

    return registro


def tratar_registros(
    registros: list[dict],
    origem: str
) -> tuple[list[dict], int]:
    """Aplica o tratamento e retorna os registros e a quantidade corrigida."""

    registros_tratados = []
    registros_corrigidos = 0

    for registro in registros:

        registro_original = registro.copy()

        if origem == "catalogo":
            registro_tratado = padronizar_catalogo(registro)

        elif origem == "interacoes":
            registro_tratado = padronizar_interacao(registro)

        elif origem == "comentarios":
            registro_tratado = padronizar_comentario(registro)

        else:
            raise ValueError(
                f"Origem não reconhecida: {origem}"
            )

        if registro_tratado != registro_original:
            registros_corrigidos += 1

        registros_tratados.append(registro_tratado)

    return registros_tratados, registros_corrigidos


def remover_duplicados(
    registros: list[dict],
    origem: str
) -> list[dict]:
    """Remove registros duplicados conforme a regra da fonte."""

    registros_unicos = []
    chaves_existentes = set()

    for registro in registros:

        if origem == "catalogo":
            chave = registro["conteudo_id"]

        elif origem == "interacoes":
            chave = (
                registro["usuario_id"],
                registro["conteudo_id"],
                registro["tipo_interacao"],
                registro["data_hora"]
            )

        elif origem == "comentarios":
            chave = (
                registro["usuario_id"],
                registro["conteudo_id"],
                registro["data"],
                registro["comentario"]
            )

        else:
            raise ValueError(
                f"Origem não reconhecida: {origem}"
            )

        if chave not in chaves_existentes:
            chaves_existentes.add(chave)
            registros_unicos.append(registro)

    return registros_unicos