"""Gera uma Silver Parquet ampliada para medir o pipeline Beam em volume maior.

Replica as interações Silver com a mesma regra do benchmark de Parquet
(usuario_id deslocado a cada réplica) e copia o catálogo, mantendo a
estrutura esperada por beam/pipeline.py:

    dados/silver/parquet_x<fator>/interacoes/ano_mes=AAAA-MM/parte-0.parquet
    dados/silver/parquet_x<fator>/catalogo/parte-0.parquet

Uso:
    python beam/gerar_volume.py --fator 100
    python beam/pipeline.py --entrada dados/silver/parquet_x100 ...
"""

import argparse
import shutil
import tempfile
import uuid
from pathlib import Path

from benchmark_parquet import replicar_csv
from contratos import CATALOGO, INTERACOES, RAIZ_PROJETO, parquet_home
from exportar_parquet import exportar


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fator", type=int, default=100)
    args = parser.parse_args(argv)

    destino = parquet_home().with_name(f"{parquet_home().name}_x{args.fator}")
    id_execucao = f"volume-x{args.fator}-{uuid.uuid4()}"
    with tempfile.TemporaryDirectory(prefix="gerar_volume_") as temporario:
        csv = Path(temporario) / "interacoes.csv"
        replicar_csv(INTERACOES.caminho, csv, args.fator)
        resultado = exportar(INTERACOES, destino, id_execucao, origem=csv)

    shutil.rmtree(destino / CATALOGO.nome, ignore_errors=True)
    shutil.copytree(parquet_home() / CATALOGO.nome, destino / CATALOGO.nome)
    print(
        f"{resultado['linhas']} interações em {resultado['arquivos']} arquivo(s): "
        f"{destino.relative_to(RAIZ_PROJETO).as_posix()}"
    )


if __name__ == "__main__":
    main()
