"""Configura o Apache Superset a partir do repositório (RF17, RF18).

Etapas (idempotentes: cria ou atualiza cada objeto pelo nome):
    1. PostgreSQL: usuário somente leitura superset_leitura (sql/acesso_superset.sql),
       com a senha de superset/.env, e verificação de que ele só enxerga gold.
    2. Superset, via API REST:
       - conexão com a Gold usando superset_leitura;
       - consultas salvas do SQL Lab (sql/sql_lab.sql);
       - conjuntos de dados virtuais e suas métricas;
       - gráficos e dashboard com filtros cruzados e filtros globais;
       - alerta de conversão de recomendações, com envio de e-mail ao Mailpit.
    3. Verifica a consulta de cada gráfico e grava em superset/exportacao_e_evidencias/
       a exportação do dashboard e das consultas e as evidências do alerta.

Pré-requisitos: Gold publicada (gold/publicar_gold.py) e Superset no ar
(docker compose -f superset/docker-compose.yml up -d --build).

Uso:
    python superset/configurar_superset.py
    python superset/configurar_superset.py --alerta-demonstracao   # alerta a cada minuto
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import psycopg
import requests
from dotenv import dotenv_values, load_dotenv
from psycopg import sql

RAIZ_PROJETO = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ_PROJETO / ".env")
SEGREDOS = dotenv_values(RAIZ_PROJETO / "superset" / ".env")

URL = os.environ.get("SUPERSET_URL", "http://localhost:8088")
MAILPIT = os.environ.get("MAILPIT_URL", "http://localhost:8025")
DIR_EVIDENCIAS = RAIZ_PROJETO / "superset" / "exportacao_e_evidencias"

NOME_BANCO = "Desafio Dados — Gold"
# O Superset roda em container e alcança o PostgreSQL pela rede do Desafio 1.
HOST_BANCO = "desafio_dados_postgres:5432"
SLUG_DASHBOARD = "engajamento-recomendacoes"
TITULO_DASHBOARD = "Engajamento e Recomendações — Visão Analítica"

ALERTA = {
    "nome": "Conversão de recomendações abaixo de 5%",
    "destinatario": "curadoria@plataforma-educacional.example",
    "crontab": "0 8 * * *",  # diário, 08:00 (America/Sao_Paulo)
    "limite": 5,
    "descricao": (
        "Condição: taxa de conversão (%) das recomendações vigentes < 5. "
        "Ação esperada: a curadoria revisa os parâmetros do motor de recomendação "
        "(pesos de visualização, curtida e conclusão) e prioriza conteúdos com "
        "histórico de consumo na categoria do usuário."
    ),
}


# --- 1. Usuário somente leitura --------------------------------------------


def configurar_usuario_leitura():
    with psycopg.connect(connect_timeout=10) as conexao:
        conexao.execute((RAIZ_PROJETO / "sql" / "acesso_superset.sql").read_text(encoding="utf-8"))
        conexao.execute(
            sql.SQL("ALTER ROLE superset_leitura PASSWORD {}").format(
                sql.Literal(SEGREDOS["SUPERSET_DB_SENHA"])
            )
        )

    # Verifica o acesso real do usuário: lê a gold, não lê silver nem public.
    parametros = {"user": "superset_leitura", "password": SEGREDOS["SUPERSET_DB_SENHA"]}
    verificacao = {}
    with psycopg.connect(connect_timeout=10, **parametros) as conexao:
        for objeto in ["gold.vw_kpi_mensal", "silver.interacao", "public.usuario", "mestre.conteudo_correspondencia"]:
            try:
                conexao.execute(f"SELECT 1 FROM {objeto} LIMIT 1")
                verificacao[objeto] = "permitido"
            except psycopg.errors.InsufficientPrivilege:
                verificacao[objeto] = "negado"
            conexao.rollback()
    esperado = {"gold.vw_kpi_mensal": "permitido"}
    if any(verificacao[o] != esperado.get(o, "negado") for o in verificacao):
        raise SystemExit(f"Permissões de superset_leitura inesperadas: {verificacao}")
    return verificacao


# --- Cliente da API ----------------------------------------------------------


class Superset:
    def __init__(self):
        self.sessao = requests.Session()
        self.sessao.headers["Referer"] = URL
        for _ in range(60):
            try:
                if self.sessao.get(f"{URL}/health", timeout=5).ok:
                    break
            except requests.ConnectionError:
                pass
            time.sleep(5)
        token = self.post("security/login", {
            "username": "admin", "password": SEGREDOS["SUPERSET_ADMIN_SENHA"],
            "provider": "db", "refresh": False,
        })["access_token"]
        self.sessao.headers["Authorization"] = f"Bearer {token}"
        self.sessao.headers["X-CSRFToken"] = self.get("security/csrf_token/")["result"]

    def _checar(self, resposta):
        if not resposta.ok:
            raise RuntimeError(f"{resposta.request.method} {resposta.url}: {resposta.status_code} {resposta.text[:500]}")
        return resposta

    def get(self, caminho, **kwargs):
        return self._checar(self.sessao.get(f"{URL}/api/v1/{caminho}", **kwargs)).json()

    def post(self, caminho, dados):
        return self._checar(self.sessao.post(f"{URL}/api/v1/{caminho}", json=dados)).json()

    def put(self, caminho, dados):
        return self._checar(self.sessao.put(f"{URL}/api/v1/{caminho}", json=dados)).json()

    def baixar(self, caminho):
        return self._checar(self.sessao.get(f"{URL}/api/v1/{caminho}")).content

    def listar(self, recurso, campo):
        """Todos os objetos de um recurso, indexados pelo campo de nome."""
        resultado = self.get(f"{recurso}/", params={"q": "(page_size:100)"})["result"]
        return {item[campo]: item for item in resultado}

    def salvar(self, recurso, campo, nome, dados):
        """Cria ou atualiza pelo nome; devolve o id."""
        existente = self.listar(recurso, campo).get(nome)
        if existente:
            self.put(f"{recurso}/{existente['id']}", dados)
            return existente["id"]
        return self.post(f"{recurso}/", {campo: nome, **dados})["id"]


# --- 2. Objetos do Superset ----------------------------------------------------


def ler_consultas():
    """Blocos de sql/sql_lab.sql: {nome: {titulo, finalidade, dataset_virtual, sql}}."""
    texto = (RAIZ_PROJETO / "sql" / "sql_lab.sql").read_text(encoding="utf-8")
    consultas = {}
    for bloco in re.split(r"^-- @consulta: ", texto, flags=re.M)[1:]:
        nome, corpo = bloco.split("\n", 1)
        cabecalho = re.findall(r"^-- @(\w+): (.*)$", corpo, flags=re.M)
        meta = dict(cabecalho)
        # Documentação completa: todas as linhas de comentário do bloco.
        documentacao = "\n".join(
            l[3:] for l in corpo.splitlines() if l.startswith("-- ")
        )
        consulta_sql = "\n".join(l for l in corpo.splitlines() if not l.startswith("--")).strip()
        consultas[nome.strip()] = {
            "titulo": meta["titulo"], "virtual": meta["dataset_virtual"] == "sim",
            "documentacao": documentacao, "sql": consulta_sql.rstrip(";"),
        }
    return consultas


def configurar_banco(api):
    uri = f"postgresql+psycopg2://superset_leitura:{SEGREDOS['SUPERSET_DB_SENHA']}@{HOST_BANCO}/desafio_dados"
    api.post("database/test_connection/", {"database_name": NOME_BANCO, "sqlalchemy_uri": uri})
    return api.salvar("database", "database_name", NOME_BANCO, {
        "sqlalchemy_uri": uri,
        "expose_in_sqllab": True,
        "allow_dml": False,
        "allow_ctas": False,
        "allow_cvas": False,
        "allow_run_async": False,
    })


def configurar_consultas_salvas(api, id_banco, consultas):
    ids = {}
    for nome, consulta in consultas.items():
        ids[nome] = api.salvar("saved_query", "label", consulta["titulo"], {
            "db_id": id_banco, "schema": "gold",
            "description": consulta["documentacao"], "sql": consulta["sql"] + ";",
        })
    return ids


METRICAS = {
    "vds_engajamento_interacoes": [
        ("interacoes", "COUNT(*)", "Interações", ",d"),
        ("usuarios_ativos", "COUNT(DISTINCT usuario_chave)", "Usuários ativos", ",d"),
        ("conclusoes", "SUM(conclusao)", "Conclusões", ",d"),
        ("taxa_conclusao", "SUM(conclusao) * 1.0 / NULLIF(SUM(consumo), 0)", "Taxa de conclusão", ".1%"),
        ("avaliacao_media", "AVG(avaliacao_atribuida)", "Avaliação média", ".2f"),
    ],
    "vds_conversao_recomendacao": [
        ("total_recomendacoes", "SUM(recomendacoes)", "Recomendações", ",d"),
        ("total_convertidas", "SUM(convertidas)", "Convertidas", ",d"),
        ("taxa_conversao", "SUM(convertidas) * 1.0 / NULLIF(SUM(recomendacoes), 0)", "Taxa de conversão", ".1%"),
    ],
    "lista_acao_conteudos": [
        ("conteudos", "COUNT(*)", "Conteúdos", ",d"),
    ],
    "v_evolucao_metricas": [
        ("metrica_pior", "MIN(metrica)", "Métrica (%)", ".1f"),
    ],
}
DATAHORA = {"vds_engajamento_interacoes": "data_hora", "v_evolucao_metricas": "data_execucao"}
# Rótulos exibidos nos gráficos e tabelas (verbose_name das colunas).
ROTULOS = {
    "conteudo_mestre_id": "Conteúdo mestre", "titulo": "Título", "categoria": "Categoria",
    "tipo": "Tipo", "nivel": "Nível", "usuarios": "Usuários", "interacoes": "Interações",
    "nota_media": "Nota média", "qtd_notas": "Qtd. de notas", "classificacao": "Classificação",
    "meses_publicado": "Meses publicado", "faixa_posicao": "Faixa de posição", "status": "Status",
    "recomendacoes": "Recomendações", "convertidas": "Convertidas", "concluidas": "Concluídas",
    "pontuacao_media": "Pontuação média", "mes": "Mês", "mes_geracao": "Mês de geração",
    "periodo_do_dia": "Período do dia", "dia_semana": "Dia da semana",
    "tipo_interacao": "Tipo de interação", "faixa_duracao": "Faixa de duração",
    "id_regra": "Regra", "fonte": "Fonte", "metrica": "Métrica (%)", "origem_dados": "Origem",
}
CAMPOS_COLUNA = ("id", "column_name", "verbose_name", "type", "is_dttm", "expression",
                 "filterable", "groupby", "description")


def configurar_datasets(api, id_banco, consultas):
    existentes = {
        (d["table_name"], d["schema"]): d for d in api.get("dataset/", params={"q": "(page_size:100)"})["result"]
    }
    alvos = [(n, "gold", c) for n, c in consultas.items() if c["virtual"]]
    alvos.append(("v_evolucao_metricas", "qualidade", None))  # dataset físico da qualidade

    ids = {}
    for nome, schema, consulta in alvos:
        dados = {"database": id_banco, "schema": schema, "table_name": nome}
        if consulta:
            dados["sql"] = consulta["sql"]
        if (nome, schema) in existentes:
            id_dataset = existentes[(nome, schema)]["id"]
            if consulta:
                api.put(f"dataset/{id_dataset}", {"sql": consulta["sql"]})
        else:
            id_dataset = api.post("dataset/", dados)["id"]
        api.put(f"dataset/{id_dataset}/refresh", {})

        atual = api.get(f"dataset/{id_dataset}")["result"]
        metricas = {m["metric_name"]: m for m in atual["metrics"]}
        for nome_metrica, expressao, rotulo, formato in METRICAS[nome]:
            metricas[nome_metrica] = {
                **({"id": metricas[nome_metrica]["id"]} if nome_metrica in metricas else {}),
                "metric_name": nome_metrica, "expression": expressao,
                "verbose_name": rotulo, "d3format": formato,
            }
        colunas = [
            {**{k: c[k] for k in CAMPOS_COLUNA if k in c},
             "verbose_name": ROTULOS.get(c["column_name"], c.get("verbose_name"))}
            for c in atual["columns"]
        ]
        atualizacao = {
            "description": consulta["documentacao"] if consulta else "Evolução das métricas de qualidade (RF31).",
            "columns": colunas,
            "metrics": [
                {k: v for k, v in m.items() if k in ("id", "metric_name", "expression", "verbose_name", "d3format")}
                for m in metricas.values()
            ],
        }
        if nome in DATAHORA:
            atualizacao["main_dttm_col"] = DATAHORA[nome]
        api.put(f"dataset/{id_dataset}", atualizacao)
        ids[nome] = id_dataset
    return ids


def graficos(ds):
    """Definição dos gráficos: (nome, dataset, viz_type, parâmetros)."""
    eng, conv, lista, qual = (
        ds["vds_engajamento_interacoes"], ds["vds_conversao_recomendacao"],
        ds["lista_acao_conteudos"], ds["v_evolucao_metricas"],
    )
    comum = {"adhoc_filters": [], "time_range": "No filter", "row_limit": 10000}
    return [
        ("Usuários ativos por mês", eng, "big_number", {
            **comum, "x_axis": "mes", "time_grain_sqla": "P1M", "metric": "usuarios_ativos",
            "show_trend_line": True, "start_y_axis_at_zero": True, "compare_lag": 1,
            "compare_suffix": "vs. mês anterior", "y_axis_format": "SMART_NUMBER",
            "subheader": "último mês com interações",
        }),
        ("Taxa de conclusão mensal", eng, "echarts_timeseries_line", {
            **comum, "x_axis": "mes", "time_grain_sqla": "P1M", "metrics": ["taxa_conclusao"],
            "groupby": [], "y_axis_format": ".0%", "show_legend": False, "markerEnabled": True,
            "rich_tooltip": True, "x_axis_time_format": "%b/%Y",
        }),
        ("Interações por categoria", eng, "echarts_timeseries_bar", {
            **comum, "x_axis": "categoria", "metrics": ["interacoes"], "groupby": [],
            "orientation": "horizontal", "x_axis_sort": "interacoes", "x_axis_sort_asc": True,
            "show_legend": False, "show_value": True, "y_axis_format": ",d",
        }),
        ("Taxa de conclusão por tipo de conteúdo", eng, "echarts_timeseries_bar", {
            **comum, "x_axis": "tipo", "metrics": ["taxa_conclusao"], "groupby": [],
            "x_axis_sort": "taxa_conclusao", "x_axis_sort_asc": False, "show_legend": False,
            "show_value": True, "y_axis_format": ".0%",
        }),
        ("Conversão de recomendações por categoria", conv, "echarts_timeseries_bar", {
            **comum, "x_axis": "categoria", "metrics": ["taxa_conversao"], "groupby": [],
            "orientation": "horizontal", "x_axis_sort": "taxa_conversao", "x_axis_sort_asc": True,
            "show_legend": False, "show_value": True, "y_axis_format": ".1%",
        }),
        ("Conversão por faixa de posição", conv, "table", {
            **comum, "query_mode": "aggregate", "groupby": ["faixa_posicao"],
            "metrics": ["total_recomendacoes", "total_convertidas", "taxa_conversao"],
            # Ordena pela faixa (1–3, 4–6, 7–10), não pela primeira métrica.
            "timeseries_limit_metric": None, "order_desc": False,
            "order_by_cols": [], "all_columns": [], "show_cell_bars": True,
            "table_timestamp_format": "smart_date", "server_page_length": 10,
        }),
        ("Lista de ação da curadoria", lista, "table", {
            **comum, "query_mode": "raw",
            "all_columns": ["conteudo_mestre_id", "titulo", "categoria", "tipo", "usuarios",
                            "nota_media", "classificacao"],
            "order_by_cols": [json.dumps(["usuarios", False])], "server_pagination": True,
            "server_page_length": 10, "include_search": True, "row_limit": 1000,
        }),
        ("Evolução da qualidade das interações (QD06 e QD08)", qual, "echarts_timeseries_bar", {
            # Execuções ocorrem com minutos de intervalo: um rótulo por execução
            # (categórico) é mais legível que um eixo de tempo contínuo.
            **comum, "x_axis": {
                "label": "Execução", "expressionType": "SQL",
                "sqlExpression": "to_char(data_execucao, 'DD/MM HH24:MI:SS') || ' · ' || origem_dados",
            },
            "metrics": ["metrica_pior"], "groupby": ["id_regra"], "show_value": True,
            "adhoc_filters": [
                {"expressionType": "SIMPLE", "clause": "WHERE", "subject": "id_regra",
                 "operator": "IN", "comparator": ["QD06", "QD08"]},
                {"expressionType": "SIMPLE", "clause": "WHERE", "subject": "fonte",
                 "operator": "==", "comparator": "interacoes"},
            ],
            "rich_tooltip": True, "show_legend": True, "y_axis_format": ".1f",
            "x_axis_sort_asc": True,
        }),
    ]


def contexto_consulta(id_dataset, params):
    """query_context da tabela do alerta: o e-mail do alerta usa os dados salvos."""
    return {
        "datasource": {"id": id_dataset, "type": "table"},
        "force": False,
        "queries": [{
            "columns": params["groupby"], "metrics": params["metrics"],
            "filters": [], "extras": {"having": "", "where": ""},
            "orderby": [[params["metrics"][0], False]], "row_limit": params["row_limit"],
            "time_range": "No filter", "annotation_layers": [], "url_params": {},
        }],
        "form_data": params,
        "result_format": "json",
        "result_type": "full",
    }


def configurar_dashboard(api, ds):
    id_dashboard = api.salvar("dashboard", "dashboard_title", TITULO_DASHBOARD, {
        "slug": SLUG_DASHBOARD, "published": True,
    })
    ids = {}
    for nome, id_dataset, viz, params in graficos(ds):
        params = {**params, "viz_type": viz, "datasource": f"{id_dataset}__table"}
        dados = {
            "viz_type": viz, "datasource_id": id_dataset, "datasource_type": "table",
            "params": json.dumps(params), "dashboards": [id_dashboard],
        }
        if viz == "table" and params["query_mode"] == "aggregate":
            dados["query_context"] = json.dumps(contexto_consulta(id_dataset, params))
        ids[nome] = api.salvar("chart", "slice_name", nome, dados)

    api.put(f"dashboard/{id_dashboard}", {
        "position_json": json.dumps(layout(ids)),
        "json_metadata": json.dumps(metadados_dashboard(ids, ds)),
    })
    return id_dashboard, ids


def layout(ids):
    linhas = [
        [("MARKDOWN", 12, 18, (
            "### Como ler este painel\n"
            "Dados da **camada Gold** (jan–ago/2026). Clique em uma barra de categoria ou tipo "
            "para **filtrar os demais gráficos** (filtro cruzado); use os filtros globais de "
            "**período**, **categoria** e **tipo** à esquerda. "
            "Usuário ativo = ao menos uma interação no mês; taxa de conclusão = conclusões / "
            "interações de consumo; conversão = recomendação vigente cujo conteúdo foi consumido."
        ))],
        [("Usuários ativos por mês", 4, 50), ("Taxa de conclusão mensal", 8, 50)],
        [("Interações por categoria", 6, 60), ("Taxa de conclusão por tipo de conteúdo", 6, 60)],
        [("Conversão de recomendações por categoria", 7, 60), ("Conversão por faixa de posição", 5, 60)],
        [("Lista de ação da curadoria", 7, 70), ("Evolução da qualidade das interações (QD06 e QD08)", 5, 70)],
    ]
    posicoes = {
        "DASHBOARD_VERSION_KEY": "v2",
        "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
        "GRID_ID": {"type": "GRID", "id": "GRID_ID", "children": [], "parents": ["ROOT_ID"]},
        "HEADER_ID": {"type": "HEADER", "id": "HEADER_ID", "meta": {"text": TITULO_DASHBOARD}},
    }
    for n, linha in enumerate(linhas, start=1):
        id_linha = f"ROW-{n}"
        posicoes["GRID_ID"]["children"].append(id_linha)
        posicoes[id_linha] = {
            "type": "ROW", "id": id_linha, "children": [], "parents": ["ROOT_ID", "GRID_ID"],
            "meta": {"background": "BACKGROUND_TRANSPARENT"},
        }
        for m, item in enumerate(linha, start=1):
            if item[0] == "MARKDOWN":
                _, largura, altura, texto = item
                id_item = f"MARKDOWN-{n}-{m}"
                meta = {"width": largura, "height": altura, "code": texto}
                tipo = "MARKDOWN"
            else:
                nome, largura, altura = item
                id_item = f"CHART-{ids[nome]}"
                meta = {"width": largura, "height": altura, "chartId": ids[nome], "sliceName": nome}
                tipo = "CHART"
            posicoes[id_linha]["children"].append(id_item)
            posicoes[id_item] = {
                "type": tipo, "id": id_item, "children": [],
                "parents": ["ROOT_ID", "GRID_ID", id_linha], "meta": meta,
            }
    return posicoes


def metadados_dashboard(ids, ds):
    todos = list(ids.values())
    qualidade = ids["Evolução da qualidade das interações (QD06 e QD08)"]
    negocio = [i for i in todos if i != qualidade]
    engajamento = [ids[n] for n in (
        "Usuários ativos por mês", "Taxa de conclusão mensal",
        "Interações por categoria", "Taxa de conclusão por tipo de conteúdo",
    )]

    def filtro(id_filtro, nome, tipo, coluna, escopo, controles=None, descricao=""):
        return {
            "id": id_filtro, "name": nome, "filterType": tipo, "type": "NATIVE_FILTER",
            "targets": [{"datasetId": ds["vds_engajamento_interacoes"], "column": {"name": coluna}}] if coluna else [{}],
            "controlValues": controles or {}, "defaultDataMask": {"filterState": {}, "extraFormData": {}},
            "cascadeParentIds": [], "description": descricao,
            "scope": {"rootPath": ["ROOT_ID"], "excluded": [i for i in todos if i not in escopo]},
            "chartsInScope": escopo,
        }

    selecao = {"multiSelect": True, "enableEmptyFilter": False, "defaultToFirstItem": False,
               "inverseSelection": False, "searchAllOptions": False}
    return {
        "native_filter_configuration": [
            filtro("NATIVE_FILTER-periodo", "Período", "filter_time", None, engajamento,
                   descricao="Período das interações (data_hora)."),
            filtro("NATIVE_FILTER-categoria", "Categoria", "filter_select", "categoria", negocio, selecao),
            filtro("NATIVE_FILTER-tipo", "Tipo de conteúdo", "filter_select", "tipo", negocio, selecao),
        ],
        "cross_filters_enabled": True,
        "chart_configuration": {
            str(i): {"id": i, "crossFilters": {"scope": "global", "chartsInScope": [o for o in negocio if o != i]}}
            for i in negocio
        },
        "global_chart_configuration": {
            "scope": {"rootPath": ["ROOT_ID"], "excluded": [qualidade]},
            "chartsInScope": negocio,
        },
        "color_scheme": "supersetColors",
        "refresh_frequency": 0,
        "expanded_slices": {},
        "label_colors": {},
        "timed_refresh_immune_slices": [],
    }


def configurar_alerta(api, id_banco, id_grafico, consultas, demonstracao):
    usuario = api.get("me/")["result"]
    dados = {
        "type": "Alert",
        "active": True,
        "description": ALERTA["descricao"],
        "crontab": "* * * * *" if demonstracao else ALERTA["crontab"],
        "timezone": "America/Sao_Paulo",
        "database": id_banco,
        "sql": consultas["alerta_conversao_recomendacao"]["sql"],
        "validator_type": "operator",
        "validator_config_json": {"op": "<", "threshold": ALERTA["limite"]},
        "chart": id_grafico,
        "report_format": "TEXT",
        "recipients": [{"type": "Email", "recipient_config_json": {"target": ALERTA["destinatario"]}}],
        "grace_period": 60 if demonstracao else 86400,
        "working_timeout": 3600,
        "log_retention": 90,
        "owners": [usuario["id"]],
        "creation_method": "alerts_reports",
    }
    return api.salvar("report", "name", ALERTA["nome"], dados)


def verificar_graficos(api, ids, ds):
    """Executa no Superset a consulta de cada gráfico e devolve as linhas obtidas.

    Monta a consulta a partir dos parâmetros salvos (eixo, agrupamentos,
    métricas e filtros), como o frontend faz ao renderizar o gráfico.
    """
    definicoes = {nome: (id_dataset, params) for nome, id_dataset, _, params in graficos(ds)}
    linhas = {}
    for nome, id_grafico in ids.items():
        id_dataset, params = definicoes[nome]
        colunas = list(params.get("groupby", []))
        if "x_axis" in params:
            eixo = params["x_axis"]
            if params.get("time_grain_sqla") and isinstance(eixo, str):
                eixo = {"columnType": "BASE_AXIS", "sqlExpression": eixo, "label": eixo,
                        "expressionType": "SQL", "timeGrain": params["time_grain_sqla"]}
            colunas.insert(0, eixo)
        consulta = {
            "columns": colunas if params.get("query_mode") != "raw" else params["all_columns"],
            # Modo raw: sem métricas, o Superset não agrupa as colunas.
            "metrics": (
                None if params.get("query_mode") == "raw"
                else params.get("metrics") or [params["metric"]]
            ),
            "filters": [
                {"col": f["subject"], "op": "IN" if f["operator"] == "IN" else "==", "val": f["comparator"]}
                for f in params.get("adhoc_filters", [])
            ],
            "row_limit": params.get("row_limit", 1000),
            "time_range": "No filter",
        }
        resposta = api.post("chart/data", {
            "datasource": {"id": id_dataset, "type": "table"},
            "queries": [consulta], "result_format": "json", "result_type": "full",
        })
        linhas[nome] = resposta["result"][0]["rowcount"]
    vazios = [n for n, total in linhas.items() if not total]
    if vazios:
        raise SystemExit(f"Gráficos sem dados: {vazios}")
    return linhas


def registrar_evidencias_alerta(api, id_alerta):
    """Salva o histórico de execuções do alerta e o último e-mail recebido no Mailpit."""
    destino = DIR_EVIDENCIAS / "alerta"
    destino.mkdir(parents=True, exist_ok=True)
    logs = api.get(f"report/{id_alerta}/log/", params={
        "q": "(order_column:start_dttm,order_direction:desc,page_size:20)"
    })["result"]
    execucoes = [
        {"inicio": l["start_dttm"], "fim": l["end_dttm"], "estado": l["state"],
         "valor_avaliado": l["value"], "erro": l["error_message"]}
        for l in logs if l["state"] != "Working"
    ]
    alerta = api.get(f"report/{id_alerta}")["result"]
    (destino / "execucoes_alerta.json").write_text(json.dumps({
        "alerta": {
            "nome": alerta["name"], "descricao": alerta["description"], "crontab": alerta["crontab"],
            "timezone": alerta["timezone"], "sql": alerta["sql"],
            "condicao": f"valor {alerta['validator_config_json']}",
            "destinatarios": [r["recipient_config_json"] for r in alerta["recipients"]],
            "formato": alerta["report_format"],
        },
        "execucoes": execucoes,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        mensagens = requests.get(f"{MAILPIT}/api/v1/messages", timeout=5).json()["messages"]
    except requests.RequestException:
        mensagens = []
    if mensagens:
        mensagem = requests.get(f"{MAILPIT}/api/v1/message/{mensagens[0]['ID']}", timeout=5).json()
        cabecalho = (
            f"<!-- Assunto: {mensagem['Subject']} | Para: "
            f"{', '.join(t['Address'] for t in mensagem['To'])} | Data: {mensagem['Date']} -->\n"
        )
        (destino / "email_alerta.html").write_text(cabecalho + mensagem["HTML"], encoding="utf-8")
    return len(execucoes), len(mensagens)


def exportar(api, id_dashboard, ids_consultas):
    DIR_EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    arquivos = {
        "dashboard_engajamento_recomendacoes.zip": f"dashboard/export/?q=!({id_dashboard})",
        "consultas_sql_lab.zip": f"saved_query/export/?q=!({','.join(map(str, ids_consultas.values()))})",
    }
    for arquivo, caminho in arquivos.items():
        (DIR_EVIDENCIAS / arquivo).write_bytes(api.baixar(caminho))
    return list(arquivos)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--alerta-demonstracao", action="store_true",
                        help="avalia o alerta a cada minuto (demonstração); o padrão é diário às 08:00")
    args = parser.parse_args(argv)

    permissoes = configurar_usuario_leitura()
    print(f"superset_leitura: {permissoes}")

    api = Superset()
    consultas = ler_consultas()
    id_banco = configurar_banco(api)
    ids_consultas = configurar_consultas_salvas(api, id_banco, consultas)
    ds = configurar_datasets(api, id_banco, consultas)
    id_dashboard, ids_graficos = configurar_dashboard(api, ds)
    id_alerta = configurar_alerta(
        api, id_banco, ids_graficos["Conversão por faixa de posição"], consultas, args.alerta_demonstracao
    )
    linhas_graficos = verificar_graficos(api, ids_graficos, ds)
    exportados = exportar(api, id_dashboard, ids_consultas)
    execucoes, emails = registrar_evidencias_alerta(api, id_alerta)

    print(f"Banco {id_banco}; consultas salvas {list(ids_consultas.values())}; datasets {ds}")
    print(f"Dashboard {URL}/superset/dashboard/{SLUG_DASHBOARD}/ com gráficos {ids_graficos}")
    print(f"Linhas por gráfico: {linhas_graficos}")
    print(f"Alerta {id_alerta} ({'a cada minuto' if args.alerta_demonstracao else ALERTA['crontab']})")
    print(f"Alerta: {execucoes} execução(ões) registrada(s); {emails} e-mail(s) no Mailpit")
    print(f"Exportados em {DIR_EVIDENCIAS.relative_to(RAIZ_PROJETO)}: {exportados}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
