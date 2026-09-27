r"""Pipeline Apache Beam: engajamento mensal por categoria (RF25).

Lê as interações e o catálogo da Silver em Parquet (gerados por
beam/exportar_parquet.py), agrega por mês e categoria de conteúdo e grava o
resultado em Parquet para a camada Gold. A mesma regra roda no DirectRunner
e no Apache Spark, pelo PortableRunner e o job server do Beam
(ver beam/spark/docker-compose.yml).

Os caminhos são relativos à raiz do projeto, que é o diretório de trabalho
tanto na máquina local quanto no container de workers do Beam (/projeto).

Uso:
    python beam/pipeline.py
    python beam/pipeline.py --runner PortableRunner --job_endpoint localhost:8099 \
        --artifact_endpoint localhost:8098 --environment_type EXTERNAL \
        --environment_config localhost:50000 --environment_cache_millis 60000 \
        --rotulo spark
"""

import argparse
import json
import os
import platform
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

import apache_beam as beam
import pyarrow as pa
import pyarrow.parquet as pq
from apache_beam.io.parquetio import ReadFromParquet, WriteToParquet
from apache_beam.metrics import Metrics
from apache_beam.metrics.metric import MetricsFilter
from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions

RAIZ_PROJETO = Path(__file__).resolve().parent.parent

ENTRADA_PADRAO = "dados/silver/parquet"
SAIDA_PADRAO = "dados/gold/engajamento_categoria_mensal"
DIR_EVIDENCIAS = RAIZ_PROJETO / "beam" / "evidencias"

RUNNERS_LOCAIS = {"DirectRunner", "PrismRunner", "FnApiRunner"}

SEM_CATEGORIA = "Não catalogado"
TIPOS_CONSUMO = {"início", "visualização", "conclusão"}

ESQUEMA_SAIDA = pa.schema(
    [
        pa.field("ano_mes", pa.string(), nullable=False),
        pa.field("categoria", pa.string(), nullable=False),
        pa.field("total_interacoes", pa.int64(), nullable=False),
        pa.field("usuarios_ativos", pa.int64(), nullable=False),
        pa.field("conteudos_consumidos", pa.int64(), nullable=False),
        pa.field("interacoes_consumo", pa.int64(), nullable=False),
        pa.field("conclusoes", pa.int64(), nullable=False),
        pa.field("taxa_conclusao", pa.float64()),
        pa.field("percentual_conclusao_medio", pa.float64(), nullable=False),
        pa.field("tempo_consumido_total", pa.float64(), nullable=False),
        pa.field("curtidas", pa.int64(), nullable=False),
        pa.field("compartilhamentos", pa.int64(), nullable=False),
        pa.field("avaliacoes", pa.int64(), nullable=False),
        pa.field("avaliacao_media", pa.float64()),
        pa.field("id_execucao", pa.string(), nullable=False),
        pa.field("runtime", pa.string(), nullable=False),
    ]
)

COLUNAS_INTERACAO = [
    "usuario_id",
    "conteudo_id",
    "tipo_interacao",
    "data_hora",
    "tempo_consumido",
    "percentual_conclusao",
    "avaliacao_atribuida",
]


class ChavearPorMesCategoria(beam.DoFn):
    """Associa cada interação à chave (ano_mes, categoria)."""

    def __init__(self):
        self.lidas = Metrics.counter("engajamento", "interacoes_lidas")
        self.sem_categoria = Metrics.counter("engajamento", "interacoes_sem_categoria")

    def process(self, interacao, categorias):
        self.lidas.inc()
        categoria = categorias.get(interacao["conteudo_id"])
        if categoria is None:
            self.sem_categoria.inc()
            categoria = SEM_CATEGORIA
        # Mesma regra da partição ano_mes da exportação Parquet.
        ano_mes = interacao["data_hora"].strftime("%Y-%m")
        yield (ano_mes, categoria), interacao


