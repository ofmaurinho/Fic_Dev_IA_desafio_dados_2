"""Testes de qualidade de dados da camada Silver (RF31).

Avalia os arquivos Silver gerados pelo Apache Hop, comparando-os com a Bronze
e a quarentena, com 8 regras que cobrem completude, validade, unicidade,
integridade referencial e consistência. Cada regra é aplicada por fonte
(catalogo, interacoes, comentarios) e o resultado é gravado:

    - no PostgreSQL, em qualidade.execucao e qualidade.resultado_teste
      (sql/qualidade.sql), para acompanhar a evolução no Superset;
    - em qualidade/resultados/<data>_<id>.json, como evidência da execução;
    - em qualidade/resultados/evolucao.md, com o histórico das métricas.

Status da execução:
    sucesso                nenhuma regra violada;
    sucesso_com_ressalvas  só regras de severidade "alerta" violadas;
    falha                  ao menos uma regra "critica" violada.

Códigos de saída (usados pelo workflow para liberar ou bloquear a Gold):
    0  Gold liberada (sucesso ou sucesso com ressalvas)
    1  Gold bloqueada (falha crítica)
    2  execução não concluída (arquivo ou banco indisponível)

Uso:
    python qualidade/executar_testes.py
    python qualidade/executar_testes.py --id-execucao X   # correlaciona com o workflow
    python qualidade/executar_testes.py --documentar      # atualiza a tabela de regras.md
"""

import argparse
import json
import os
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

import pandas as pd
import psycopg
from dotenv import load_dotenv
from psycopg.types.json import Jsonb

RAIZ_PROJETO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_PROJETO / "beam"))
from contratos import CONTRATOS, ler_silver_csv, silver_home  # noqa: E402

load_dotenv(RAIZ_PROJETO / ".env")

DIR_RESULTADOS = RAIZ_PROJETO / "qualidade" / "resultados"
ARQUIVO_REGRAS = RAIZ_PROJETO / "qualidade" / "regras.md"
SQL_QUALIDADE = RAIZ_PROJETO / "sql" / "qualidade.sql"
TAMANHO_AMOSTRA = 5

CHAVES = {
    "catalogo": ["conteudo_id"],
    "interacoes": ["usuario_id", "conteudo_id", "tipo_interacao", "data_hora"],
    "comentarios": ["usuario_id", "conteudo_id", "data", "comentario"],
}
# Campos usados para identificar o registro nas amostras de violação.
IDENTIFICADORES = {**CHAVES, "comentarios": ["usuario_id", "conteudo_id", "data"]}
DOMINIOS = {
    "catalogo": {
        "tipo": {"Curso", "Vídeo", "Artigo", "Podcast"},
        "nivel": {"Básico", "Intermediário", "Avançado"},
    },
    "interacoes": {
        "tipo_interacao": {
            "início", "visualização", "conclusão", "curtida", "compartilhamento", "avaliação",
        },
    },
    "comentarios": {},
}
DATA_EVENTO = {"catalogo": "data_publicacao", "interacoes": "data_hora", "comentarios": "data"}


def diretorio(variavel, camada):
    return Path(os.environ.get(variavel) or RAIZ_PROJETO / "dados" / camada)


@dataclass
class Dados:
    """Tudo que as regras consultam, carregado uma vez por execução."""

    texto: dict  # Silver como texto, para detectar vazios e formatos inválidos
    silver: dict  # Silver com os tipos do contrato (valores inválidos viram nulos)
    bronze_linhas: dict
    quarentena_linhas: dict
    usuarios: set


@dataclass
class Avaliacao:
    avaliados: int
    violados: int
    amostra: list = field(default_factory=list)
    metrica: float | None = None  # padrão: % de registros conformes


@dataclass(frozen=True)
class Regra:
    id: str
    dimensao: str
    descricao: str
    formula: str
    fontes: tuple
    operador: str
    limite: float
    severidade: str
    acao: str
    avaliar: Callable[[Dados, str], Avaliacao]


# --- Carga -----------------------------------------------------------------


def ler_texto(contrato, caminho):
    return pd.read_csv(
        caminho, sep=contrato.separador, dtype=str, keep_default_na=False,
        na_values=[""], encoding="utf-8",
    )


def contar_bronze(contrato):
    caminho = diretorio("BRONZE_HOME", "bronze") / contrato.arquivo
    if contrato.nome == "catalogo":
        return len(pd.read_csv(caminho, dtype=str))
    # Interações e comentários: JSON do Hop no formato {"data": [...]}.
    return len(json.loads(caminho.read_text(encoding="utf-8"))["data"])


