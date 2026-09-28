"""Consolida os dados mestres da entidade Conteúdo (RF30).

Fontes (em ordem de prioridade):
    silver_catalogo  catálogo Silver gerado pelo Apache Hop (fonte de referência)
    d1_postgres      tabela public.conteudo do Desafio 1

Etapas:
    1. M1: registros com o mesmo conteudo_id nas duas fontes são a mesma
       entidade; conflitos de atributo são resolvidos pela prioridade da fonte.
    2. M2: registros com a mesma chave de correspondência (título, tipo,
       autor, nível e descrição normalizados) são duplicatas do mesmo
       conteúdo; o registro de ouro é montado pelas regras de sobrevivência.
    3. Cada grupo recebe um identificador mestre (CM-000001). A tabela de
       correspondência é persistente, então o mesmo grupo mantém o mesmo
       identificador entre execuções.

Grava o schema mestre no PostgreSQL (sql/dados_mestres.sql) e as evidências
em dados_mestres/evidencias/.

Uso:
    python dados_mestres/consolidar_conteudo.py
    python dados_mestres/consolidar_conteudo.py --id-execucao X
"""

import argparse
import hashlib
import json
import os
import re
import sys
import unicodedata
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
import psycopg
from dotenv import load_dotenv
from psycopg.types.json import Jsonb

RAIZ_PROJETO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_PROJETO / "beam"))
from contratos import CATALOGO, ler_silver_csv  # noqa: E402

load_dotenv(RAIZ_PROJETO / ".env")

SQL_MESTRE = RAIZ_PROJETO / "sql" / "dados_mestres.sql"
DIR_EVIDENCIAS = RAIZ_PROJETO / "dados_mestres" / "evidencias"

FONTES = ("silver_catalogo", "d1_postgres")  # ordem = prioridade
ATRIBUTOS = [
    "titulo", "tipo", "categoria", "nivel", "carga_horaria_min",
    "data_publicacao", "descricao", "autor",
]
TITULACOES = {"prof", "profa", "dr", "dra", "eng", "me", "ma", "msc", "phd"}


# --- Normalização e chave de correspondência -------------------------------


def normalizar(texto):
    """Minúsculas, sem acentos e com pontuação e espaços colapsados."""
    sem_acento = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return re.sub(r"[\W_]+", " ", sem_acento.lower()).strip()


def normalizar_autor(autor):
    """Remove titulações ("Prof.", "Dra.", "Eng.") do início do nome."""
    palavras = normalizar(autor).split()
    while palavras and palavras[0] in TITULACOES:
        palavras.pop(0)
    return " ".join(palavras)


def chave_candidato(registro):
    """Título, tipo e autor: aproxima registros que podem ser o mesmo conteúdo."""
    return "|".join([
        normalizar(registro["titulo"]), normalizar(registro["tipo"]),
        normalizar_autor(registro["autor"]),
    ])


def chave_correspondencia(registro):
    """Chave de negócio (M2): candidato + nível + descrição normalizados."""
    partes = [chave_candidato(registro), normalizar(registro["nivel"]),
              normalizar(registro["descricao"])]
    return hashlib.sha256("|".join(partes).encode()).hexdigest()


# --- Carga -----------------------------------------------------------------


def carregar(conexao):
    silver = ler_silver_csv(CATALOGO)[["conteudo_id", *ATRIBUTOS]]
    with conexao.cursor() as cursor:
        cursor.execute(
            """SELECT c.conteudo_id, c.titulo, c.tipo, cat.nome, c.nivel,
                      c.carga_horaria_min, c.data_publicacao, c.descricao, c.autor
               FROM public.conteudo c
               JOIN public.categoria cat USING (categoria_id)"""
        )
        d1 = pd.DataFrame(cursor.fetchall(), columns=["conteudo_id", *ATRIBUTOS])

    registros = pd.concat(
        [silver.assign(fonte="silver_catalogo"), d1.assign(fonte="d1_postgres")],
        ignore_index=True,
    )
    registros["conteudo_id"] = registros["conteudo_id"].astype(int)
    registros["carga_horaria_min"] = registros["carga_horaria_min"].astype(int)
    registros["data_publicacao"] = pd.to_datetime(registros["data_publicacao"]).dt.date
    return registros


# --- Etapa 1: mesmo conteudo_id entre fontes (M1) --------------------------


def valores_distintos(grupo, atributo):
    return grupo[atributo].dropna().map(str).nunique() > 1


def descrever_valores(grupo, atributo):
    """Valor de cada registro do grupo, com a(s) fonte(s) de onde veio."""
    return [
        {"fonte": linha["fonte"] if "fonte" in grupo else ",".join(linha["fontes"]),
         "id_origem": int(linha["conteudo_id"]), "valor": str(linha[atributo])}
        for _, linha in grupo.iterrows()
    ]


