"""Compara tamanho e tempo de leitura de CSV e Parquet (RF24).

Usa o mesmo recorte de dados nos três formatos: o arquivo Silver de
interações (CSV gerado pelo Apache Hop), o Parquet particionado por ano_mes
e um Parquet em arquivo único, para medir o custo do particionamento.

Cenários de leitura:
    completa  lê todas as colunas com os tipos do contrato;
    seletiva  lê 3 colunas de um único mês, como uma consulta de KPI mensal.

Como a Silver tem poucas linhas, o experimento também é repetido com o
recorte replicado (--fatores), gerado em um diretório temporário.

Uso:
    python beam/benchmark_parquet.py
    python beam/benchmark_parquet.py --fatores 1 100 1000 --repeticoes 7
"""

import argparse
import json
import os
import platform
import statistics
import sys
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from contratos import COLUNA_PARTICAO, INTERACOES, RAIZ_PROJETO, ler_silver_csv, parquet_home
from exportar_parquet import COMPRESSAO, exportar, montar_tabela

DIR_EVIDENCIAS = RAIZ_PROJETO / "beam" / "evidencias"
COLUNAS_SELETIVAS = ["conteudo_id", "tipo_interacao", "percentual_conclusao"]


def replicar_csv(origem, destino, fator):
    """Replica o recorte, deslocando usuario_id para não gerar linhas idênticas."""
    df = pd.read_csv(origem, sep=INTERACOES.separador, dtype=str, keep_default_na=False)
    base = df["usuario_id"].astype(int)
    passo = int(base.max()) + 1
    partes = [df.assign(usuario_id=(base + i * passo).astype(str)) for i in range(fator)]
    pd.concat(partes, ignore_index=True).to_csv(
        destino, sep=INTERACOES.separador, index=False, encoding="utf-8"
    )


def tamanho(caminho):
    caminho = Path(caminho)
    if caminho.is_file():
        return caminho.stat().st_size
    return sum(a.stat().st_size for a in caminho.rglob("*.parquet"))


def cronometrar(funcao, repeticoes):
    funcao()  # aquecimento: cache de disco e importações
    tempos = []
    for _ in range(repeticoes):
        inicio = time.perf_counter()
        linhas = len(funcao())
        tempos.append(time.perf_counter() - inicio)
    return {
        "linhas": linhas,
        "mediana_s": round(statistics.median(tempos), 4),
        "min_s": round(min(tempos), 4),
        "max_s": round(max(tempos), 4),
    }


def leitores(csv, parquet_particionado, parquet_unico, mes):
    inicio_mes = pd.Timestamp(f"{mes}-01")
    fim_mes = inicio_mes + pd.offsets.MonthBegin(1)

    def csv_seletiva():
        df = pd.read_csv(
            csv, sep=INTERACOES.separador, usecols=[*COLUNAS_SELETIVAS, "data_hora"]
        )
        return df.loc[df["data_hora"].str.startswith(mes), COLUNAS_SELETIVAS]

    return {
        "completa": {
            "csv": lambda: ler_silver_csv(INTERACOES, csv),
            "parquet_particionado": lambda: pd.read_parquet(parquet_particionado),
            "parquet_unico": lambda: pd.read_parquet(parquet_unico),
        },
        "seletiva": {
            "csv": csv_seletiva,
            "parquet_particionado": lambda: pd.read_parquet(
                parquet_particionado,
                columns=COLUNAS_SELETIVAS,
                filters=[(COLUNA_PARTICAO, "=", mes)],
            ),
            "parquet_unico": lambda: pd.read_parquet(
                parquet_unico,
                columns=COLUNAS_SELETIVAS,
                filters=[("data_hora", ">=", inicio_mes), ("data_hora", "<", fim_mes)],
            ),
        },
    }


