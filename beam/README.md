# Parquet e processamento distribuído

Responsável: Estudante 2 (RF24 e RF25).

## RF24 — Exportação da Silver para Parquet

### Execução

Pré-requisitos: Python 3.13 e a camada Silver gerada pelo workflow
`hop/workflows/pipeline_principal.hwf`.

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Linux/macOS: .venv/bin/python

.venv/Scripts/python beam/exportar_parquet.py              # interacoes, comentarios e catalogo
.venv/Scripts/python beam/exportar_parquet.py interacoes   # apenas um conjunto
.venv/Scripts/python beam/benchmark_parquet.py             # medições (fatores 1 e 1000)
```

| Variável | Padrão | Uso |
|---|---|---|
| `SILVER_HOME` | `dados/silver` | Arquivos Silver gerados pelo Apache Hop (mesma variável do ambiente Hop) |
| `PARQUET_HOME` | `$SILVER_HOME/parquet` | Destino dos conjuntos Parquet |
| `ID_EXECUCAO` | UUID gerado | Identificador da execução, para correlacionar com o workflow |

O script termina com código 1 se algum conjunto falhar. Assim, o workflow pode
interromper as etapas dependentes.

### Contrato de entrada

O contrato de cada arquivo Silver está em `beam/contratos.py`, com arquivo,
separador, formatos de data e esquema Arrow. Os tipos seguem os pipelines
`hop/pipelines/silver_*.hpl`:

| Conjunto | Arquivo Silver | Separador | Chave de negócio |
|---|---|---|---|
| interacoes | `interacoes.json` | `;` | usuario_id, conteudo_id, tipo_interacao, data_hora |
| comentarios | `comentarios.json` | `;` | usuario_id, conteudo_id, data, comentario |
| catalogo | `catalogo.csv` | `,` | conteudo_id |

Os arquivos `interacoes.json` e `comentarios.json` da Silver são CSV, apesar da
extensão `.json`, porque o Hop grava os dois com *Text File Output*.

Os campos de auditoria da Bronze (`origem`, `data_ingestao`, `id_execucao`)
são preservados. Cada arquivo Parquet também recebe metadados da exportação:
`camada`, `conjunto`, `arquivo_origem`, `id_execucao_exportacao` e `exportado_em`.

### Garantias da exportação

- **Tipos explícitos:** inteiros como `int32`, medidas como `float64`, datas
  como `date32` e datas/horas como `timestamp[ms]`. O Parquet não tem
  timestamp com precisão de segundos, por isso `data_hora` usa milissegundos.
- **Sem publicação parcial:** o conjunto é gravado em um diretório temporário.
  Antes de substituir o anterior, o script confere a quantidade de linhas e o
  esquema de cada arquivo contra o contrato. Se algo falha, o conjunto
  anterior continua intacto.
- **Obrigatoriedade:** campos obrigatórios são `not null` no esquema. Um valor
  ausente interrompe a exportação daquele conjunto.

### Estratégia de particionamento

| Conjunto | Partição | Motivo |
|---|---|---|
| interacoes | `ano_mes` (AAAA-MM de `data_hora`) | Fato principal dos KPIs, consultado por período |
| comentarios | `ano_mes` (AAAA-MM de `data`) | Mesmo padrão de consulta temporal |
| catalogo | nenhuma | Dimensão pequena (1000 linhas), sempre lida inteira |

Justificativa para `ano_mes`:

1. **Padrão de consulta:** os KPIs (usuário ativo, taxa de conclusão,
   engajamento) são mensais, e o dashboard tem filtro global de período
   (RF18). Filtrar por mês lê só a partição necessária (*partition pruning*).
2. **Reprocessamento:** um mês com problema pode ser regravado sem tocar nos
   demais.
3. **Cardinalidade controlada:** cerca de 12 partições por ano, o que evita o
   excesso de arquivos pequenos.

Alternativas descartadas:

- **Por dia:** cerca de 240 partições com 4 linhas cada no volume atual, ou
  seja, arquivos pequenos demais.
- **Por `tipo_interacao`:** não acompanha o filtro de período, que é o mais
  usado.
- **Por `usuario_id`:** cardinalidade alta, e o campo é identificador pessoal
  indireto (RF32).

### Medições (`beam/evidencias/benchmark_parquet.md`)

O mesmo recorte (interações Silver) foi medido em três formatos: o CSV da
Silver, o Parquet particionado e um Parquet em arquivo único, este como
controle do custo do particionamento.

| Linhas | CSV | Parquet particionado | Parquet único | Leitura seletiva: CSV → particionado |
|---:|---:|---:|---:|---:|
| 1.000 (real) | 127,4 KB | 55,2 KB (43%) | 23,6 KB (19%) | 6,0 ms → 3,8 ms |
| 100.000 | 12,62 MB | 653,7 KB (5%) | 248,5 KB (2%) | 132,5 ms → 4,8 ms |
| 1.000.000 | 127,13 MB | 5,93 MB (5%) | 2,64 MB (2%) | 1147,1 ms → 9,7 ms |

Leitura completa com 1.000.000 de linhas: CSV 3818 ms, Parquet particionado
89 ms, Parquet único 105 ms.

Conclusões:

- O Parquet ocupa menos espaço em todos os volumes. No dado real ficou com 43%
  do tamanho do CSV particionado e 19% em arquivo único. Os campos de auditoria
  (UUID e data de ingestão, repetidos em toda linha) pesam no CSV e são
  comprimidos por dicionário no Parquet.
- Com 1.000 linhas, o particionamento **custa mais do que rende**: o conjunto
  fica 2,3 vezes maior que o arquivo único (8 rodapés e dicionários) e a
  leitura é mais lenta. Aceitamos esse custo porque o volume está crescendo
  (situação-problema).
- A partir de 100 mil linhas, a leitura seletiva de um mês no particionado é a
  mais rápida. Com 1 milhão de linhas, é 4 vezes mais rápida que no arquivo
  único e 118 vezes mais rápida que no CSV.

### Limitações do experimento

- **Volume real pequeno:** a Silver tem 1.000 interações, então as diferenças
  de tempo no fator 1 ficam na casa dos milissegundos e dentro da variação da
  máquina.
- **Dados replicados:** os fatores 100 e 1000 repetem o recorte real, só
  deslocando `usuario_id`. Linhas repetidas favorecem a compressão por
  dicionário, então as reduções de 95% a 98% são um **limite otimista**. A
  medida realista de tamanho é a do fator 1.
- **Cache aquecido:** há uma leitura de aquecimento antes das medições. Os
  tempos refletem cache de disco quente, em uma máquina Windows local, sem
  isolamento de outros processos.
- **CSV tipado:** a leitura completa do CSV inclui a conversão de tipos do
  contrato (datas e números), para comparar resultados equivalentes, já que o
  Parquet é tipado.
- **Sem Spark:** as leituras são feitas por pandas/pyarrow em um único
  processo. O desempenho distribuído é medido no RF25.
- **Sobrescrita completa:** a exportação sobrescreve o conjunto inteiro a cada
  execução. Uma evolução possível é regravar só as partições alteradas.
