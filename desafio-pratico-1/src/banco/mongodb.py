import logging

from pymongo import ASCENDING, MongoClient, UpdateOne


logger = logging.getLogger(__name__)


CHAVE_COMENTARIO = ["usuario_id", "conteudo_id", "data", "comentario"]


def conectar_mongodb(config) -> MongoClient:
    """Cria um cliente MongoDB e confirma a conexão com um ping."""

    mongodb = config["mongodb"]

    try:
        cliente = MongoClient(
            host=mongodb["host"],
            port=mongodb["porta"],
            username=mongodb.get("usuario"),
            password=mongodb.get("senha"),
            serverSelectionTimeoutMS=mongodb.get("timeout_ms", 5000)
        )

        cliente.admin.command("ping")

        logger.info("Conexão com MongoDB estabelecida.")

        return cliente

    except Exception:
        logger.exception(
            "Falha na conexão com MongoDB (%s:%s).",
            mongodb["host"],
            mongodb["porta"]
        )
        raise


def obter_colecao(cliente: MongoClient, config):
    """Retorna a coleção de comentários configurada."""

    mongodb = config["mongodb"]

    return cliente[mongodb["banco"]][mongodb["colecao_comentarios"]]


def criar_indices(colecao) -> None:
    """Cria os índices usados pela carga idempotente e pelas consultas."""

    colecao.create_index(
        [(campo, ASCENDING) for campo in CHAVE_COMENTARIO],
        unique=True,
        name="uq_comentario"
    )
    colecao.create_index("conteudo_id", name="idx_conteudo")
    colecao.create_index("tags", name="idx_tags")
    colecao.create_index("avaliacao", name="idx_avaliacao")
    colecao.create_index("categoria", name="idx_categoria")


def preparar_documentos_comentarios(
    comentarios: list[dict],
    catalogo: list[dict]
) -> list[dict]:
    """Enriquece os comentários com título, tipo e categoria do conteúdo.

    Comentários que referenciam conteúdos inexistentes no catálogo são
    descartados e registrados no log.
    """

    conteudos = {
        conteudo["conteudo_id"]: conteudo
        for conteudo in catalogo
    }

    documentos = []
    rejeitados = 0

    for comentario in comentarios:
        conteudo = conteudos.get(comentario["conteudo_id"])

        if conteudo is None:
            rejeitados += 1
            logger.warning(
                "Comentário rejeitado: conteúdo inexistente "
                "(usuario_id=%s, conteudo_id=%s).",
                comentario["usuario_id"],
                comentario["conteudo_id"]
            )
            continue

        documento = dict(comentario)
        documento["titulo"] = conteudo["titulo"]
        documento["tipo"] = conteudo["tipo"]
        documento["categoria"] = conteudo["categoria"]

        documentos.append(documento)

    logger.info(
        "Documentos de comentários preparados: %d (rejeitados: %d)",
        len(documentos),
        rejeitados
    )

    return documentos


def carregar_mongodb(
    config,
    comentarios: list[dict],
    catalogo: list[dict]
) -> int:
    """Carrega os comentários no MongoDB e retorna a quantidade persistida.

    A carga usa upsert pela chave do comentário; executá-la novamente não
    gera documentos duplicados.
    """

    documentos = preparar_documentos_comentarios(comentarios, catalogo)

    cliente = conectar_mongodb(config)

    try:
        colecao = obter_colecao(cliente, config)

        criar_indices(colecao)

        if not documentos:
            return 0

        operacoes = [
            UpdateOne(
                {campo: documento[campo] for campo in CHAVE_COMENTARIO},
                {"$set": documento},
                upsert=True
            )
            for documento in documentos
        ]

        resultado = colecao.bulk_write(operacoes, ordered=False)

        logger.info(
            "Carga MongoDB concluída: inseridos=%d, atualizados=%d, "
            "sem alteração=%d",
            resultado.upserted_count,
            resultado.modified_count,
            resultado.matched_count - resultado.modified_count
        )

        return resultado.upserted_count + resultado.matched_count

    except Exception:
        logger.exception("Falha na persistência dos comentários no MongoDB.")
        raise

    finally:
        cliente.close()
        logger.info("Conexão com MongoDB encerrada.")