def contar_quarentena(contrato):
    caminho = diretorio("QUARENTENA_HOME", "quarentena") / contrato.arquivo
    # O Hop só cria o arquivo de quarentena quando há registros rejeitados.
    return len(ler_texto(contrato, caminho)) if caminho.exists() else 0


def carregar(conexao):
    with conexao.cursor() as cursor:
        cursor.execute("SELECT usuario_id FROM public.usuario")
        usuarios = {linha[0] for linha in cursor}
    return Dados(
        texto={n: ler_texto(c, c.caminho) for n, c in CONTRATOS.items()},
        silver={n: ler_silver_csv(c, tolerante=True) for n, c in CONTRATOS.items()},
        bronze_linhas={n: contar_bronze(c) for n, c in CONTRATOS.items()},
        quarentena_linhas={n: contar_quarentena(c) for n, c in CONTRATOS.items()},
        usuarios=usuarios,
    )


# --- Regras ----------------------------------------------------------------


def avaliar_registros(dados, fonte, violacoes):
    """Converte {mensagem: máscara de registros violados} em uma Avaliacao."""
    df = dados.silver[fonte]
    mascara = pd.Series(False, index=df.index)
    for violado in violacoes.values():
        mascara |= violado.fillna(False).astype(bool)

    amostra = []
    for indice in df.index[mascara][:TAMANHO_AMOSTRA]:
        registro = "|".join(
            f"{c}={dados.texto[fonte].at[indice, c]}" for c in IDENTIFICADORES[fonte]
        )
        mensagens = [m for m, v in violacoes.items() if bool(v.fillna(False).at[indice])]
        amostra.append({"registro": registro, "mensagem": "; ".join(mensagens)})
    return Avaliacao(avaliados=len(df), violados=int(mascara.sum()), amostra=amostra)


def completude(dados, fonte):
    texto = dados.texto[fonte]
    obrigatorios = [c.name for c in CONTRATOS[fonte].esquema if not c.nullable]
    vazios = texto[obrigatorios].apply(lambda c: c.isna() | c.str.strip().eq(""))
    return avaliar_registros(dados, fonte, {f"{c} vazio": vazios[c] for c in obrigatorios})


def validade(dados, fonte):
    df, texto = dados.silver[fonte], dados.texto[fonte]
    contrato = CONTRATOS[fonte]
    violacoes = {}

    # Formato: havia valor no arquivo, mas ele não converte para o tipo do contrato.
    for campo in contrato.esquema:
        if str(campo.type) != "string":
            violacoes[f"{campo.name} em formato inválido"] = (
                texto[campo.name].notna() & df[campo.name].isna()
            )

    for coluna, permitidos in DOMINIOS[fonte].items():
        violacoes[f"{coluna} fora do domínio"] = df[coluna].notna() & ~df[coluna].isin(permitidos)

    data_evento = pd.to_datetime(df[DATA_EVENTO[fonte]])
    violacoes[f"{DATA_EVENTO[fonte]} posterior à ingestão"] = data_evento > df["data_ingestao"]

    # Nulos são tratados pela completude (QD01): aqui só valores presentes.
    if fonte == "catalogo":
        violacoes["carga_horaria_min <= 0"] = df["carga_horaria_min"] <= 0
    elif fonte == "interacoes":
        violacoes["percentual_conclusao fora de 0–100"] = fora_da_faixa(
            df["percentual_conclusao"], 0, 100
        )
        violacoes["tempo_consumido negativo"] = df["tempo_consumido"] < 0
        violacoes["avaliacao_atribuida fora de 1–5"] = fora_da_faixa(
            df["avaliacao_atribuida"], 1, 5
        )
    elif fonte == "comentarios":
        violacoes["avaliacao fora de 1–5"] = fora_da_faixa(df["avaliacao"], 1, 5)
        violacoes["tags não é lista JSON"] = df["tags"].notna() & ~df["tags"].map(eh_lista_json)

    return avaliar_registros(dados, fonte, violacoes)


def fora_da_faixa(serie, minimo, maximo):
    return serie.notna() & ~serie.between(minimo, maximo)


def eh_lista_json(valor):
    try:
        return isinstance(json.loads(valor), list)
    except (TypeError, ValueError):
        return False


def unicidade(dados, fonte):
    df = dados.silver[fonte]
    duplicado = df.duplicated(CHAVES[fonte], keep="first")
    return avaliar_registros(
        dados, fonte, {f"chave duplicada ({', '.join(CHAVES[fonte])})": duplicado}
    )


