"""Contrato dos arquivos da camada Silver gerados pelo Apache Hop.

Para cada conjunto, descreve o arquivo de origem, o separador, os formatos de
data e o esquema Arrow usado na exportação para Parquet. Os tipos seguem os
definidos nos pipelines hop/pipelines/silver_*.hpl, e os campos de auditoria
herdados da Bronze (origem, data_ingestao, id_execucao) são preservados.

Os diretórios vêm das mesmas variáveis usadas no ambiente do Apache Hop
(SILVER_HOME) e podem ser sobrescritos por variáveis de ambiente.
"""

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pyarrow as pa

RAIZ_PROJETO = Path(__file__).resolve().parent.parent

FORMATO_DATA = "%Y-%m-%d"
FORMATO_DATA_HORA = "%Y-%m-%dT%H:%M:%S"
FORMATO_DATA_INGESTAO = "%Y/%m/%d %H:%M:%S.%f"

COLUNA_PARTICAO = "ano_mes"

CAMPOS_AUDITORIA = [
    pa.field("origem", pa.string(), nullable=False),
    pa.field("data_ingestao", pa.timestamp("ms"), nullable=False),
    pa.field("id_execucao", pa.string(), nullable=False),
]


def silver_home():
    return Path(os.environ.get("SILVER_HOME") or RAIZ_PROJETO / "dados" / "silver")


def parquet_home():
    return Path(os.environ.get("PARQUET_HOME") or silver_home() / "parquet")


@dataclass(frozen=True)
class ContratoSilver:
    nome: str
    arquivo: str
    separador: str
    esquema: pa.Schema
    formatos_data: dict
    coluna_data_particao: str | None = None

    @property
    def caminho(self):
        return silver_home() / self.arquivo


INTERACOES = ContratoSilver(
    nome="interacoes",
    arquivo="interacoes.csv",
    separador=";",
    esquema=pa.schema(
        [
            pa.field("usuario_id", pa.int32(), nullable=False),
            pa.field("conteudo_id", pa.int32(), nullable=False),
            pa.field("tipo_interacao", pa.string(), nullable=False),
            pa.field("data_hora", pa.timestamp("ms"), nullable=False),
            pa.field("tempo_consumido", pa.float64(), nullable=False),
            pa.field("percentual_conclusao", pa.float64(), nullable=False),
            pa.field("avaliacao_atribuida", pa.float64()),
            *CAMPOS_AUDITORIA,
        ]
    ),
    formatos_data={
        "data_hora": FORMATO_DATA_HORA,
        "data_ingestao": FORMATO_DATA_INGESTAO,
    },
    coluna_data_particao="data_hora",
)

COMENTARIOS = ContratoSilver(
    nome="comentarios",
    arquivo="comentarios.csv",
    separador=";",
    esquema=pa.schema(
        [
            pa.field("usuario_id", pa.int32(), nullable=False),
            pa.field("conteudo_id", pa.int32(), nullable=False),
            pa.field("avaliacao", pa.float64(), nullable=False),
            pa.field("comentario", pa.string(), nullable=False),
            # Lista serializada como texto JSON, como na Silver.
            pa.field("tags", pa.string(), nullable=False),
            pa.field("data", pa.date32(), nullable=False),
            *CAMPOS_AUDITORIA,
        ]
    ),
    formatos_data={
        "data": FORMATO_DATA,
        "data_ingestao": FORMATO_DATA_INGESTAO,
    },
    coluna_data_particao="data",
)

CATALOGO = ContratoSilver(
    nome="catalogo",
    arquivo="catalogo.csv",
    separador=",",
    esquema=pa.schema(
        [
            pa.field("conteudo_id", pa.int32(), nullable=False),
            pa.field("titulo", pa.string(), nullable=False),
            pa.field("tipo", pa.string(), nullable=False),
            pa.field("categoria", pa.string(), nullable=False),
            pa.field("nivel", pa.string(), nullable=False),
            pa.field("carga_horaria_min", pa.int32(), nullable=False),
            pa.field("data_publicacao", pa.date32(), nullable=False),
            pa.field("descricao", pa.string(), nullable=False),
            pa.field("autor", pa.string(), nullable=False),
            *CAMPOS_AUDITORIA,
        ]
    ),
    formatos_data={
        "data_publicacao": FORMATO_DATA,
        "data_ingestao": FORMATO_DATA_INGESTAO,
    },
)

CONTRATOS = {c.nome: c for c in (INTERACOES, COMENTARIOS, CATALOGO)}


def ler_silver_csv(contrato, caminho=None, tolerante=False):
    """Lê o arquivo Silver e devolve um DataFrame com os tipos do contrato.

    Com tolerante=True, valores fora do formato viram nulos em vez de erro,
    para que os testes de qualidade possam contá-los como violações.
    """
    caminho = caminho or contrato.caminho
    erros = "coerce" if tolerante else "raise"
    df = pd.read_csv(
        caminho,
        sep=contrato.separador,
        dtype=str,
        keep_default_na=False,
        na_values=[""],
        encoding="utf-8",
    )

    esperadas = contrato.esquema.names
    faltantes = set(esperadas) - set(df.columns)
    if faltantes:
        raise ValueError(
            f"{caminho}: colunas ausentes no arquivo Silver: {sorted(faltantes)}"
        )

    for campo in contrato.esquema:
        coluna = df[campo.name]
        if campo.name in contrato.formatos_data:
            convertida = pd.to_datetime(
                coluna, format=contrato.formatos_data[campo.name], errors=erros
            )
            df[campo.name] = convertida.dt.date if pa.types.is_date(campo.type) else convertida
        elif pa.types.is_integer(campo.type):
            numeros = pd.to_numeric(coluna, errors=erros)
            if tolerante:
                numeros = numeros.where(numeros % 1 == 0)
            df[campo.name] = numeros.astype("Int64")
        elif pa.types.is_floating(campo.type):
            coluna = coluna.str.replace(",", ".", regex=False)
            df[campo.name] = pd.to_numeric(coluna, errors=erros)

    return df[esperadas]


def adicionar_particao(df, contrato):
    """Acrescenta a coluna ano_mes (AAAA-MM) derivada da data de negócio."""
    datas = pd.to_datetime(df[contrato.coluna_data_particao])
    return df.assign(**{COLUNA_PARTICAO: datas.dt.strftime("%Y-%m")})


def impressao_silver():
    """SHA-256 dos arquivos Silver: identifica exatamente os dados avaliados.

    O quality gate grava esta impressão, e a publicação da Gold exige que os
    arquivos não tenham mudado desde os testes.
    """
    resumo = hashlib.sha256()
    for nome in sorted(CONTRATOS):
        resumo.update(nome.encode())
        resumo.update(CONTRATOS[nome].caminho.read_bytes())
    return resumo.hexdigest()