def inserir_documento(colecao, documento: dict):
    """Insere um único documento e retorna seu identificador."""

    resultado = colecao.insert_one(dict(documento))

    return resultado.inserted_id


def consultar_comentarios_por_conteudo(
    colecao,
    conteudo_id: int
) -> list[dict]:
    """Retorna os comentários de um conteúdo, dos mais recentes aos mais antigos."""

    return list(
        colecao.find(
            {"conteudo_id": conteudo_id},
            {"_id": 0}
        ).sort("data", -1)
    )


def buscar_por_tag(colecao, tag: str) -> list[dict]:
    """Retorna os documentos que possuem a tag informada."""

    return list(colecao.find({"tags": tag}, {"_id": 0}))


def filtrar_por_nota(
    colecao,
    nota_minima: float,
    nota_maxima: float | None = None
) -> list[dict]:
    """Retorna as avaliações com nota dentro do intervalo informado."""

    filtro = {"$gte": nota_minima}

    if nota_maxima is not None:
        filtro["$lte"] = nota_maxima

    return list(colecao.find({"avaliacao": filtro}, {"_id": 0}))


def agregar_por_categoria(colecao) -> list[dict]:
    """Agrega a quantidade de comentários e a nota média por categoria."""

    pipeline = [
        {
            "$group": {
                "_id": "$categoria",
                "total_comentarios": {"$sum": 1},
                "avaliacao_media": {"$avg": "$avaliacao"}
            }
        },
        {"$sort": {"total_comentarios": -1}},
        {
            "$project": {
                "_id": 0,
                "categoria": "$_id",
                "total_comentarios": 1,
                "avaliacao_media": {"$round": ["$avaliacao_media", 2]}
            }
        }
    ]

    return list(colecao.aggregate(pipeline))


def obter_avaliacoes_positivas(
    config,
    nota_minima: float
) -> dict[int, set[int]]:
    """Retorna, por usuário, os conteúdos avaliados com nota mínima no MongoDB."""

    cliente = conectar_mongodb(config)

    try:
        colecao = obter_colecao(cliente, config)

        documentos = colecao.find(
            {"avaliacao": {"$gte": nota_minima}},
            {"_id": 0, "usuario_id": 1, "conteudo_id": 1}
        )

        avaliacoes = {}

        for documento in documentos:
            avaliacoes.setdefault(
                documento["usuario_id"], set()
            ).add(documento["conteudo_id"])

        return avaliacoes

    finally:
        cliente.close()


def demonstrar_consultas(config) -> None:
    """Executa e exibe um exemplo de cada consulta exigida no MongoDB."""

    cliente = conectar_mongodb(config)

    try:
        colecao = obter_colecao(cliente, config)

        exemplo = colecao.find_one({}, {"_id": 0})

        if exemplo is None:
            print("MongoDB: coleção de comentários vazia.")
            return

        conteudo_id = exemplo["conteudo_id"]
        tag = exemplo["tags"][0] if exemplo["tags"] else None

        print("\n--- Consultas MongoDB ---")
        print(f"Total de documentos: {colecao.count_documents({})}")

        comentarios = consultar_comentarios_por_conteudo(colecao, conteudo_id)
        print(
            f"Comentários do conteúdo {conteudo_id}: {len(comentarios)}"
        )

        if tag:
            print(f"Documentos com a tag '{tag}': "
                  f"{len(buscar_por_tag(colecao, tag))}")

        print(f"Avaliações com nota 5: {len(filtrar_por_nota(colecao, 5, 5))}")
        print(f"Avaliações com nota até 2: "
              f"{len(filtrar_por_nota(colecao, 1, 2))}")

        print("Comentários por categoria:")
        for item in agregar_por_categoria(colecao):
            print(
                f"  {item['categoria']:<25} "
                f"{item['total_comentarios']:>4} comentários | "
                f"nota média {item['avaliacao_media']}"
            )

    finally:
        cliente.close()