def integridade_referencial(dados, fonte):
    df = dados.silver[fonte]
    conteudos = set(dados.silver["catalogo"]["conteudo_id"].dropna())
    return avaliar_registros(dados, fonte, {
        "conteudo_id ausente no catálogo Silver": ~df["conteudo_id"].isin(conteudos),
        "usuario_id ausente em public.usuario": ~df["usuario_id"].isin(dados.usuarios),
    })


def consistencia_negocio(dados, fonte):
    df = dados.silver[fonte]
    conclusao = df["tipo_interacao"].eq("conclusão")
    return avaliar_registros(dados, fonte, {
        "conclusão sem percentual 100 ou 100% sem conclusão":
            conclusao != df["percentual_conclusao"].eq(100),
        "avaliação sem nota atribuída":
            df["tipo_interacao"].eq("avaliação") & df["avaliacao_atribuida"].isna(),
    })


def consistencia_temporal(dados, fonte):
    df = dados.silver[fonte]
    catalogo = dados.silver["catalogo"].drop_duplicates("conteudo_id")
    publicacao = df["conteudo_id"].map(catalogo.set_index("conteudo_id")["data_publicacao"])
    evento = pd.to_datetime(df[DATA_EVENTO[fonte]]).dt.normalize()
    return avaliar_registros(dados, fonte, {
        f"{DATA_EVENTO[fonte]} anterior à publicação do conteúdo":
            evento < pd.to_datetime(publicacao),
    })


def conservacao_volume(dados, fonte):
    bronze = dados.bronze_linhas[fonte]
    silver, quarentena = len(dados.silver[fonte]), dados.quarentena_linhas[fonte]
    diferenca = abs(bronze - silver - quarentena)
    amostra = [] if not diferenca else [{
        "registro": fonte,
        "mensagem": f"bronze={bronze}, silver={silver}, quarentena={quarentena}",
    }]
    return Avaliacao(
        avaliados=bronze, violados=diferenca, amostra=amostra,
        metrica=100 * (1 - diferenca / bronze) if bronze else 0.0,
    )


def taxa_quarentena(dados, fonte):
    bronze, quarentena = dados.bronze_linhas[fonte], dados.quarentena_linhas[fonte]
    return Avaliacao(
        avaliados=bronze, violados=quarentena,
        metrica=100 * quarentena / bronze if bronze else 100.0,
    )


TODAS = ("catalogo", "interacoes", "comentarios")
EVENTOS = ("interacoes", "comentarios")
BLOQUEAR = "Bloquear a publicação da Gold. "

REGRAS = [
    Regra(
        "QD01", "Completude", "Campos obrigatórios preenchidos na Silver",
        "registros sem campo obrigatório vazio / registros × 100", TODAS, ">=", 100, "critica",
        BLOQUEAR + "Corrigir a regra de campos obrigatórios da Silver e reprocessar.", completude,
    ),
    Regra(
        "QD02", "Validade",
        "Formato, domínio e faixa dos valores (tipos, níveis, percentuais, notas, datas não futuras)",
        "registros com todos os valores válidos / registros × 100", TODAS, ">=", 100, "critica",
        BLOQUEAR + "Enviar os registros inválidos à quarentena e reprocessar.", validade,
    ),
    Regra(
        "QD03", "Unicidade", "Chave de negócio única por fonte",
        "registros não duplicados na chave / registros × 100", TODAS, ">=", 100, "critica",
        BLOQUEAR + "Revisar a deduplicação da Silver e reprocessar.", unicidade,
    ),
    Regra(
        "QD04", "Integridade referencial",
        "conteudo_id existe no catálogo Silver e usuario_id existe em public.usuario",
        "registros com referências válidas / registros × 100", EVENTOS, ">=", 100, "critica",
        BLOQUEAR + "Colocar os órfãos em quarentena ou carregar o cadastro faltante.",
        integridade_referencial,
    ),
    Regra(
        "QD05", "Consistência",
        "Tipo da interação coerente com as medidas (conclusão ⇔ 100%; avaliação ⇒ nota)",
        "registros coerentes / registros × 100", ("interacoes",), ">=", 100, "critica",
        BLOQUEAR + "Revisar a origem das interações; a taxa de conclusão ficaria incorreta.",
        consistencia_negocio,
    ),
    Regra(
        "QD06", "Consistência",
        "Evento (interação ou comentário) não anterior à publicação do conteúdo",
        "eventos na data de publicação ou depois / eventos × 100", EVENTOS, ">=", 95, "alerta",
        "Publicar a Gold com ressalva e acionar a curadoria do catálogo para revisar as datas.",
        consistencia_temporal,
    ),
    Regra(
        "QD07", "Consistência",
        "Conservação de volume: Bronze = Silver + quarentena",
        "(1 − |bronze − silver − quarentena| / bronze) × 100", TODAS, ">=", 100, "critica",
        BLOQUEAR + "Há registros perdidos ou criados entre as camadas; revisar o pipeline Silver.",
        conservacao_volume,
    ),
    Regra(
        "QD08", "Validade", "Taxa de rejeição para a quarentena",
        "registros em quarentena / registros na Bronze × 100", TODAS, "<=", 5, "alerta",
        "Publicar a Gold com ressalva, analisar a quarentena e reprocessar os corrigidos.",
        taxa_quarentena,
    ),
]


