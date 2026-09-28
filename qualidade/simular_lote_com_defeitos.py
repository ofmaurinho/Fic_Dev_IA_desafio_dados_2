"""Simula um lote com defeitos para demonstrar o bloqueio da Gold (RF31).

Copia Bronze, Silver e quarentena para um diretório temporário, injeta
defeitos conhecidos e executa os testes de qualidade sobre a cópia, com
origem_dados = "simulacao". Os dados reais em dados/ não são alterados.

Defeitos injetados (regra que deve detectá-los):
    catalogo     2 títulos vazios (QD01); 1 nível "Expert" (QD02)
    interacoes   3 percentuais = 150 (QD02); 5 linhas duplicadas (QD03, QD07);
                 2 conteúdos inexistentes (QD04); 2 conclusões com 80% (QD05);
                 80 registros rejeitados na quarentena (QD08)
    comentarios  1 avaliação = 7 (QD02)

Uso:
    python qualidade/simular_lote_com_defeitos.py
"""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pandas as pd

from executar_testes import CONTRATOS, diretorio, ler_texto, main as executar_testes

REJEITADOS = 80


def gravar(df, contrato, caminho):
    df.to_csv(caminho, sep=contrato.separador, index=False, encoding="utf-8")


def injetar(base):
    silver, bronze, quarentena = base / "silver", base / "bronze", base / "quarentena"

    contrato = CONTRATOS["catalogo"]
    catalogo = ler_texto(contrato, silver / contrato.arquivo)
    catalogo.loc[[10, 11], "titulo"] = ""
    catalogo.loc[12, "nivel"] = "Expert"
    gravar(catalogo, contrato, silver / contrato.arquivo)

    contrato = CONTRATOS["interacoes"]
    interacoes = ler_texto(contrato, silver / contrato.arquivo)
    interacoes.loc[[20, 21, 22], "percentual_conclusao"] = "150.00"
    interacoes.loc[[30, 31], "conteudo_id"] = "99999"
    conclusoes = interacoes.index[interacoes["tipo_interacao"] == "conclusão"][:2]
    interacoes.loc[conclusoes, "percentual_conclusao"] = "80.00"
    interacoes = pd.concat([interacoes, interacoes.iloc[40:45]], ignore_index=True)
    gravar(interacoes, contrato, silver / contrato.arquivo)

    # Registros rejeitados pelo Hop: entram na Bronze e vão para a quarentena.
    rejeitados = interacoes.iloc[100:100 + REJEITADOS].assign(tipo_interacao="desconhecido")
    gravar(rejeitados, contrato, quarentena / contrato.arquivo)
    arquivo_bronze = bronze / contrato.arquivo
    bruto = json.loads(arquivo_bronze.read_text(encoding="utf-8"))
    bruto["data"] += [dict(r, tipo_interacao="desconhecido") for r in bruto["data"][:REJEITADOS]]
    arquivo_bronze.write_text(json.dumps(bruto, ensure_ascii=False), encoding="utf-8")

    contrato = CONTRATOS["comentarios"]
    comentarios = ler_texto(contrato, silver / contrato.arquivo)
    comentarios.loc[5, "avaliacao"] = "7.00"
    gravar(comentarios, contrato, silver / contrato.arquivo)


def main():
    with tempfile.TemporaryDirectory(prefix="lote_defeitos_") as temporario:
        base = Path(temporario)
        for variavel, camada in [
            ("BRONZE_HOME", "bronze"), ("SILVER_HOME", "silver"), ("QUARENTENA_HOME", "quarentena"),
        ]:
            shutil.copytree(diretorio(variavel, camada), base / camada,
                            ignore=shutil.ignore_patterns("parquet*"))
            os.environ[variavel] = str(base / camada)

        injetar(base)
        print(f"Lote simulado em {base}")
        return executar_testes(["--origem-dados", "simulacao"])


if __name__ == "__main__":
    sys.exit(main())