class EngajamentoFn(beam.CombineFn):
    """Acumula as medidas de engajamento de um grupo (mês, categoria).

    As somas e os conjuntos são combináveis em qualquer ordem, o que permite
    ao runtime agregar parcialmente em cada worker e unir os resultados.
    """

    def create_accumulator(self):
        return {
            "total_interacoes": 0,
            "usuarios": set(),
            "conteudos": set(),
            "interacoes_consumo": 0,
            "conclusoes": 0,
            "soma_percentual": 0.0,
            "tempo_consumido_total": 0.0,
            "curtidas": 0,
            "compartilhamentos": 0,
            "avaliacoes": 0,
            "soma_avaliacao": 0.0,
        }

    def add_input(self, acc, interacao):
        tipo = interacao["tipo_interacao"]
        acc["total_interacoes"] += 1
        acc["usuarios"].add(interacao["usuario_id"])
        acc["conteudos"].add(interacao["conteudo_id"])
        acc["interacoes_consumo"] += tipo in TIPOS_CONSUMO
        acc["conclusoes"] += tipo == "conclusão"
        acc["curtidas"] += tipo == "curtida"
        acc["compartilhamentos"] += tipo == "compartilhamento"
        acc["soma_percentual"] += interacao["percentual_conclusao"]
        acc["tempo_consumido_total"] += interacao["tempo_consumido"]
        if interacao["avaliacao_atribuida"] is not None:
            acc["avaliacoes"] += 1
            acc["soma_avaliacao"] += interacao["avaliacao_atribuida"]
        return acc

    def merge_accumulators(self, accs):
        accs = iter(accs)
        resultado = next(accs)
        for acc in accs:
            for campo, valor in acc.items():
                if isinstance(valor, set):
                    resultado[campo] |= valor
                else:
                    resultado[campo] += valor
        return resultado

    def extract_output(self, acc):
        total = acc["total_interacoes"]
        consumo = acc["interacoes_consumo"]
        return {
            "total_interacoes": total,
            "usuarios_ativos": len(acc["usuarios"]),
            "conteudos_consumidos": len(acc["conteudos"]),
            "interacoes_consumo": consumo,
            "conclusoes": acc["conclusoes"],
            "taxa_conclusao": round(acc["conclusoes"] / consumo, 4) if consumo else None,
            "percentual_conclusao_medio": round(acc["soma_percentual"] / total, 2),
            "tempo_consumido_total": round(acc["tempo_consumido_total"], 2),
            "curtidas": acc["curtidas"],
            "compartilhamentos": acc["compartilhamentos"],
            "avaliacoes": acc["avaliacoes"],
            "avaliacao_media": (
                round(acc["soma_avaliacao"] / acc["avaliacoes"], 2) if acc["avaliacoes"] else None
            ),
        }


def construir(p, entrada, saida, id_execucao, runtime, caminho=lambda c: c):
    categorias = (
        p
        | "Ler catálogo" >> ReadFromParquet(
            caminho(f"{entrada}/catalogo/*.parquet"),
            columns=["conteudo_id", "categoria"],
            validate=False,
        )
        | "Conteúdo → categoria" >> beam.Map(lambda c: (c["conteudo_id"], c["categoria"]))
    )

    return (
        p
        | "Ler interações" >> ReadFromParquet(
            caminho(f"{entrada}/interacoes/*/*.parquet"),
            columns=COLUNAS_INTERACAO,
            validate=False,
        )
        | "Chavear por mês e categoria" >> beam.ParDo(
            ChavearPorMesCategoria(), categorias=beam.pvalue.AsDict(categorias)
        )
        | "Agregar engajamento" >> beam.CombinePerKey(EngajamentoFn())
        | "Montar linha Gold" >> beam.MapTuple(
            lambda chave, medidas: {
                "ano_mes": chave[0],
                "categoria": chave[1],
                **medidas,
                "id_execucao": id_execucao,
                "runtime": runtime,
            }
        )
        | "Gravar Parquet" >> WriteToParquet(
            caminho(f"{saida}/parte"),
            ESQUEMA_SAIDA,
            file_name_suffix=".parquet",
            num_shards=1,
            codec="snappy",
        )
    )