# --- Execução --------------------------------------------------------------


def aprovado(regra, metrica):
    return metrica >= regra.limite if regra.operador == ">=" else metrica <= regra.limite


def executar_regras(dados):
    resultados = []
    for regra in REGRAS:
        for fonte in regra.fontes:
            avaliacao = regra.avaliar(dados, fonte)
            metrica = avaliacao.metrica
            if metrica is None:
                total = avaliacao.avaliados
                metrica = 100 * (total - avaliacao.violados) / total if total else 100.0
            resultados.append({
                "id_regra": regra.id,
                "fonte": fonte,
                "dimensao": regra.dimensao,
                "descricao": regra.descricao,
                "severidade": regra.severidade,
                "registros_avaliados": avaliacao.avaliados,
                "registros_violados": avaliacao.violados,
                "metrica": round(metrica, 3),
                "operador": regra.operador,
                "limite": regra.limite,
                "aprovado": aprovado(regra, round(metrica, 3)),
                "acao": regra.acao,
                "amostra_violacoes": avaliacao.amostra,
            })
    return resultados


def status_final(resultados):
    reprovadas = {r["severidade"] for r in resultados if not r["aprovado"]}
    if "critica" in reprovadas:
        return "falha"
    return "sucesso_com_ressalvas" if reprovadas else "sucesso"


def gravar_banco(conexao, execucao, resultados):
    with conexao.transaction(), conexao.cursor() as cursor:
        cursor.execute(
            """INSERT INTO qualidade.execucao
               (id_execucao, inicio, fim, status, gold_liberada, origem_dados, silver_home)
               VALUES (%(id_execucao)s, %(inicio)s, %(fim)s, %(status)s, %(gold_liberada)s,
                       %(origem_dados)s, %(silver_home)s)""",
            execucao,
        )
        cursor.executemany(
            """INSERT INTO qualidade.resultado_teste
               (id_execucao, id_regra, fonte, dimensao, descricao, severidade,
                registros_avaliados, registros_violados, metrica, operador, limite,
                aprovado, acao, amostra_violacoes, executado_em)
               VALUES (%(id_execucao)s, %(id_regra)s, %(fonte)s, %(dimensao)s, %(descricao)s,
                       %(severidade)s, %(registros_avaliados)s, %(registros_violados)s,
                       %(metrica)s, %(operador)s, %(limite)s, %(aprovado)s, %(acao)s,
                       %(amostra)s, %(executado_em)s)""",
            [
                {**r, "id_execucao": execucao["id_execucao"], "executado_em": execucao["fim"],
                 "amostra": Jsonb(r["amostra_violacoes"])}
                for r in resultados
            ],
        )


