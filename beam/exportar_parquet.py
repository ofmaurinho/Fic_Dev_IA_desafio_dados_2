"""Exporta a camada Silver para Parquet (RF24).

Lê os arquivos Silver gerados pelo Apache Hop, aplica os tipos do contrato
(beam/contratos.py) e grava um conjunto Parquet por entidade em PARQUET_HOME:

    interacoes/ano_mes=AAAA-MM/parte-0.parquet   particionado por mês da interação
    comentarios/ano_mes=AAAA-MM/parte-0.parquet  particionado por mês do comentário
    catalogo/parte-0.parquet                     dimensão pequena, sem partição

A gravação é feita em um diretório temporário e só substitui o conjunto
anterior depois de validar a quantidade de linhas e o esquema, evitando que
um consumidor leia uma exportação parcial.

Uso:
    python beam/exportar_parquet.py                  # todos os conjuntos
    python beam/exportar_parquet.py interacoes       # apenas os informados
    python beam/exportar_parquet.py --id-execucao X  # correlaciona com o workflow
"""

import argparse
import json
import logging
import os
import shutil
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq

from contratos import (
    COLUNA_PARTICAO,
    CONTRATOS,
    RAIZ_PROJETO,
    adicionar_particao,
    ler_silver_csv,
    parquet_home,
)

COMPRESSAO = "snappy"
ARQUIVO_EVIDENCIA = RAIZ_PROJETO / "beam" / "evidencias" / "exportacao_parquet.json"

log = logging.getLogger("exportar_parquet")


def caminho_relativo(caminho):
    """Registra caminhos relativos ao projeto para não versionar caminhos locais."""
    caminho = Path(caminho).resolve()
    try:
        return caminho.relative_to(RAIZ_PROJETO).as_posix()
    except ValueError:
        return caminho.as_posix()


def montar_tabela(contrato, origem, id_execucao):
    df = ler_silver_csv(contrato, origem)
    esquema = contrato.esquema
    if contrato.coluna_data_particao:
        df = adicionar_particao(df, contrato)
        esquema = esquema.append(pa.field(COLUNA_PARTICAO, pa.string(), nullable=False))

    metadados = {
        "camada": "silver",
        "conjunto": contrato.nome,
        "arquivo_origem": contrato.arquivo,
        "id_execucao_exportacao": id_execucao,
        "exportado_em": datetime.now().isoformat(timespec="seconds"),
    }
    tabela = pa.Table.from_pandas(df, schema=esquema, preserve_index=False)
    # Substitui os metadados do pandas pelos de auditoria da exportação.
    return tabela.replace_schema_metadata(metadados)


def gravar(tabela, contrato, diretorio):
    particionado = contrato.coluna_data_particao is not None
    ds.write_dataset(
        tabela,
        diretorio,
        format="parquet",
        partitioning=[COLUNA_PARTICAO] if particionado else None,
        partitioning_flavor="hive" if particionado else None,
        basename_template="parte-{i}.parquet",
        file_options=ds.ParquetFileFormat().make_write_options(compression=COMPRESSAO),
        existing_data_behavior="error",
    )


def validar(diretorio, tabela, contrato):
    """Confere linhas e esquema gravados antes de publicar o conjunto."""
    arquivos = sorted(Path(diretorio).rglob("*.parquet"))
    linhas = sum(pq.read_metadata(a).num_rows for a in arquivos)
    if linhas != tabela.num_rows:
        raise RuntimeError(
            f"{contrato.nome}: {linhas} linhas gravadas, {tabela.num_rows} esperadas"
        )

    for arquivo in arquivos:
        gravado = pq.read_schema(arquivo).remove_metadata()
        if not gravado.equals(contrato.esquema):
            raise RuntimeError(
                f"{arquivo}: esquema diferente do contrato\n"
                f"gravado:\n{gravado}\nesperado:\n{contrato.esquema}"
            )
    return arquivos


def publicar(temporario, destino):
    """Substitui o conjunto anterior pelo novo com duas renomeações."""
    antigo = destino.with_name(f".{destino.name}.anterior")
    shutil.rmtree(antigo, ignore_errors=True)
    if destino.exists():
        destino.rename(antigo)
    temporario.rename(destino)
    shutil.rmtree(antigo, ignore_errors=True)


def exportar(contrato, destino_base, id_execucao, origem=None):
    inicio = time.perf_counter()
    tabela = montar_tabela(contrato, origem, id_execucao)

    destino_base.mkdir(parents=True, exist_ok=True)
    destino = destino_base / contrato.nome
    temporario = destino_base / f".{contrato.nome}.{id_execucao}.tmp"
    shutil.rmtree(temporario, ignore_errors=True)
    try:
        gravar(tabela, contrato, temporario)
        arquivos = validar(temporario, tabela, contrato)
        publicar(temporario, destino)
    except Exception:
        shutil.rmtree(temporario, ignore_errors=True)
        raise

    particoes = sorted(
        {p.parent.name for p in arquivos if p.parent.name.startswith(COLUNA_PARTICAO)}
    )
    return {
        "conjunto": contrato.nome,
        "origem": caminho_relativo(origem or contrato.caminho),
        "destino": caminho_relativo(destino),
        "linhas": tabela.num_rows,
        "colunas": tabela.num_columns,
        "arquivos": len(arquivos),
        "particoes": particoes,
        "bytes": sum(a.stat().st_size for a in destino.rglob("*.parquet")),
        "duracao_s": round(time.perf_counter() - inicio, 3),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("conjuntos", nargs="*", help=f"padrão: {' '.join(CONTRATOS)}")
    parser.add_argument("--id-execucao", default=os.environ.get("ID_EXECUCAO") or str(uuid.uuid4()))
    args = parser.parse_args(argv)
    conjuntos = args.conjuntos or list(CONTRATOS)
    desconhecidos = set(conjuntos) - set(CONTRATOS)
    if desconhecidos:
        parser.error(f"conjuntos desconhecidos: {sorted(desconhecidos)}")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    destino_base = parquet_home()
    log.info("id_execucao=%s destino=%s", args.id_execucao, destino_base)

    inicio = datetime.now()
    resultados, falhas = [], []
    for nome in conjuntos:
        try:
            resultado = exportar(CONTRATOS[nome], destino_base, args.id_execucao)
            resultados.append(resultado)
            log.info(
                "%s: %d linhas, %d arquivo(s), %d bytes em %.3fs",
                nome, resultado["linhas"], resultado["arquivos"],
                resultado["bytes"], resultado["duracao_s"],
            )
        except Exception as erro:
            falhas.append({"conjunto": nome, "erro": str(erro)})
            log.error("%s: falha na exportação: %s", nome, erro)

    evidencia = {
        "id_execucao": args.id_execucao,
        "inicio": inicio.isoformat(timespec="seconds"),
        "fim": datetime.now().isoformat(timespec="seconds"),
        "status": "falha" if falhas else "sucesso",
        "compressao": COMPRESSAO,
        "versoes": {"python": sys.version.split()[0], "pyarrow": pa.__version__},
        "conjuntos": resultados,
        "falhas": falhas,
    }
    ARQUIVO_EVIDENCIA.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO_EVIDENCIA.write_text(
        json.dumps(evidencia, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