def medir(fator, repeticoes, mes, temporario):
    id_execucao = f"benchmark-{uuid.uuid4()}"
    if fator == 1:
        csv = INTERACOES.caminho
        parquet_particionado = parquet_home() / INTERACOES.nome
        if not parquet_particionado.exists():
            raise SystemExit("Execute antes: python beam/exportar_parquet.py interacoes")
    else:
        csv = temporario / f"interacoes_x{fator}.csv"
        replicar_csv(INTERACOES.caminho, csv, fator)
        exportar(INTERACOES, temporario / f"x{fator}", id_execucao, origem=csv)
        parquet_particionado = temporario / f"x{fator}" / INTERACOES.nome

    parquet_unico = temporario / f"interacoes_x{fator}_unico.parquet"
    tabela = montar_tabela(INTERACOES, csv, id_execucao)
    pq.write_table(tabela, parquet_unico, compression=COMPRESSAO)

    tamanhos = {
        "csv": tamanho(csv),
        "parquet_particionado": tamanho(parquet_particionado),
        "parquet_unico": tamanho(parquet_unico),
    }
    tempos = {
        cenario: {formato: cronometrar(ler, repeticoes) for formato, ler in formatos.items()}
        for cenario, formatos in leitores(csv, parquet_particionado, parquet_unico, mes).items()
    }

    # Os três formatos precisam devolver o mesmo recorte em cada cenário.
    for cenario, resultados in tempos.items():
        if len({r["linhas"] for r in resultados.values()}) != 1:
            raise RuntimeError(f"fator {fator}, cenário {cenario}: contagens divergentes {resultados}")

    return {
        "fator": fator,
        "linhas": tabela.num_rows,
        "arquivos_particionado": len(list(Path(parquet_particionado).rglob("*.parquet"))),
        "bytes": tamanhos,
        "tempos": tempos,
    }


def formatar_markdown(evidencia):
    mb = lambda b: f"{b / 1024 / 1024:.2f} MB" if b >= 1024 * 1024 else f"{b / 1024:.1f} KB"
    ms = lambda s: f"{s * 1000:.1f} ms"
    linhas = [
        "# Benchmark CSV × Parquet — interações Silver",
        "",
        f"- Execução: `{evidencia['id_execucao']}` em {evidencia['data']}",
        f"- Ambiente: {evidencia['ambiente']['sistema']}, {evidencia['ambiente']['cpus']} CPUs, "
        f"Python {evidencia['ambiente']['python']}, pyarrow {evidencia['ambiente']['pyarrow']}, "
        f"pandas {evidencia['ambiente']['pandas']}",
        f"- Compressão Parquet: {evidencia['compressao']}; mês da leitura seletiva: {evidencia['mes_seletivo']}",
        f"- Repetições por medição: {evidencia['repeticoes']} (após 1 aquecimento); tempos = mediana",
        "",
    ]
    for r in evidencia["resultados"]:
        linhas += [
            f"## Fator {r['fator']} — {r['linhas']:,} linhas".replace(",", "."),
            "",
            "| Formato | Tamanho | % do CSV | Leitura completa | Leitura seletiva |",
            "|---|---:|---:|---:|---:|",
        ]
        for formato in ("csv", "parquet_particionado", "parquet_unico"):
            nome = formato
            if formato == "parquet_particionado":
                nome = f"parquet_particionado ({r['arquivos_particionado']} arquivos)"
            linhas.append(
                f"| {nome} | {mb(r['bytes'][formato])} "
                f"| {100 * r['bytes'][formato] / r['bytes']['csv']:.0f}% "
                f"| {ms(r['tempos']['completa'][formato]['mediana_s'])} "
                f"| {ms(r['tempos']['seletiva'][formato]['mediana_s'])} |"
            )
        linhas.append("")
    return "\n".join(linhas)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fatores", nargs="+", type=int, default=[1, 1000])
    parser.add_argument("--repeticoes", type=int, default=5)
    parser.add_argument("--mes", default="2026-03", help="mês (AAAA-MM) da leitura seletiva")
    args = parser.parse_args(argv)

    evidencia = {
        "id_execucao": str(uuid.uuid4()),
        "data": datetime.now().isoformat(timespec="seconds"),
        "ambiente": {
            "sistema": platform.platform(),
            "processador": platform.processor(),
            "cpus": os.cpu_count(),
            "python": sys.version.split()[0],
            "pyarrow": pa.__version__,
            "pandas": pd.__version__,
        },
        "compressao": COMPRESSAO,
        "repeticoes": args.repeticoes,
        "mes_seletivo": args.mes,
        "resultados": [],
    }
    with tempfile.TemporaryDirectory(prefix="benchmark_parquet_") as temporario:
        for fator in args.fatores:
            print(f"Medindo fator {fator}...", flush=True)
            evidencia["resultados"].append(
                medir(fator, args.repeticoes, args.mes, Path(temporario))
            )

    DIR_EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    (DIR_EVIDENCIAS / "benchmark_parquet.json").write_text(
        json.dumps(evidencia, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    markdown = formatar_markdown(evidencia)
    (DIR_EVIDENCIAS / "benchmark_parquet.md").write_text(markdown, encoding="utf-8")
    print(markdown)


if __name__ == "__main__":
    main()
