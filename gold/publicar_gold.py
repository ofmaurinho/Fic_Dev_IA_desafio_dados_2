"""Publica a camada Gold no PostgreSQL (RF26).

Etapas, todas em uma única transação (nada é publicado se algo falhar):
    1. Quality gate: a execução de qualidade (RF31) do mesmo --id-execucao,
       ou a mais recente sobre a Silver real, precisa ter liberado a Gold e
       ter avaliado exatamente os arquivos Silver atuais (impressão SHA-256).
    2. Recarrega o schema silver com os arquivos Silver do Apache Hop e a
       saída Parquet do pipeline Beam (sql/camada_silver.sql).
    3. Define a chave de pseudonimização (PSEUDONIMIZACAO_CHAVE, do .env)
       apenas na transação e executa sql/camada_gold.sql.
    4. Registra a publicação em gold.publicacao e grava evidências e amostras
       em gold/evidencias/.

Pré-requisitos: dados mestres consolidados (dados_mestres/consolidar_conteudo.py)
e pipeline Beam executado (beam/pipeline.py).

Códigos de saída: 0 publicada; 1 bloqueada pelo quality gate ou por
pré-requisito ausente; 2 erro de execução (nada publicado).

Uso:
    python gold/publicar_gold.py
    python gold/publicar_gold.py --id-execucao <id do workflow>
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
import psycopg
import pyarrow.parquet as pq
from dotenv import load_dotenv
from psycopg.types.json import Jsonb

RAIZ_PROJETO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_PROJETO / "beam"))
from contratos import CATALOGO, COMENTARIOS, INTERACOES, impressao_silver, ler_silver_csv  # noqa: E402

load_dotenv(RAIZ_PROJETO / ".env")

SQL_SILVER = RAIZ_PROJETO / "sql" / "camada_silver.sql"
SQL_GOLD = RAIZ_PROJETO / "sql" / "camada_gold.sql"
SAIDA_BEAM = RAIZ_PROJETO / "dados" / "gold" / "engajamento_categoria_mensal"
DIR_EVIDENCIAS = RAIZ_PROJETO / "gold" / "evidencias"

TABELAS_GOLD = [
    "gold.dim_conteudo", "gold.dim_usuario", "gold.fato_interacao", "gold.fato_comentario",
    "gold.fato_recomendacao", "gold.kpi_engajamento_mensal_categoria",
]
VISOES_GOLD = ["gold.vw_kpi_mensal", "gold.vw_desempenho_conteudo", "gold.vw_conversao_recomendacao"]

# Tabela silver → (conjunto de origem, colunas na ordem da tabela).
CARGAS_SILVER = {
    "silver.catalogo": (CATALOGO, CATALOGO.esquema.names),
    "silver.interacao": (INTERACOES, INTERACOES.esquema.names),
    "silver.comentario": (COMENTARIOS, COMENTARIOS.esquema.names),
}


class Bloqueio(Exception):
    """Pré-condição de publicação não atendida."""


def verificar_quality_gate(cursor, id_execucao):
    cursor.execute(
        """SELECT id_execucao, status, gold_liberada, impressao_silver
           FROM qualidade.execucao
           WHERE id_execucao = %(id)s OR (%(id)s IS NULL AND origem_dados = 'silver')
           ORDER BY fim DESC
           LIMIT 1""",
        {"id": id_execucao},
    )
    execucao = cursor.fetchone()
    if execucao is None:
        raise Bloqueio(
            f"nenhuma execução de qualidade encontrada{f' para {id_execucao}' if id_execucao else ''}"
        )
    id_qualidade, status, liberada, impressao = execucao
    if not liberada:
        raise Bloqueio(f"quality gate {id_qualidade} terminou em '{status}'")
    if impressao != impressao_silver():
        raise Bloqueio(
            f"a Silver mudou depois do quality gate {id_qualidade}; execute os testes novamente"
        )
    return id_qualidade, status


def verificar_prerequisitos(cursor):
    cursor.execute("SELECT to_regclass('mestre.conteudo') IS NOT NULL")
    if not cursor.fetchone()[0]:
        raise Bloqueio("dados mestres ausentes: execute dados_mestres/consolidar_conteudo.py")
    cursor.execute("SELECT COUNT(*) FROM mestre.conteudo")
    if cursor.fetchone()[0] == 0:
        raise Bloqueio("mestre.conteudo está vazio")
    if not list(SAIDA_BEAM.glob("*.parquet")):
        raise Bloqueio(f"saída do Beam ausente em {SAIDA_BEAM}: execute beam/pipeline.py")


def linhas_para_copia(df):
    """DataFrame → tuplas com tipos Python (nulos do pandas viram None)."""
    objetos = df.astype(object).where(df.notna(), None)
    return objetos.itertuples(index=False, name=None)


def copiar(cursor, tabela, colunas, df):
    cursor.execute(f"TRUNCATE {tabela}")
    with cursor.copy(f"COPY {tabela} ({', '.join(colunas)}) FROM STDIN") as copia:
        for linha in linhas_para_copia(df[colunas]):
            copia.write_row(linha)
    return len(df)


def carregar_silver(cursor):
    cursor.execute(SQL_SILVER.read_text(encoding="utf-8"))
    linhas = {}
    for tabela, (contrato, colunas) in CARGAS_SILVER.items():
        linhas[tabela] = copiar(cursor, tabela, colunas, ler_silver_csv(contrato))

    beam = pq.read_table(SAIDA_BEAM).to_pandas()
    linhas["silver.engajamento_categoria_mensal"] = copiar(
        cursor, "silver.engajamento_categoria_mensal", list(beam.columns), beam
    )
    return linhas


def contar(cursor, objetos):
    contagens = {}
    for objeto in objetos:
        cursor.execute(f"SELECT COUNT(*) FROM {objeto}")
        contagens[objeto] = cursor.fetchone()[0]
    return contagens


def gravar_amostras(cursor):
    """Amostra de 10 linhas de cada tabela e visão da Gold (evidência RF34)."""
    destino = DIR_EVIDENCIAS / "amostras"
    destino.mkdir(parents=True, exist_ok=True)
    for objeto in TABELAS_GOLD + VISOES_GOLD:
        cursor.execute(f"SELECT * FROM {objeto} ORDER BY 1 LIMIT 10")
        colunas = [c.name for c in cursor.description]
        pd.DataFrame(cursor.fetchall(), columns=colunas).to_csv(
            destino / f"{objeto.removeprefix('gold.')}.csv", index=False, encoding="utf-8"
        )


def formatar_markdown(ev):
    linhas = [
        "# Publicação da camada Gold",
        "",
        f"- Execução: `{ev['id_execucao']}` em {ev['publicado_em']}",
        f"- Quality gate: `{ev['id_execucao_qualidade']}` — {ev['status_qualidade']}",
        "",
        "| Objeto | Linhas |",
        "|---|---:|",
        *[f"| `{objeto}` | {total} |" for objeto, total in ev["linhas"].items()],
        "",
        "Amostras de 10 linhas de cada objeto da Gold em `gold/evidencias/amostras/`.",
    ]
    return "\n".join(linhas) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--id-execucao", default=os.environ.get("ID_EXECUCAO"))
    args = parser.parse_args(argv)
    id_execucao = args.id_execucao or str(uuid.uuid4())

    chave = os.environ.get("PSEUDONIMIZACAO_CHAVE")
    if not chave:
        print("PSEUDONIMIZACAO_CHAVE não definida no ambiente ou no .env", file=sys.stderr)
        return 2

    try:
        with psycopg.connect(connect_timeout=10) as conexao, conexao.cursor() as cursor:
            id_qualidade, status_qualidade = verificar_quality_gate(cursor, args.id_execucao)
            verificar_prerequisitos(cursor)

            with conexao.transaction():
                linhas = carregar_silver(cursor)
                cursor.execute(
                    "SELECT set_config('app.chave_pseudonimizacao', %s, true)", (chave,)
                )
                cursor.execute(SQL_GOLD.read_text(encoding="utf-8"))
                linhas.update(contar(cursor, TABELAS_GOLD + VISOES_GOLD))
                publicado_em = datetime.now()
                cursor.execute(
                    """INSERT INTO gold.publicacao
                       (id_execucao, id_execucao_qualidade, status_qualidade, publicado_em, linhas)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (id_execucao, id_qualidade, status_qualidade, publicado_em, Jsonb(linhas)),
                )
            gravar_amostras(cursor)
    except Bloqueio as motivo:
        print(f"Gold NÃO publicada: {motivo}", file=sys.stderr)
        return 1
    except (OSError, psycopg.Error) as erro:
        print(f"Erro na publicação; nada foi publicado: {erro}", file=sys.stderr)
        return 2

    evidencia = {
        "id_execucao": id_execucao,
        "id_execucao_qualidade": id_qualidade,
        "status_qualidade": status_qualidade,
        "publicado_em": publicado_em.isoformat(timespec="seconds"),
        "linhas": linhas,
    }
    DIR_EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    (DIR_EVIDENCIAS / "publicacao.json").write_text(
        json.dumps(evidencia, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (DIR_EVIDENCIAS / "publicacao.md").write_text(formatar_markdown(evidencia), encoding="utf-8")
    print(formatar_markdown(evidencia))
    return 0


if __name__ == "__main__":
    sys.exit(main())