def resolver_entre_fontes(registros):
    """Um registro de origem por conteudo_id, pela prioridade das fontes."""
    prioridade = {fonte: i for i, fonte in enumerate(FONTES)}
    ordenados = registros.assign(_p=registros["fonte"].map(prioridade)).sort_values(
        ["conteudo_id", "_p"]
    )
    origens, conflitos = [], []
    for conteudo_id, grupo in ordenados.groupby("conteudo_id", sort=True):
        registro = {"conteudo_id": conteudo_id, "fontes": list(grupo["fonte"])}
        for atributo in ATRIBUTOS:
            # Primeiro valor não nulo na ordem de prioridade das fontes.
            registro[atributo] = grupo[atributo].dropna().iloc[0]
            if valores_distintos(grupo, atributo):
                conflitos.append({
                    "conteudo_id": conteudo_id, "atributo": atributo, "nivel": "entre_fontes",
                    "valores": descrever_valores(grupo, atributo),
                    "valor_escolhido": str(registro[atributo]),
                    "regra_sobrevivencia": "prioridade da fonte: " + " > ".join(FONTES),
                })
        origens.append(registro)
    return pd.DataFrame(origens), conflitos


# --- Etapa 2: duplicatas por atributos (M2) e sobrevivência ----------------

# Regra de sobrevivência por atributo: (descrição, função sobre o grupo
# ordenado por data_publicacao e conteudo_id).
SOBREVIVENCIA = {
    "titulo": ("valor do registro sobrevivente (igual após normalização)", lambda g: g.iloc[0]),
    "tipo": ("valor do registro sobrevivente (igual após normalização)", lambda g: g.iloc[0]),
    "autor": ("valor do registro sobrevivente (igual após normalização)", lambda g: g.iloc[0]),
    "nivel": ("valor do registro sobrevivente (igual após normalização)", lambda g: g.iloc[0]),
    "descricao": ("valor do registro sobrevivente (igual após normalização)", lambda g: g.iloc[0]),
    "categoria": ("registro publicado mais recentemente (versão vigente)", lambda g: g.iloc[-1]),
    "carga_horaria_min": ("registro publicado mais recentemente (versão vigente)", lambda g: g.iloc[-1]),
    "data_publicacao": ("data mais antiga (primeira publicação do conteúdo)", lambda g: g.min()),
}
REGRA_SOBREVIVENTE = "menor data_publicacao; empate: menor conteudo_id (registro original)"


def consolidar_duplicatas(origens):
    origens = origens.assign(
        chave=origens.apply(chave_correspondencia, axis=1),
        candidato=origens.apply(chave_candidato, axis=1),
    ).sort_values(["data_publicacao", "conteudo_id"])

    grupos, conflitos = [], []
    for chave, grupo in origens.groupby("chave", sort=False):
        sobrevivente = grupo.iloc[0]
        ouro = {
            "chave_correspondencia": chave,
            "conteudo_id_canonico": int(sobrevivente["conteudo_id"]),
            "membros": [int(i) for i in grupo["conteudo_id"]],
            "fontes": {int(r["conteudo_id"]): r["fontes"] for _, r in grupo.iterrows()},
        }
        for atributo, (descricao, escolher) in SOBREVIVENCIA.items():
            ouro[atributo] = escolher(grupo[atributo])
            if len(grupo) > 1 and valores_distintos(grupo, atributo):
                conflitos.append({
                    "conteudo_id": ouro["conteudo_id_canonico"], "atributo": atributo,
                    "nivel": "entre_duplicatas",
                    "valores": descrever_valores(grupo, atributo),
                    "valor_escolhido": str(ouro[atributo]),
                    "regra_sobrevivencia": descricao,
                })
        grupos.append(ouro)

    # Mesmo título, tipo e autor, mas chave diferente: não fundidos (ex.: edições
    # de níveis diferentes). Registrados para revisão da curadoria.
    candidatos = []
    for _, grupo in origens.groupby("candidato"):
        if grupo["chave"].nunique() > 1:
            diferencas = [a for a in ("nivel", "descricao") if grupo[a].map(normalizar).nunique() > 1]
            candidatos.append({
                "conteudo_ids": sorted(int(i) for i in grupo["conteudo_id"]),
                "titulo": grupo["titulo"].iloc[0], "autor": grupo["autor"].iloc[0],
                "motivo": "diferem em " + " e ".join(diferencas),
            })
    return grupos, conflitos, candidatos


# --- Etapa 3: identificador mestre e gravação ------------------------------


