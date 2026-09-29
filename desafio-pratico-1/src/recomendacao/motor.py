import logging
from datetime import datetime

from psycopg2.extras import execute_values

from src.banco.mongodb import obter_avaliacoes_positivas
from src.banco.vetorial import conectar_vetorial


logger = logging.getLogger(__name__)


POSITIVO = "Positivo"
ESTAVEL = "Estável"
NEGATIVO = "Negativo"


CONSULTA_INDICES = """
    WITH perfil_visualizacao AS (
        SELECT AVG(ce.embedding) AS vetor
        FROM interacao i
        JOIN conteudo_embedding ce
            ON ce.conteudo_id = i.conteudo_id
        WHERE i.usuario_id = %(usuario_id)s
          AND i.tipo_interacao = ANY(%(tipos_visualizacao)s)
    ),
    perfil_curtidas AS (
        SELECT AVG(ce.embedding) AS vetor
        FROM conteudo_embedding ce
        WHERE ce.conteudo_id IN (
            SELECT i.conteudo_id
            FROM interacao i
            WHERE i.usuario_id = %(usuario_id)s
              AND (
                  i.tipo_interacao = %(tipo_curtida)s
                  OR i.avaliacao_atribuida >= %(nota_minima)s
              )
        )
        OR ce.conteudo_id = ANY(%(avaliados_mongodb)s::INTEGER[])
    ),
    concluidos AS (
        SELECT DISTINCT i.conteudo_id
        FROM interacao i
        WHERE i.usuario_id = %(usuario_id)s
          AND (
              i.tipo_interacao = %(tipo_conclusao)s
              OR i.percentual_conclusao >= 100
          )
    )
    SELECT
        ce.conteudo_id,
        COALESCE(1 - (ce.embedding <=> pv.vetor), 0) AS similaridade_vis,
        COALESCE(1 - (ce.embedding <=> pc.vetor), 0) AS similaridade_cur,
        c.conteudo_id IS NULL AS nao_concluido
    FROM conteudo_embedding ce
    CROSS JOIN perfil_visualizacao pv
    CROSS JOIN perfil_curtidas pc
    LEFT JOIN concluidos c
        ON c.conteudo_id = ce.conteudo_id
    ORDER BY ce.conteudo_id
"""


def limitar_indice(valor: float) -> float:
    """Restringe um índice ao intervalo de 0.0 a 1.0."""

    return min(max(float(valor), 0.0), 1.0)


def normalizar_indices(valores: list[float]) -> list[float]:
    """Reescala os índices de um usuário para o intervalo de 0.0 a 1.0 (min-max)."""

    if not valores:
        return []

    minimo = min(valores)
    maximo = max(valores)

    if maximo == minimo:
        return [0.0 for _ in valores]

    return [(valor - minimo) / (maximo - minimo) for valor in valores]


def calcular_pontuacao(i_vis: float, i_cur: float, i_conc: int) -> float:
    """Pontuação = ((Ivis + Icur) / 2) * 100 * Iconc."""

    return round(((i_vis + i_cur) / 2) * 100 * i_conc, 2)


def classificar_status(
    pontuacao: float,
    i_conc: int,
    limiar_positivo: float,
    limiar_negativo: float
) -> str:
    """Classifica a recomendação como Positivo, Estável ou Negativo."""

    if i_conc == 0 or pontuacao <= limiar_negativo:
        return NEGATIVO

    if pontuacao >= limiar_positivo:
        return POSITIVO

    return ESTAVEL


def obter_usuarios(conexao) -> list[int]:
    """Retorna os identificadores dos usuários cadastrados."""

    with conexao.cursor() as cursor:
        cursor.execute("SELECT usuario_id FROM usuario ORDER BY usuario_id")

        return [usuario_id for (usuario_id,) in cursor.fetchall()]


def calcular_candidatos(
    conexao,
    usuario_id: int,
    avaliados_mongodb: set[int],
    parametros: dict
) -> list[dict]:
    """Calcula Ivis, Icur, Iconc, pontuação e status de cada conteúdo."""

    with conexao.cursor() as cursor:
        cursor.execute(
            CONSULTA_INDICES,
            {
                "usuario_id": usuario_id,
                "tipos_visualizacao": parametros["tipos_visualizacao"],
                "tipo_curtida": parametros["tipo_curtida"],
                "tipo_conclusao": parametros["tipo_conclusao"],
                "nota_minima": parametros["nota_minima_curtida"],
                "avaliados_mongodb": sorted(avaliados_mongodb)
            }
        )

        registros = cursor.fetchall()

    indices_vis = [limitar_indice(registro[1]) for registro in registros]
    indices_cur = [limitar_indice(registro[2]) for registro in registros]

    if parametros.get("normalizar_indices"):
        indices_vis = normalizar_indices(indices_vis)
        indices_cur = normalizar_indices(indices_cur)

    candidatos = []

    for (conteudo_id, _, _, nao_concluido), i_vis, i_cur in zip(
        registros, indices_vis, indices_cur
    ):
        i_conc = 1 if nao_concluido else 0

        pontuacao = calcular_pontuacao(i_vis, i_cur, i_conc)

        candidatos.append(
            {
                "usuario_id": usuario_id,
                "conteudo_id": conteudo_id,
                "i_vis": round(i_vis, 4),
                "i_cur": round(i_cur, 4),
                "i_conc": i_conc,
                "pontuacao": pontuacao,
                "status": classificar_status(
                    pontuacao,
                    i_conc,
                    parametros["limiar_positivo"],
                    parametros["limiar_negativo"]
                )
            }
        )

    return candidatos


