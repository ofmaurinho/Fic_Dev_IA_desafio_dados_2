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

## RF25 — Processamento distribuído com Apache Beam

### Regra de negócio

`beam/pipeline.py` calcula o **engajamento mensal por categoria**: lê as
interações e o catálogo da Silver em Parquet, associa cada interação à
categoria do conteúdo e agrega por (`ano_mes`, `categoria`). O resultado é
gravado em Parquet na Gold, em `dados/gold/engajamento_categoria_mensal/`.

| Medida | Regra |
|---|---|
| `total_interacoes` | Quantidade de interações do grupo |
| `usuarios_ativos` | Usuários distintos com ao menos uma interação no mês e na categoria |
| `conteudos_consumidos` | Conteúdos distintos com interação |
| `interacoes_consumo` | Interações do tipo início, visualização ou conclusão |
| `conclusoes` | Interações do tipo conclusão |
| `taxa_conclusao` | `conclusoes / interacoes_consumo`, com 4 casas decimais (nula se não houver consumo) |
| `percentual_conclusao_medio` | Média de `percentual_conclusao`, com 2 casas decimais |
| `tempo_consumido_total` | Soma de `tempo_consumido`, na unidade da fonte |
| `curtidas`, `compartilhamentos` | Contagem por tipo de interação |
| `avaliacoes`, `avaliacao_media` | Quantidade e média das avaliações atribuídas (nulas ignoradas) |
| `id_execucao`, `runtime` | Auditoria: execução e runtime que gerou a linha |

Etapas do pipeline:

1. `ReadFromParquet` lê só as colunas necessárias, aproveitando o formato colunar.
2. O catálogo vira um *side input* (`conteudo_id → categoria`).
3. Um `ParDo` gera as chaves. Interações sem conteúdo no catálogo entram como
   "Não catalogado" e são contadas na métrica `interacoes_sem_categoria`.
4. `CombinePerKey` aplica uma `CombineFn` associativa. Cada worker pré-agrega
   seus dados e o runtime une os acumuladores parciais.
5. `WriteToParquet` grava o resultado.

A regra foi conferida contra um cálculo independente em pandas, e as 64 linhas
bateram. A única diferença foi de arredondamento: um valor exatamente em x,xx5,
em que o `round` do Python está correto.

### Runtimes

| Runtime | Como executa |
|---|---|
| DirectRunner | Local. No Beam 2.76, o DirectRunner do Python delega a execução ao **Prism**, o runner local do Beam, que o SDK baixa em `~/.apache_beam/cache` |
| Spark | Cluster standalone em Docker (`beam/spark/docker-compose.yml`): 1 master e 2 workers de 2 cores e 1 GB cada. O pipeline vai pelo `PortableRunner` ao job server do Beam, que é o driver Spark. Os executores rodam o código Python em *worker pools* do Beam (ambiente `EXTERNAL`) |

```bash
# DirectRunner
.venv/Scripts/python beam/pipeline.py

# Spark
docker compose -f beam/spark/docker-compose.yml up -d        # UI do Spark: http://localhost:8090
.venv/Scripts/python beam/pipeline.py --runner PortableRunner \
    --job_endpoint localhost:8099 --artifact_endpoint localhost:8098 \
    --environment_type EXTERNAL --environment_config localhost:50000 \
    --environment_cache_millis 60000 --rotulo spark

# Comparação dos runtimes (gera beam/evidencias/comparacao_runtimes.md)
.venv/Scripts/python beam/comparar_runtimes.py
```

Parâmetros próprios do pipeline: `--entrada` (padrão `dados/silver/parquet`),
`--saida` (padrão `dados/gold/engajamento_categoria_mensal`), `--id-execucao`
(ou a variável `ID_EXECUCAO`) e `--rotulo`. Os demais argumentos são opções do
Beam. Cada execução grava `beam/evidencias/execucao_<runtime>_<linhas>.json`,
com estado, duração, volume de entrada e saída, métricas, opções e versões.

Versões: Apache Beam 2.76.0 (SDK Python 3.13), Spark 3.5.0 (Scala 2.12), job
server `apache/beam_spark3_job_server:2.76.0` (Java 11).

### Decisões de configuração do cluster

- **Mesma versão do Spark do job server:** o cluster usa Spark 3.5.0, a mesma
  versão empacotada no job server do Beam 2.76.0.
- **Worker pool acoplado a cada worker Spark** (`network_mode: service:...`):
  o executor e o processo Python do Beam se conectam por `localhost`.
- **Jar do Beam à frente no classpath dos executores**
  (`spark.executor.extraClassPath`):
  - O jar do Beam precisa de Guava 33, e o Spark traz Guava 14. Sem esse
    ajuste, a primeira tarefa de cada executor falha com `NoSuchMethodError`
    e só passa na nova tentativa.
  - A alternativa `spark.executor.userClassPathFirst` quebra a desserialização
    das tarefas do Spark.
- **`--environment_cache_millis 60000`:** mantém o processo Python vivo entre
  estágios do Spark. Sem isso, o Beam recria o ambiente a cada estágio, com
  11 a 17 s por partida, e a execução levava 223 s em vez de cerca de 40 s.
- **`RUN_PYTHON_SDK_IN_DEFAULT_ENVIRONMENT=1`:** o worker usa o Python da
  imagem em vez de criar um venv temporário por processo.

### Medições (`beam/evidencias/comparacao_runtimes.md`)

| Linhas de entrada | DirectRunner | Spark (2 workers, 4 cores) | Saídas iguais |
|---:|---:|---:|---|
| 1.000 (Silver real) | 1,4 s | 49,4 s | sim |
| 100.000 (replicada, `beam/gerar_volume.py --fator 100`) | 2,3 s | 32,2 s | sim |

Nos dois volumes, os runtimes produziram exatamente as mesmas 64 linhas.

O Spark é mais lento neste volume porque quase todo o tempo é custo fixo de
cada execução: iniciar a aplicação Spark, alocar executores, subir o Python do
Beam e trafegar os dados entre JVM e Python. O processamento em si leva poucos
segundos. O ganho do Spark aparece quando o volume não cabe em uma máquina ou
quando mais workers dividem a leitura dos arquivos Parquet (1 tarefa por
arquivo ou faixa de arquivo). A mesma regra, sem alteração de código, pode ir
para um cluster maior só mudando as opções de execução, e essa é a razão de
usar o Beam.

### Limitações

- **Cluster em uma máquina só:** os 2 workers rodam na mesma máquina, em
  Docker, e competem por CPU e disco. Não há ganho real de paralelismo físico.
- **Volume ampliado artificial:** os 100 mil registros são o recorte real
  replicado, e dados repetidos favorecem compressão e cache.
- **Tempos com partida a frio:** cada execução no Spark é uma nova aplicação,
  então os tempos incluem a partida a frio dos executores e variam entre
  execuções. A primeira execução após subir o cluster foi a mais lenta.
- **Métricas tentadas no Spark:** o runner do Spark só informa métricas
  *tentadas*. O script registra essas quando as *confirmadas* não existem.
- **Dados locais:** os dados são lidos de um diretório local montado nos
  containers, não de um sistema distribuído (HDFS ou S3). Todos os workers
  enxergam o mesmo disco.