def gravar_evolucao(conexao):
    """Regrava evolucao.md com o pior valor de cada regra em cada execução."""
    with conexao.cursor() as cursor:
        cursor.execute(
            """SELECT data_execucao, id_execucao, origem_dados, status, id_regra,
                      CASE WHEN operador = '>=' THEN MIN(metrica) ELSE MAX(metrica) END,
                      BOOL_AND(aprovado)
               FROM qualidade.v_evolucao_metricas
               GROUP BY data_execucao, id_execucao, origem_dados, status, id_regra, operador
               ORDER BY data_execucao, id_regra"""
        )
        linhas = cursor.fetchall()

    execucoes, valores = {}, {}
    for data, id_execucao, origem, status, id_regra, metrica, ok in linhas:
        execucoes[id_execucao] = (data, origem, status)
        valores[id_execucao, id_regra] = f"{float(metrica):.1f}{'' if ok else ' ✖'}"

    ids_regras = [r.id for r in REGRAS]
    saida = [
        "# Evolução das métricas de qualidade",
        "",
        "Pior valor de cada regra entre as fontes em cada execução, em %: mínimo",
        "para regras de conformidade (≥) e máximo para a taxa de quarentena",
        "(QD08, ≤). ✖ = limite violado em ao menos uma fonte. Gerado por",
        "`qualidade/executar_testes.py` a partir de `qualidade.v_evolucao_metricas`.",
        "",
        "| Execução | Origem | Status | " + " | ".join(ids_regras) + " |",
        "|---|---|---|" + "---:|" * len(ids_regras),
    ]
    for id_execucao, (data, origem, status) in execucoes.items():
        celulas = [valores.get((id_execucao, r), "—") for r in ids_regras]
        saida.append(
            f"| {data:%Y-%m-%d %H:%M:%S} `{id_execucao[:8]}` | {origem} | {status} | "
            + " | ".join(celulas) + " |"
        )
    (DIR_RESULTADOS / "evolucao.md").write_text("\n".join(saida) + "\n", encoding="utf-8")


def documentar():
    """Atualiza a tabela de regras em qualidade/regras.md a partir de REGRAS."""
    linhas = [
        "| Regra | Dimensão | Descrição | Fontes | Fórmula | Limite | Severidade | Ação |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in REGRAS:
        limite = f"{r.operador} {r.limite:g}%"
        linhas.append(
            f"| {r.id} | {r.dimensao} | {r.descricao} | {', '.join(r.fontes)} "
            f"| {r.formula} | {limite} | {r.severidade} | {r.acao} |"
        )
    texto = ARQUIVO_REGRAS.read_text(encoding="utf-8")
    inicio, fim = "<!-- regras:inicio -->", "<!-- regras:fim -->"
    antes, resto = texto.split(inicio)
    _, depois = resto.split(fim)
    ARQUIVO_REGRAS.write_text(
        f"{antes}{inicio}\n" + "\n".join(linhas) + f"\n{fim}{depois}", encoding="utf-8"
    )


def imprimir(resultados, status):
    for r in resultados:
        marca = "ok " if r["aprovado"] else ("ERRO" if r["severidade"] == "critica" else "AVISO")
        print(
            f"[{marca:>5}] {r['id_regra']} {r['fonte']:<12} {r['dimensao']:<24} "
            f"{r['metrica']:>8.3f}% {r['operador']} {r['limite']:g}% "
            f"({r['registros_violados']}/{r['registros_avaliados']} violados)"
        )
    print(f"Status: {status} — Gold {'liberada' if status != 'falha' else 'BLOQUEADA'}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--id-execucao", default=os.environ.get("ID_EXECUCAO") or str(uuid.uuid4()))
    parser.add_argument("--origem-dados", default="silver", choices=["silver", "simulacao"])
    parser.add_argument("--documentar", action="store_true", help="só atualiza qualidade/regras.md")
    args = parser.parse_args(argv)

    if args.documentar:
        documentar()
        return 0

    inicio = datetime.now()
    try:
        with psycopg.connect(connect_timeout=10) as conexao:
            conexao.execute(SQL_QUALIDADE.read_text(encoding="utf-8"))
            conexao.commit()
            resultados = executar_regras(carregar(conexao))
            status = status_final(resultados)
            execucao = {
                "id_execucao": args.id_execucao,
                "inicio": inicio,
                "fim": datetime.now(),
                "status": status,
                "gold_liberada": status != "falha",
                "origem_dados": args.origem_dados,
                "silver_home": silver_home().as_posix(),
            }
            gravar_banco(conexao, execucao, resultados)
            gravar_evolucao(conexao)
    except (OSError, psycopg.Error) as erro:
        print(f"Execução não concluída; Gold bloqueada: {erro}", file=sys.stderr)
        return 2

    DIR_RESULTADOS.mkdir(parents=True, exist_ok=True)
    try:
        execucao["silver_home"] = silver_home().resolve().relative_to(RAIZ_PROJETO).as_posix()
    except ValueError:
        execucao["silver_home"] = "(diretório temporário da simulação)"
    evidencia = DIR_RESULTADOS / f"{inicio:%Y%m%d-%H%M%S}_{args.id_execucao[:8]}.json"
    evidencia.write_text(
        json.dumps({"execucao": execucao, "resultados": resultados},
                   ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    imprimir(resultados, status)
    return 1 if status == "falha" else 0


if __name__ == "__main__":
    sys.exit(main())