def selecionar_recomendacoes(
    candidatos: list[dict],
    quantidade: int
) -> list[dict]:
    """Descarta os negativos, ordena pela pontuação e atribui a posição."""

    aptos = [
        candidato for candidato in candidatos
        if candidato["status"] != NEGATIVO
    ]

    aptos.sort(
        key=lambda candidato: (-candidato["pontuacao"], candidato["conteudo_id"])
    )

    selecionados = aptos[:quantidade]

    for posicao, candidato in enumerate(selecionados, start=1):
        candidato["posicao"] = posicao

    return selecionados


def inserir_recomendacoes(
    conexao,
    recomendacoes: list[dict],
    data_geracao: datetime
) -> None:
    """Insere as recomendações geradas em uma execução."""

    if not recomendacoes:
        return

    with conexao.cursor() as cursor:
        execute_values(
            cursor,
            """
            INSERT INTO recomendacao (
                usuario_id,
                conteudo_id,
                pontuacao,
                posicao,
                i_vis,
                i_cur,
                i_conc,
                status,
                data_geracao
            )
            VALUES %s
            """,
            [
                (
                    recomendacao["usuario_id"],
                    recomendacao["conteudo_id"],
                    recomendacao["pontuacao"],
                    recomendacao["posicao"],
                    recomendacao["i_vis"],
                    recomendacao["i_cur"],
                    recomendacao["i_conc"],
                    recomendacao["status"],
                    data_geracao
                )
                for recomendacao in recomendacoes
            ]
        )


def gerar_recomendacoes(config) -> dict:
    """Gera, classifica e persiste as recomendações de todos os usuários."""

    parametros = config["recomendacao"]
    data_geracao = datetime.now()

    avaliacoes_mongodb = obter_avaliacoes_positivas(
        config,
        parametros["nota_minima_curtida"]
    )

    conexao = conectar_vetorial(config)

    try:
        usuarios = obter_usuarios(conexao)

        total_por_status = {POSITIVO: 0, ESTAVEL: 0}
        usuarios_sem_recomendacao = 0

        for usuario_id in usuarios:
            candidatos = calcular_candidatos(
                conexao,
                usuario_id,
                avaliacoes_mongodb.get(usuario_id, set()),
                parametros
            )

            recomendacoes = selecionar_recomendacoes(
                candidatos,
                parametros["top_n"]
            )

            if not recomendacoes:
                usuarios_sem_recomendacao += 1

            for recomendacao in recomendacoes:
                total_por_status[recomendacao["status"]] += 1

            inserir_recomendacoes(conexao, recomendacoes, data_geracao)

        conexao.commit()

        total = sum(total_por_status.values())

        logger.info(
            "Recomendações geradas em %s: total=%d, positivas=%d, "
            "estáveis=%d, usuários sem recomendação=%d",
            data_geracao.isoformat(),
            total,
            total_por_status[POSITIVO],
            total_por_status[ESTAVEL],
            usuarios_sem_recomendacao
        )

        return {
            "data_geracao": data_geracao.isoformat(),
            "usuarios": len(usuarios),
            "usuarios_sem_recomendacao": usuarios_sem_recomendacao,
            "total": total,
            "por_status": total_por_status
        }

    except Exception:
        conexao.rollback()
        logger.exception("Falha na persistência das recomendações no PostgreSQL.")
        raise

    finally:
        conexao.close()


def consultar_recomendacoes_usuario(config, usuario_id: int) -> list[dict]:
    """Abre uma conexão e retorna as recomendações atuais do usuário."""

    conexao = conectar_vetorial(config)

    try:
        return obter_recomendacoes_usuario(conexao, usuario_id)

    finally:
        conexao.close()


def obter_recomendacoes_usuario(conexao, usuario_id: int) -> list[dict]:
    """Retorna as recomendações do usuário na execução mais recente.

    A execução considerada é a última do pipeline como um todo. Se o usuário
    não recebeu recomendações nela, a lista é vazia, e não a de uma execução
    anterior.
    """

    with conexao.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                r.usuario_id,
                r.conteudo_id,
                co.titulo,
                r.pontuacao,
                r.posicao,
                r.status,
                r.data_geracao
            FROM recomendacao r
            JOIN conteudo co
                ON co.conteudo_id = r.conteudo_id
            WHERE r.usuario_id = %s
              AND r.data_geracao = (
                  SELECT MAX(data_geracao)
                  FROM recomendacao
              )
            ORDER BY r.posicao
            """,
            (usuario_id,)
        )

        registros = cursor.fetchall()

    campos = [
        "usuario_id", "conteudo_id", "titulo",
        "pontuacao", "posicao", "status", "data_geracao"
    ]

    return [dict(zip(campos, registro)) for registro in registros]


def exibir_recomendacoes(usuario_id: int, recomendacoes: list[dict]) -> None:
    """Exibe as recomendações de um usuário em formato de tabela."""

    print(f"\nRecomendações para o usuário {usuario_id}:")

    if not recomendacoes:
        print("  Nenhuma recomendação disponível.")
        return

    print(
        f"  {'Pos':>3} | {'ID':>4} | {'Pontuação':>9} | {'Status':<8} | "
        f"{'Gerada em':<19} | Conteúdo"
    )

    for recomendacao in recomendacoes:
        print(
            f"  {recomendacao['posicao']:>3} | "
            f"{recomendacao['conteudo_id']:>4} | "
            f"{float(recomendacao['pontuacao']):>9.2f} | "
            f"{recomendacao['status']:<8} | "
            f"{recomendacao['data_geracao']:%Y-%m-%d %H:%M:%S} | "
            f"{recomendacao['titulo']}"
        )