def atribuir_ids(conexao, grupos):
    with conexao.cursor() as cursor:
        cursor.execute("SELECT fonte, id_origem, conteudo_mestre_id FROM mestre.conteudo_correspondencia")
        existentes = {(f, i): m for f, i, m in cursor}

        novos, reutilizados, fusoes = 0, 0, []
        for grupo in grupos:
            membros = [(f, i) for i in grupo["membros"] for f in grupo["fontes"][i]]
            anteriores = sorted({existentes[m] for m in membros if m in existentes})
            if not anteriores:
                cursor.execute("SELECT nextval('mestre.seq_conteudo_mestre')")
                grupo["conteudo_mestre_id"] = f"CM-{cursor.fetchone()[0]:06d}"
                novos += 1
            else:
                grupo["conteudo_mestre_id"] = anteriores[0]
                reutilizados += 1
                if len(anteriores) > 1:  # dois mestres passaram a ser o mesmo conteúdo
                    fusoes.append({"mantido": anteriores[0], "absorvidos": anteriores[1:]})
    return {"novos": novos, "reutilizados": reutilizados, "fusoes": fusoes}


def regra_do_membro(grupo, conteudo_id):
    if len(grupo["membros"]) > 1:
        return "M2"
    return "M1" if len(grupo["fontes"][conteudo_id]) > 1 else "UNICO"


def gravar(conexao, grupos, conflitos, id_execucao, agora):
    mestre_por_id = {i: g["conteudo_mestre_id"] for g in grupos for i in g["membros"]}
    with conexao.transaction(), conexao.cursor() as cursor:
        cursor.executemany(
            """INSERT INTO mestre.conteudo_correspondencia
               (fonte, id_origem, conteudo_mestre_id, regra_correspondencia, sobrevivente,
                primeira_vez_em, atualizado_em, id_execucao)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (fonte, id_origem) DO UPDATE SET
                   conteudo_mestre_id = EXCLUDED.conteudo_mestre_id,
                   regra_correspondencia = EXCLUDED.regra_correspondencia,
                   sobrevivente = EXCLUDED.sobrevivente,
                   atualizado_em = EXCLUDED.atualizado_em,
                   id_execucao = EXCLUDED.id_execucao""",
            [
                (fonte, i, g["conteudo_mestre_id"], regra_do_membro(g, i),
                 i == g["conteudo_id_canonico"], agora, agora, id_execucao)
                for g in grupos for i in g["membros"] for fonte in g["fontes"][i]
            ],
        )
        # Registro de ouro e conflitos refletem sempre a execução mais recente.
        cursor.execute("TRUNCATE mestre.conteudo, mestre.conteudo_conflito")
        cursor.executemany(
            """INSERT INTO mestre.conteudo
               (conteudo_mestre_id, conteudo_id_canonico, titulo, tipo, categoria, nivel,
                carga_horaria_min, data_publicacao, descricao, autor, chave_correspondencia,
                qtd_registros_origem, atualizado_em, id_execucao)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            [
                (g["conteudo_mestre_id"], g["conteudo_id_canonico"], g["titulo"], g["tipo"],
                 g["categoria"], g["nivel"], int(g["carga_horaria_min"]), g["data_publicacao"],
                 g["descricao"], g["autor"], g["chave_correspondencia"],
                 sum(len(f) for f in g["fontes"].values()), agora, id_execucao)
                for g in grupos
            ],
        )
        cursor.executemany(
            """INSERT INTO mestre.conteudo_conflito
               (conteudo_mestre_id, atributo, nivel, valores, valor_escolhido,
                regra_sobrevivencia, id_execucao)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            [
                (mestre_por_id[c["conteudo_id"]], c["atributo"], c["nivel"], Jsonb(c["valores"]),
                 c["valor_escolhido"], c["regra_sobrevivencia"], id_execucao)
                for c in conflitos
            ],
        )


# --- Evidências ------------------------------------------------------------