def contar_linhas(padrao):
    arquivos = sorted(RAIZ_PROJETO.glob(padrao))
    return sum(pq.read_metadata(a).num_rows for a in arquivos), len(arquivos)


def ler_metricas(resultado):
    try:
        consulta = resultado.metrics().query(MetricsFilter().with_namespace("engajamento"))
    except Exception as erro:  # nem todo runner portátil expõe métricas
        return {"indisponivel": str(erro)}
    # Contadores que nunca foram incrementados não aparecem na consulta.
    metricas = {"interacoes_lidas": 0, "interacoes_sem_categoria": 0}
    # O runner do Spark só informa valores tentados (attempted), não confirmados.
    metricas.update(
        {
            m.key.metric.name: m.committed if m.committed is not None else m.attempted
            for m in consulta["counters"]
        }
    )
    return metricas


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--entrada", default=ENTRADA_PADRAO, help="Parquet da Silver (relativo à raiz)")
    parser.add_argument("--saida", default=SAIDA_PADRAO, help="destino na Gold (relativo à raiz)")
    parser.add_argument("--id-execucao", default=os.environ.get("ID_EXECUCAO") or str(uuid.uuid4()))
    parser.add_argument("--rotulo", help="nome do runtime nas evidências (padrão: derivado do runner)")
    args, opcoes_beam = parser.parse_known_args(argv)

    os.chdir(RAIZ_PROJETO)
    opcoes = PipelineOptions(opcoes_beam)
    runner = opcoes.view_as(StandardOptions).runner or "DirectRunner"
    rotulo = args.rotulo or runner.removesuffix("Runner").lower()

    entrada_linhas, entrada_arquivos = contar_linhas(f"{args.entrada}/interacoes/*/*.parquet")
    print(f"[{rotulo}] {entrada_linhas} interações em {entrada_arquivos} arquivo(s) Parquet", flush=True)

    inicio = datetime.now()
    cronometro = time.perf_counter()
    p = beam.Pipeline(options=opcoes)
    # Os padrões de arquivo são resolvidos nos workers. O sistema de arquivos
    # local do Beam no Windows só reconhece a barra invertida; workers Linux usam "/".
    caminho = os.path.normpath if runner in RUNNERS_LOCAIS else (lambda c: c)
    construir(p, args.entrada, args.saida, args.id_execucao, rotulo, caminho)
    resultado = p.run()
    estado = resultado.wait_until_finish()
    duracao = time.perf_counter() - cronometro

    saida_linhas, saida_arquivos = contar_linhas(f"{args.saida}/*.parquet")
    evidencia = {
        "id_execucao": args.id_execucao,
        "runtime": rotulo,
        "runner": runner,
        "estado": str(estado),
        "inicio": inicio.isoformat(timespec="seconds"),
        "duracao_s": round(duracao, 3),
        "entrada": {"caminho": args.entrada, "linhas": entrada_linhas, "arquivos": entrada_arquivos},
        "saida": {"caminho": args.saida, "linhas": saida_linhas, "arquivos": saida_arquivos},
        "metricas": ler_metricas(resultado),
        "opcoes_beam": opcoes.get_all_options(drop_default=True),
        "versoes": {
            "python": sys.version.split()[0],
            "apache_beam": beam.__version__,
            "pyarrow": pa.__version__,
            "sistema": platform.platform(),
        },
    }
    DIR_EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    (DIR_EVIDENCIAS / f"execucao_{rotulo}_{entrada_linhas}.json").write_text(
        json.dumps(evidencia, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(evidencia, ensure_ascii=False, indent=2, default=str))
    return 0 if str(estado) == "DONE" else 1


if __name__ == "__main__":
    sys.exit(main())
