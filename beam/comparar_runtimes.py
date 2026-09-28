"""Compara as execuções do pipeline Beam no DirectRunner e no Spark (RF25).

Lê as evidências beam/evidencias/execucao_<runtime>_<linhas>.json geradas por
beam/pipeline.py, confere se as saídas dos dois runtimes são iguais para o
mesmo volume de entrada e registra volume, tempo e configuração em
beam/evidencias/comparacao_runtimes.md. Se a UI do Spark estiver acessível,
guarda também o estado do cluster (aplicações e workers).

Uso:
    python beam/comparar_runtimes.py
"""

import json
import os
import urllib.request
from collections import defaultdict

import pandas as pd

from pipeline import DIR_EVIDENCIAS, ESQUEMA_SAIDA, RAIZ_PROJETO

CHAVE = ["ano_mes", "categoria"]
AUDITORIA = {"id_execucao", "runtime"}
SPARK_UI = os.environ.get("SPARK_UI_URL", "http://localhost:8090")


def carregar_evidencias():
    por_volume = defaultdict(dict)
    for arquivo in sorted(DIR_EVIDENCIAS.glob("execucao_*_*.json")):
        evidencia = json.loads(arquivo.read_text(encoding="utf-8"))
        por_volume[evidencia["entrada"]["linhas"]][evidencia["runtime"]] = evidencia
    return por_volume


def ler_saida(evidencia):
    df = pd.read_parquet(RAIZ_PROJETO / evidencia["saida"]["caminho"])
    return df.sort_values(CHAVE).reset_index(drop=True)


def comparar(a, b):
    """Compara as medidas de negócio, ignorando os campos de auditoria."""
    if len(a) != len(b) or not a[CHAVE].equals(b[CHAVE]):
        return {"iguais": False, "motivo": "grupos (ano_mes, categoria) diferentes"}

    divergentes = {}
    for campo in ESQUEMA_SAIDA:
        if campo.name in AUDITORIA or campo.name in CHAVE:
            continue
        x, y = a[campo.name].astype(float), b[campo.name].astype(float)
        diferenca = (x - y).abs().max(skipna=True)
        mesmos_nulos = x.isna().equals(y.isna())
        if not mesmos_nulos or (pd.notna(diferenca) and diferenca > 1e-9):
            divergentes[campo.name] = float(diferenca)
    return {"iguais": not divergentes, "divergentes": divergentes}


def estado_spark():
    try:
        with urllib.request.urlopen(f"{SPARK_UI}/json/", timeout=5) as resposta:
            estado = json.load(resposta)
    except OSError:
        return None
    return {
        "url": estado["url"],
        "status": estado["status"],
        "workers": [
            {"host": w["host"], "cores": w["cores"], "memoria_mb": w["memory"], "estado": w["state"]}
            for w in estado["workers"]
        ],
        "aplicacoes_concluidas": [
            {"nome": a["name"], "cores": a["cores"], "duracao_ms": a["duration"], "estado": a["state"]}
            for a in estado["completedapps"]
        ],
    }


def formatar_markdown(resultados, spark):
    linhas = [
        "# Execução do pipeline Beam: DirectRunner × Spark",
        "",
        "Regra: engajamento mensal por categoria (`beam/pipeline.py`), lendo a Silver em",
        "Parquet e gravando Parquet. A comparação ignora os campos de auditoria",
        "(`id_execucao`, `runtime`).",
        "",
        "| Linhas de entrada | Runtime | Estado | Duração | Interações lidas | Linhas de saída | Saídas iguais |",
        "|---:|---|---|---:|---:|---:|---|",
    ]
    for r in resultados:
        for runtime, ev in r["execucoes"].items():
            linhas.append(
                f"| {r['linhas']:,} | {runtime} | {ev['estado']} | {ev['duracao_s']:.1f} s "
                f"| {ev['metricas'].get('interacoes_lidas', '—'):,} | {ev['saida']['linhas']} "
                f"| {'sim' if r['comparacao']['iguais'] else 'NÃO'} |".replace(",", ".")
            )

    linhas += ["", "## Configuração", ""]
    for r in resultados:
        for runtime, ev in r["execucoes"].items():
            opcoes = ", ".join(f"`{k}={v}`" for k, v in ev["opcoes_beam"].items())
            linhas.append(f"- **{runtime}** ({r['linhas']:,} linhas): {opcoes}".replace(",", ".", 1))
    versoes = next(iter(resultados[0]["execucoes"].values()))["versoes"]
    linhas.append(
        f"- Cliente: Python {versoes['python']}, Apache Beam {versoes['apache_beam']}, "
        f"pyarrow {versoes['pyarrow']}, {versoes['sistema']}"
    )

    if spark:
        linhas += [
            "",
            "## Cluster Spark",
            "",
            f"- Master `{spark['url']}` ({spark['status']}), "
            f"{len(spark['workers'])} workers: "
            + ", ".join(f"{w['host']} ({w['cores']} cores, {w['memoria_mb']} MB)" for w in spark["workers"]),
            "",
            "| Aplicação | Cores | Duração | Estado |",
            "|---|---:|---:|---|",
        ]
        for app in spark["aplicacoes_concluidas"]:
            linhas.append(
                f"| {app['nome']} | {app['cores']} | {app['duracao_ms'] / 1000:.1f} s | {app['estado']} |"
            )
    return "\n".join(linhas) + "\n"


def main():
    resultados = []
    for linhas, execucoes in sorted(carregar_evidencias().items()):
        if {"direct", "spark"} - execucoes.keys():
            print(f"{linhas} linhas: falta execução de {sorted({'direct', 'spark'} - execucoes.keys())}")
            continue
        comparacao = comparar(ler_saida(execucoes["direct"]), ler_saida(execucoes["spark"]))
        resultados.append({"linhas": linhas, "comparacao": comparacao, "execucoes": execucoes})
        print(f"{linhas} linhas: saídas {'iguais' if comparacao['iguais'] else 'DIFERENTES'} {comparacao}")

    if not resultados:
        raise SystemExit("Nenhum par de execuções direct/spark encontrado em beam/evidencias.")

    spark = estado_spark()
    (DIR_EVIDENCIAS / "comparacao_runtimes.json").write_text(
        json.dumps(
            {"resultados": [{k: v for k, v in r.items() if k != "execucoes"} for r in resultados],
             "cluster_spark": spark},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (DIR_EVIDENCIAS / "comparacao_runtimes.md").write_text(
        formatar_markdown(resultados, spark), encoding="utf-8"
    )
    return 0 if all(r["comparacao"]["iguais"] for r in resultados) else 1


if __name__ == "__main__":
    raise SystemExit(main())