def formatar_markdown(ev):
    r = ev["resumo"]
    linhas = [
        "# Consolidação de dados mestres — Conteúdo",
        "",
        f"Execução `{ev['id_execucao']}` em {ev['data']}.",
        "",
        "| Indicador | Valor |",
        "|---|---:|",
        *[f"| {k} | {v} |" for k, v in r.items()],
        "",
        "## Registros conflitantes consolidados (M2)",
        "",
        "Cada grupo reúne cadastros duplicados do mesmo conteúdo, com a mesma chave de",
        "correspondência. Os atributos em conflito foram resolvidos pelas regras de",
        "sobrevivência.",
    ]
    for grupo in ev["duplicatas"]:
        linhas += [
            "",
            f"### {grupo['conteudo_mestre_id']} — {grupo['titulo']}",
            "",
            f"Registros de origem: {', '.join(map(str, grupo['membros']))} → "
            f"id canônico **{grupo['conteudo_id_canonico']}** ({REGRA_SOBREVIVENTE}).",
            "",
            "| Atributo | " + " | ".join(f"conteudo_id {i}" for i in grupo["membros"])
            + " | Registro de ouro | Regra |",
            "|---|" + "---|" * len(grupo["membros"]) + "---|---|",
        ]
        for conflito in grupo["conflitos"]:
            por_id = {v["id_origem"]: v["valor"] for v in conflito["valores"]}
            linhas.append(
                f"| {conflito['atributo']} | "
                + " | ".join(por_id.get(i, "—") for i in grupo["membros"])
                + f" | **{conflito['valor_escolhido']}** | {conflito['regra_sobrevivencia']} |"
            )
    linhas += [
        "",
        "## Candidatos não fundidos",
        "",
        "Mesmo título, tipo e autor, mas com chave de correspondência diferente. São",
        "tratados como conteúdos distintos (por exemplo, edições de níveis diferentes)",
        "e ficam listados para revisão da curadoria.",
        "",
        "| conteudo_ids | Título | Autor | Motivo |",
        "|---|---|---|---|",
        *[
            f"| {', '.join(map(str, c['conteudo_ids']))} | {c['titulo']} | {c['autor']} | {c['motivo']} |"
            for c in ev["candidatos_nao_fundidos"]
        ],
        "",
        "## Conflitos entre fontes (M1)",
        "",
        f"{len(ev['conflitos_entre_fontes'])} conflito(s) entre `silver_catalogo` e `d1_postgres` "
        "para o mesmo conteudo_id; resolvidos pela prioridade da fonte.",
    ]
    return "\n".join(linhas) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--id-execucao", default=os.environ.get("ID_EXECUCAO") or str(uuid.uuid4()))
    args = parser.parse_args(argv)
    agora = datetime.now()

    with psycopg.connect(connect_timeout=10) as conexao:
        conexao.execute(SQL_MESTRE.read_text(encoding="utf-8"))
        conexao.commit()
        registros = carregar(conexao)
        origens, conflitos_fontes = resolver_entre_fontes(registros)
        grupos, conflitos_duplicatas, candidatos = consolidar_duplicatas(origens)
        ids = atribuir_ids(conexao, grupos)
        gravar(conexao, grupos, conflitos_fontes + conflitos_duplicatas, args.id_execucao, agora)

    duplicatas = [g for g in grupos if len(g["membros"]) > 1]
    por_canonico = {}
    for conflito in conflitos_duplicatas:
        por_canonico.setdefault(conflito["conteudo_id"], []).append(conflito)
    evidencia = {
        "id_execucao": args.id_execucao,
        "data": agora.isoformat(timespec="seconds"),
        "resumo": {
            **{f"registros na fonte {f}": int((registros["fonte"] == f).sum()) for f in FONTES},
            "conteudo_ids distintos": len(origens),
            "correspondências M1 (mesmo id nas duas fontes)": int(origens["fontes"].map(len).gt(1).sum()),
            "grupos de duplicatas M2": len(duplicatas),
            "registros absorvidos por M2": sum(len(g["membros"]) - 1 for g in duplicatas),
            "conteúdos mestres": len(grupos),
            "identificadores mestres novos": ids["novos"],
            "identificadores mestres reutilizados": ids["reutilizados"],
            "fusões de mestres existentes": len(ids["fusoes"]),
            "conflitos resolvidos entre fontes": len(conflitos_fontes),
            "conflitos resolvidos entre duplicatas": len(conflitos_duplicatas),
            "candidatos não fundidos": len(candidatos),
        },
        "duplicatas": [
            {"conteudo_mestre_id": g["conteudo_mestre_id"], "titulo": g["titulo"],
             "membros": g["membros"], "conteudo_id_canonico": g["conteudo_id_canonico"],
             "conflitos": por_canonico.get(g["conteudo_id_canonico"], [])}
            for g in duplicatas
        ],
        "candidatos_nao_fundidos": candidatos,
        "conflitos_entre_fontes": conflitos_fontes,
        "fusoes": ids["fusoes"],
    }
    DIR_EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    (DIR_EVIDENCIAS / "consolidacao_conteudo.json").write_text(
        json.dumps(evidencia, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    (DIR_EVIDENCIAS / "consolidacao_conteudo.md").write_text(
        formatar_markdown(evidencia), encoding="utf-8"
    )
    for chave, valor in evidencia["resumo"].items():
        print(f"{chave}: {valor}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
