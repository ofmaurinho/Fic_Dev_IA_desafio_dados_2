**# FIC_DEV — Desafio Prático 2**

**## Pipeline Governado, Escalável e Seguro de Conteúdos Educacionais**

Projeto desenvolvido para o Desafio Prático 2 da FIC_DEV, com evolução da solução do Desafio Prático 1 para uma arquitetura automatizada, governada, escalável e preparada para qualidade, rastreabilidade, catalogação, linhagem, proteção de dados e consumo analítico.

**## Participantes**

\- João Flavio

\- Fabricio Mauro

\- Eduardo Borges

**## 1. Objetivo**

O projeto implementa um pipeline de dados educacionais utilizando Apache Hop, Python, PostgreSQL, Apache Beam, Parquet, Superset e OpenMetadata.

A solução reutiliza as fontes e o banco de dados do Desafio Prático 1 e organiza o processamento nas camadas Bronze, Silver e Gold, com controles de qualidade, quarentena, reprocessamento, dados mestres, publicação analítica, governança de metadados, linhagem e medidas de proteção de dados.

A arquitetura foi estruturada para permitir reprodução em outro ambiente sem depender de caminhos absolutos, credenciais incorporadas no código ou configurações sensíveis versionadas.

**## 2. Arquitetura da solução**

\`\`\`text

Fontes do Desafio 1

        │

        ├── CSV

        ├── JSON

        └── PostgreSQL

              │

              ▼

        ┌─────────────┐

        │   BRONZE    │

        │ cópia/auditoria

        └──────┬──────┘

               ▼

        ┌─────────────┐

        │   SILVER    │

        │ padronização│

        │ validação   │

        │ deduplicação│

        └──────┬──────┘

               ▼

        ┌─────────────┐

        │  QUALIDADE  │

        │ QD01–QD08   │

        └──────┬──────┘

               │

        falha crítica

               │

               └──────► Abort

               │

               ▼

        ┌─────────────┐

        │ Dados Mestres│

        └──────┬──────┘

               ▼

        ┌─────────────┐

        │   Parquet   │

        └──────┬──────┘

               ▼

        ┌─────────────┐

        │ Apache Beam │

        │ DirectRunner│

        └──────┬──────┘

               ▼

        ┌─────────────┐

        │    GOLD     │

        │ fatos/dimensões

        │ KPIs/views  │

        └──────┬──────┘

               │

        ┌──────┴───────────┐

        ▼                  ▼

   SQL Lab/Superset   OpenMetadata

                           │

                    catálogo/glossário

                    classificação/linhagem

\`\`\`

A execução principal orquestrada pelo Apache Hop segue:

\`\`\`text

Bronze

  ↓

Silver

  ↓

Qualidade

  ↓

Dados Mestres

  ↓

Exportar Parquet

  ↓

Beam

  ↓

Publicar Gold

  ↓

Fim

\`\`\`

Após a publicação da Gold, a governança no OpenMetadata é executada/validada como etapa posterior.

A governança no OpenMetadata é validada depois da publicação da Gold, para que o catálogo e a linhagem representem os ativos analíticos efetivamente produzidos. A ingestão/validação do OpenMetadata é uma etapa de governança posterior à execução principal do workflow.

**## 3. Estrutura do projeto**

\`\`\`text

desafio-pratico-2/

├── README.md

├── .env.example

├── .gitignore

├── project-config.json

├── requirements.txt

├── dados/

│   ├── entrada/

│   ├── bronze/

│   ├── silver/

│   ├── gold/

│   └── quarentena/

├── hop/

│   ├── pipelines/

│   ├── workflows/

│   └── config/

│       └── DEV-config.json

├── metadata/

│   └── D1_POSTGRES.json

├── beam/

│   ├── pipeline.py

│   ├── contratos.py

│   ├── exportar_parquet.py

│   ├── benchmark_parquet.py

│   ├── comparar_runtimes.py

│   ├── gerar_volume.py

│   └── evidencias/

├── qualidade/

│   ├── regras.md

│   ├── executar_testes.py

│   ├── simular_lote_com_defeitos.py

│   └── resultados/

├── dados_mestres/

│   ├── consolidar_conteudo.py

│   └── evidencias/

├── gold/

│   ├── publicar_gold.py

│   └── evidencias/

├── sql/

│   ├── camada_gold.sql

│   ├── sql_lab.sql

│   ├── qualidade.sql

│   ├── dados_mestres.sql

│   └── acesso_superset.sql

├── superset/

│   ├── docker-compose.yml

│   ├── Dockerfile

│   ├── configurar_superset.py

│   ├── README.md

│   ├── config/

│   └── exportacao_e_evidencias/

├── openmetadata/

│   └── evidencias/

├── lgpd/

│   ├── inventario_de_dados.md

│   └── tecnicas_de_protecao.md

└── documentacao/

    ├── arquitetura.pdf

    ├── linhagem.pdf

    └── storytelling.pdf

\`\`\`

A pasta \`dados/entrada/\` contém as cópias das fontes utilizadas para reprodução. Os pipelines do Apache Hop ficam diretamente em \`hop/pipelines/\`. A configuração do ambiente fica em \`hop/config/DEV-config.json\` e a conexão de metadata \`D1_POSTGRES\` fica em \`metadata/D1_POSTGRES.json\`.

**## 4. Preparação do Desafio Prático 1**

O Desafio Prático 2 reutiliza as fontes de dados e o banco de dados produzidos pelo Desafio Prático 1. Portanto, em uma instalação nova, o Desafio Prático 1 deve ser preparado e executado antes das etapas do Desafio Prático 2.

O diretório do Desafio Prático 1 deve estar dentro da raiz deste projeto:

```text
desafio-pratico-2/
└── desafio-pratico-1/
```

### 4.1 Acessar o diretório do Desafio Prático 1

A partir da raiz do Desafio Prático 2:

```cmd
cd desafio-pratico-1
```

### 4.2 Configurar o ambiente do Desafio Prático 1

Criar o arquivo `.env` a partir do `.env.example`:

```cmd
copy .env.example .env
```

Configurar as credenciais e portas conforme o ambiente local.

Instalar as dependências do Desafio Prático 1:

```cmd
python -m pip install -r requirements.txt
```

### 4.3 Subir o PostgreSQL e o MongoDB

Executar:

```cmd
docker compose up -d
```

Validar:

```cmd
docker ps
```

Devem estar disponíveis os containers:

```text
desafio_dados_postgres
desafio_dados_mongo
```

Em uma instalação nova, o PostgreSQL utiliza a porta `5433` no host e o MongoDB utiliza a porta `27018`.

### 4.4 Criar a estrutura do banco do Desafio Prático 1

Para um banco novo, executar:

```cmd
type sql\criar_banco.sql | docker exec -i desafio_dados_postgres psql -U postgres -d desafio_dados
```

Se o banco já tiver sido criado anteriormente pelo Desafio Prático 1, utilizar:

```cmd
type sql\migracao_estudante2.sql | docker exec -i desafio_dados_postgres psql -U postgres -d desafio_dados
```

A etapa de criação/migração prepara a extensão `pgvector` e as tabelas utilizadas pelo projeto.

### 4.5 Executar o pipeline do Desafio Prático 1

Executar:

```cmd
python -m src.main
```

Essa execução realiza a leitura, validação, tratamento, remoção de duplicidades e carga dos dados nos bancos utilizados pelo projeto.

Após a execução, o banco do Desafio Prático 1 estará preparado para ser utilizado como origem pelo Desafio Prático 2.

### 4.6 Retornar à raiz do Desafio Prático 2

```cmd
cd ..
```

A partir deste ponto, seguir as etapas deste README para preparar e executar o Desafio Prático 2.

**Importante:** se os containers `desafio_dados_postgres` e `desafio_dados_mongo` já estiverem em execução, não é necessário executar novamente o `docker compose up -d` do Desafio Prático 1. O objetivo é reutilizar o ambiente existente.

### 4.7 Configuração da conexão `D1_POSTGRES` no Apache Hop

Os pipelines e workflows do Desafio Prático 2 utilizam a conexão de metadata `D1_POSTGRES`, armazenada em:

```text
metadata/D1_POSTGRES.json
```

A metadata da conexão utiliza variáveis do ambiente `DEV` para evitar que host, porta, banco, usuário e senha fiquem fixados no arquivo de conexão.

A configuração utilizada no ambiente `DEV` é:

```text
D1_POSTGRES_HOST=localhost
D1_POSTGRES_PORT=5433
D1_POSTGRES_DATABASE=desafio_dados
D1_POSTGRES_USERNAME=postgres
D1_POSTGRES_PASSWORD=postgres
```

Essas variáveis devem ser definidas no arquivo:

```text
hop/config/DEV-config.json
```

A conexão `D1_POSTGRES` utiliza essas variáveis para acessar o PostgreSQL produzido pelo Desafio Prático 1.

A senha `postgres` corresponde à configuração utilizada pelo PostgreSQL do Desafio Prático 1 neste projeto. Caso o ambiente de reprodução utilize outra senha, o valor de `D1_POSTGRES_PASSWORD` deverá ser ajustado localmente.

O arquivo `metadata/D1_POSTGRES.json` deve permanecer no projeto porque os pipelines e workflows dependem da conexão de metadata `D1_POSTGRES`.

**## 5. Ambiente utilizado**

O projeto foi desenvolvido e validado no seguinte ambiente:

\- Windows 11, build \`10.0.26200.9457\`

\- WSL2

\- Ubuntu 24.04.5 LTS

\- Docker Desktop 4.90.0

\- Docker Engine 29.7.2

\- Docker Compose 5.5.1

\- Git 2.55.0.windows.5

\- JDK Temurin 21.0.12.1 LTS

\- Apache Hop 2.19.0

\- Python 3.14.7

\- Apache Beam 2.76.0

\- PyArrow 25.0.1

\- Apache Hop Environment \`DEV\`

As versões são registradas para permitir a reprodução e a identificação das dependências da solução.

**## 6. Pré-requisitos**

Antes de executar o projeto, instalar:

1\. Git.

2\. Python.

3\. JDK 21.

4\. Apache Hop.

5\. Docker Desktop.

6\. WSL2 com Ubuntu.

7\. PostgreSQL do Desafio 1, ou uma instância PostgreSQL compatível contendo o banco e o esquema utilizados pelo projeto.

O Docker Desktop deve estar iniciado antes da execução dos serviços containerizados.

**## 7. Obter o projeto**

Clonar o repositório:

\`\`\`cmd

git clone https\://github.com/ofmaurinho/Fic_Dev_IA_desafio_dados_2.git

cd Fic_Dev_IA_desafio_dados_2

\`\`\`

No Windows, recomenda-se utilizar o diretório:

\`\`\`text

C:\projetos\desafio-pratico-2

\`\`\`

O projeto não depende desse caminho específico; os caminhos de execução são obtidos por configuração.

**## 8. Criar o ambiente virtual Python**

No diretório raiz:

\`\`\`cmd

python -m venv .venv

\`\`\`

Ativar:

\`\`\`cmd

.venv\Scripts\activate

\`\`\`

Atualizar o instalador:

\`\`\`cmd

python -m pip install --upgrade pip

\`\`\`

Instalar as dependências:

\`\`\`cmd

python -m pip install -r requirements.txt

\`\`\`

Validar as principais bibliotecas:

\`\`\`cmd

.venv\Scripts\python.exe -c "import pandas, psycopg, pyarrow, apache_beam; print('Dependências OK')"

\`\`\`

As ações Python disparadas pelo Apache Hop utilizam explicitamente \`.venv\Scripts\python.exe\`, evitando dependência do Python global da máquina.

**## 9. Configurar o PostgreSQL**

O projeto reutiliza o banco do Desafio Prático 1.

Configuração utilizada:

\`\`\`text

Container: desafio_dados_postgres

Imagem: pgvector/pgvector\:pg16

Banco: desafio_dados

Usuário: postgres

Porta host: 5433

Porta interna Docker: 5432

\`\`\`

Aplicações executadas no Windows utilizam:

\`\`\`text

localhost:5433

\`\`\`

A porta \`5432\` é a porta interna do container.

Caso o PostgreSQL do Desafio 1 seja executado pelo Docker Compose correspondente, iniciar os serviços antes de executar o pipeline.

Validar a conexão:

\`\`\`cmd

.venv\Scripts\python.exe -c "import os, psycopg; from dotenv import load_dotenv; load_dotenv(); conn=psycopg.connect(host=os.getenv('PGHOST','localhost'), port=os.getenv('PGPORT','5433'), dbname=os.getenv('PGDATABASE','desafio_dados'), user=os.getenv('PGUSER','postgres'), password=os.getenv('PGPASSWORD')); print('PostgreSQL OK'); conn.close()"

\`\`\`

**## 10. Configuração de variáveis e segredos**

Criar o arquivo \`.env\` a partir do modelo:

\`\`\`cmd

copy .env.example .env

\`\`\`

Preencher com os valores locais:

\`\`\`text

PGHOST=localhost

PGPORT=5433

PGDATABASE=desafio_dados

PGUSER=postgres

PGPASSWORD=sua_senha

PSEUDONIMIZACAO_CHAVE=chave_aleatoria

\`\`\`

Gerar uma chave aleatória:

\`\`\`cmd

python -c "import secrets; print(secrets.token_hex(32))"

\`\`\`

O \`.env\` não deve ser versionado.

Também não devem ser versionados:

\- senhas;

\- chaves;

\- tokens;

\- credenciais;

\- salts;

\- dados pessoais brutos;

\- tabelas de mapeamento sensíveis.

**## 11. Configurar o Apache Hop**

Criar ou configurar o ambiente \`DEV\` no Apache Hop.

A configuração externa utilizada fica no próprio projeto:

\`\`\`text

${PROJECT_HOME}/hop/config/DEV-config.json

\`\`\`

Os caminhos principais são:

\`\`\`text

DATA_HOME=${PROJECT_HOME}/dados

BRONZE_HOME=${PROJECT_HOME}/dados/bronze

SILVER_HOME=${PROJECT_HOME}/dados/silver

GOLD_HOME=${PROJECT_HOME}/dados/gold

QUARENTENA_HOME=${PROJECT_HOME}/dados/quarentena

DATA_INPUT=${PROJECT_HOME}/dados/entrada

D1_POSTGRES_HOST=localhost
D1_POSTGRES_PORT=5433
D1_POSTGRES_DATABASE=desafio_dados
D1_POSTGRES_USERNAME=postgres
D1_POSTGRES_PASSWORD=postgres

\`\`\`

As variáveis \`D1_POSTGRES_*\` são utilizadas pela metadata \`D1_POSTGRES\` para parametrizar a conexão PostgreSQL do Desafio Prático 1.

A utilização de \`PROJECT_HOME\` evita dependência de caminhos absolutos e permite reproduzir o projeto em outro diretório.

O projeto não utiliza caminhos absolutos dentro dos pipelines.

**## 12. Preparar as fontes de entrada**

Copiar as fontes do Desafio 1 para:

\`\`\`text

dados/entrada/catalogo.csv

dados/entrada/interacoes.json

dados/entrada/comentarios.json

\`\`\`

Esses arquivos são preservados separadamente das camadas processadas.

A preservação permite:

\- reexecução;

\- comparação entre camadas;

\- testes de falha;

\- validação de volume;

\- reprocessamento.

**## 13. RF20 — Bronze**

Os pipelines Bronze são:

\`\`\`text

hop/pipelines/bronze_catalogo.hpl

hop/pipelines/bronze_interacoes.hpl

hop/pipelines/bronze_comentarios.hpl

\`\`\`

Entradas:

\`\`\`text

dados/entrada/catalogo.csv

dados/entrada/interacoes.json

dados/entrada/comentarios.json

\`\`\`

Saídas:

\`\`\`text

dados/bronze/catalogo.csv

dados/bronze/interacoes.json

dados/bronze/comentarios.json

\`\`\`

A Bronze preserva os dados de forma não destrutiva e acrescenta informações de auditoria, incluindo origem, data/hora de ingestão e \`ID_EXECUCAO\`.

Interações e comentários são normalizados para uma estrutura JSON com:

\`\`\`json

{"data": [*...*]}

\`\`\`

**## 14. RF21 — Silver**

Os pipelines Silver são:

\`\`\`text

hop/pipelines/silver_catalogo.hpl

hop/pipelines/silver_interacoes.hpl

hop/pipelines/silver_comentarios.hpl

\`\`\`

Saídas:

\`\`\`text

dados/silver/catalogo.csv

dados/silver/interacoes.csv

dados/silver/comentarios.csv

\`\`\`

A Silver realiza:

\- padronização de campos;

\- conversão de tipos;

\- normalização de datas;

\- validação de campos obrigatórios;

\- validação de domínios;

\- validação de referências;

\- identificação de duplicidades;

\- preparação dos dados para qualidade e consumo analítico.

Interações e comentários utilizam \`;\` como separador.

Os contratos são centralizados em:

\`\`\`text

beam/contratos.py

\`\`\`

A localização da Silver é obtida por \`SILVER_HOME\`.

**## 15. Regras de duplicidade**

As chaves de negócio utilizadas são:

\`\`\`text

Catálogo:

conteudo_id

Interações:

usuario_id + conteudo_id + tipo_interacao + data_hora

Comentários:

usuario_id + conteudo_id + data + comentario

\`\`\`

Essas regras são utilizadas na validação de unicidade e no tratamento de registros duplicados.

**## 16. RF23 — Quarentena e reprocessamento**

A área de quarentena é:

\`\`\`text

dados/quarentena/

\`\`\`

O pipeline de reprocessamento é:

\`\`\`text

hop/pipelines/reprocessar_quarentena.hpl

\`\`\`

A solução registra informações necessárias para identificar:

\- registro;

\- origem;

\- regra violada;

\- data/hora;

\- mensagem de erro;

\- execução relacionada.

Os registros inválidos podem ser isolados na quarentena sem interromper o processamento dos registros válidos.

O reprocessamento é realizado separadamente para permitir correção controlada.

Foram contemplados cenários de:

1\. falha de arquivo;

2\. falha de regra;

3\. falha de conexão;

4\. quarentena;

5\. reprocessamento.

**## 17. RF22 — Workflow e orquestração**

O workflow principal é:

\`\`\`text

hop/workflows/pipeline_principal.hwf

\`\`\`

Sequência:

\`\`\`text

Bronze

  ↓

Silver

  ↓

Qualidade

  ↓

Dados Mestres

  ↓

Exportar Parquet

  ↓

Beam

  ↓

Publicar Gold

  ↓

Fim

\`\`\`

O workflow utiliza \`ID_EXECUCAO\` para correlacionar as etapas. A ingestão e validação no OpenMetadata ocorre como etapa de governança após a publicação da Gold.

Cada execução registra início, término, duração e resultado.

Falhas críticas de qualidade encaminham o fluxo para a etapa de aborto e impedem a execução das etapas dependentes.

As ações Python utilizam o interpretador do ambiente virtual:

\`\`\`text

${PROJECT_HOME}/.venv/Scripts/python.exe

\`\`\`

Isso é especialmente importante para execução pelo Apache Hop, pois o processo iniciado pelo Hop pode não herdar o Python virtualizado do terminal.

**## 18. RF31 — Qualidade de dados**

O principal script é:

\`\`\`text

qualidade/executar_testes.py

\`\`\`

As dimensões implementadas são:

\`\`\`text

QD01 — Completude

QD02 — Validade

QD03 — Unicidade

QD04 — Integridade referencial

QD05 — Consistência de negócio

QD06 — Consistência temporal

QD07 — Conservação de volume

QD08 — Taxa de quarentena

\`\`\`

As regras e seus critérios ficam documentados em:

\`\`\`text

qualidade/regras.md

\`\`\`

Os resultados são armazenados em:

\`\`\`text

qualidade/resultados/

\`\`\`

O registro dos resultados no PostgreSQL utiliza:

\`\`\`text

sql/qualidade.sql

\`\`\`

**### Execução direta**

\`\`\`cmd

.venv\Scripts\python.exe qualidade\executar_testes.py

\`\`\`

Com identificador de execução:

\`\`\`cmd

.venv\Scripts\python.exe qualidade\executar_testes.py --id-execucao ID_DA_EXECUCAO

\`\`\`

Para documentação das regras:

\`\`\`cmd

.venv\Scripts\python.exe qualidade\executar_testes.py --documentar

\`\`\`

Códigos de saída:

\`\`\`text

0 = Gold liberada

1 = Gold bloqueada por falha crítica

2 = execução não concluída por indisponibilidade de arquivo ou banco

\`\`\`

As regras críticas bloqueiam a publicação da Gold quando o critério mínimo não é atendido.

As dimensões de alerta podem permitir a continuidade, desde que não exista falha crítica.

**## 19. Dados mestres**

A consolidação é executada por:

\`\`\`text

dados_mestres/consolidar_conteudo.py

\`\`\`

A consolidação utiliza as fontes Silver e PostgreSQL do Desafio 1.

São consideradas correspondências pelo identificador de conteúdo e duplicidades entre fontes.

As evidências ficam em:

\`\`\`text

dados_mestres/evidencias/

\`\`\`

A execução integrada consolida 1000 registros de cada fonte e produz 997 conteúdos mestres após as regras de deduplicação e consolidação.

A estratégia preserva identificadores mestres entre execuções para evitar a criação desnecessária de novos identificadores.

**## 20. Parquet**

A exportação é realizada por:

\`\`\`text

beam/exportar_parquet.py

\`\`\`

Os arquivos Parquet são gerados em:

\`\`\`text

dados/silver/parquet/

\`\`\`

A execução produz:

\`\`\`text

interacoes: 1000 linhas, 8 arquivos

comentarios: 1000 linhas, 8 arquivos

catalogo: 1000 linhas, 1 arquivo

\`\`\`

O formato Parquet é utilizado como entrada otimizada para a etapa Apache Beam.

**## 21. Apache Beam**

O pipeline é:

\`\`\`text

beam/pipeline.py

\`\`\`

A execução utiliza:

\`\`\`text

DirectRunner

\`\`\`

A etapa lê os arquivos Parquet e gera a agregação:

\`\`\`text

dados/gold/engajamento_categoria_mensal

\`\`\`

A execução validada processa 1000 interações e produz 64 linhas agregadas.

As informações de execução registradas incluem:

\- \`ID_EXECUCAO\`;

\- runtime;

\- runner;

\- estado;

\- início;

\- duração;

\- caminho de entrada;

\- quantidade de linhas;

\- quantidade de arquivos;

\- caminho de saída;

\- métricas;

\- versões do Python, Beam e PyArrow.

**## 22. Gold**

A publicação da camada Gold é realizada por:

\`\`\`text

gold/publicar_gold.py

\`\`\`

Os objetos publicados incluem:

\`\`\`text

gold.dim_conteudo

gold.dim_usuario

gold.fato_interacao

gold.fato_comentario

gold.fato_recomendacao

gold.kpi_engajamento_mensal_categoria

gold.vw_kpi_mensal

gold.vw_desempenho_conteudo

gold.vw_conversao_recomendacao

\`\`\`

Também são disponibilizados os resultados derivados do Beam e os objetos Silver necessários ao consumo.

A execução integrada produz, entre outros:

\`\`\`text

gold.dim_conteudo                  997

gold.dim_usuario                   150

gold.fato_interacao               1000

gold.fato_comentario              1000

gold.fato_recomendacao            1500

gold.kpi_engajamento_mensal_categoria 64

gold.vw_kpi_mensal                   8

gold.vw_desempenho_conteudo       997

gold.vw_conversao_recomendacao      20

\`\`\`

São geradas amostras para evidência em:

\`\`\`text

gold/evidencias/amostras/

\`\`\`

**## 23. SQL Lab e Superset**

Os scripts SQL principais são:

\`\`\`text

sql/camada_gold.sql

sql/sql_lab.sql

sql/acesso_superset.sql

\`\`\`

O Superset está organizado em:

\`\`\`text

superset/

\`\`\`

Os serviços podem ser iniciados pelo Docker Compose:

\`\`\`cmd

cd superset

docker compose up -d --build

\`\`\`

Após a inicialização, acessar o Superset pela porta definida em \`superset/docker-compose.yml\`.

O banco PostgreSQL utilizado pelo Superset deve apontar para a instância configurada no ambiente de execução.

As consultas e datasets utilizados para consumo analítico devem utilizar a camada Gold, e não a Bronze.

As exportações e evidências do Superset ficam em:

\`\`\`text

superset/exportacao_e_evidencias/

\`\`\`

**## 24. OpenMetadata — RF27, RF28 e RF29**

O OpenMetadata é utilizado como camada de governança técnica e de negócio.

A estrutura de evidências é:

\`\`\`text

openmetadata/evidencias/

\`\`\`

A configuração contempla:

\- conexão com PostgreSQL;

\- ingestão de metadados técnicos;

\- catalogação de ativos;

\- descrição dos ativos;

\- definição de proprietário;

\- glossário de negócio;

\- classificações;

\- linhagem.

**### Acesso**

A instância web do OpenMetadata é disponibilizada na porta configurada pelo ambiente, com acesso local normalmente realizado por:

\`\`\`text

http\://localhost:8585

\`\`\`

**### Configuração do PostgreSQL**

No OpenMetadata, criar/configurar o serviço de banco de dados utilizando:

\`\`\`text

Host: endereço acessível pelo container/serviço do OpenMetadata

Porta: 5433 quando acessado a partir do host Windows

Banco: desafio_dados

Usuário: postgres

\`\`\`

Quando OpenMetadata estiver em container e o PostgreSQL também estiver em container, utilizar o nome do serviço/rede Docker correspondente em vez de \`localhost\`, conforme a composição utilizada.

As credenciais devem ser informadas na configuração do serviço e não armazenadas no repositório.

**### Ingestão**

Executar a ingestão de metadados do PostgreSQL pelo serviço configurado no OpenMetadata.

Após a ingestão, validar:

1\. schemas;

2\. tabelas;

3\. colunas;

4\. tipos;

5\. descrições;

6\. proprietário;

7\. classificação;

8\. glossário;

9\. linhagem.

**### Glossário**

O catálogo utiliza termos de negócio associados aos ativos correspondentes, incluindo:

\- Usuário Ativo;

\- Taxa de Conclusão;

\- Conversão de Recomendação;

\- Engajamento.

Os termos devem ser associados aos campos e ativos correspondentes da camada Silver/Gold.

**### Classificação**

Os campos relevantes são classificados de acordo com a natureza dos dados e as regras de governança definidas no projeto.

A classificação deve permitir identificar dados que exigem tratamento diferenciado, especialmente aqueles relacionados a usuários.

**### Linhagem**

A linhagem documentada representa:

\`\`\`text

Fonte

  ↓

Bronze

  ↓

Silver

  ↓

Gold

  ↓

SQL Lab / Superset

\`\`\`

Também são documentadas as transformações relevantes, os KPIs e os datasets virtuais quando a linhagem automática não for suficiente.

**## 25. LGPD**

A documentação está em:

\`\`\`text

lgpd/inventario_de_dados.md

lgpd/tecnicas_de_protecao.md

\`\`\`

O inventário identifica os dados processados, suas finalidades, origem, utilização e camada de armazenamento.

As técnicas de proteção contemplam medidas como:

\- pseudonimização;

\- controle de acesso;

\- separação de credenciais;

\- não versionamento de segredos;

\- minimização da exposição de dados pessoais;

\- proteção das informações utilizadas no pipeline.

A chave de pseudonimização permanece exclusivamente no ambiente de execução.

**## 26. Evidências**

Os principais diretórios de evidências são:

\`\`\`text

qualidade/resultados/

dados_mestres/evidencias/

gold/evidencias/

beam/evidencias/

openmetadata/evidencias/

superset/exportacao_e_evidencias/

documentacao/

\`\`\`

As evidências devem ser utilizadas para demonstrar:

\- execução dos pipelines;

\- qualidade;

\- tratamento de falhas;

\- quarentena;

\- reprocessamento;

\- consolidação dos dados mestres;

\- geração de Parquet;

\- execução Beam;

\- publicação Gold;

\- catálogo;

\- classificação;

\- glossário;

\- linhagem;

\- consumo no Superset;

\- arquitetura;

\- storytelling;

\- aplicação das medidas LGPD.

**## 27. Testes de falha e recuperação**

A solução contempla a simulação dos principais tipos de falha exigidos.

**### Falha de arquivo**

Remover ou renomear temporariamente um arquivo obrigatório de entrada e executar o pipeline correspondente.

O comportamento esperado é registrar a falha e impedir que uma execução inconsistente seja tratada como processamento normal.

Depois, restaurar o arquivo e executar novamente.

**### Falha de qualidade**

O script:

\`\`\`text

qualidade/simular_lote_com_defeitos.py

\`\`\`

permite gerar dados com defeitos para validar as regras de qualidade.

Executar os testes e verificar:

\`\`\`text

qualidade/resultados/

\`\`\`

Uma falha crítica deve bloquear a publicação da Gold.

**### Falha de conexão**

Para reproduzir o teste de conexão, alterar temporariamente a porta configurada do PostgreSQL para uma porta indisponível, executar a etapa dependente e verificar o registro da falha.

Depois, restaurar:

\`\`\`text

PGPORT=5433

\`\`\`

**### Quarentena e reprocessamento**

Validar os registros direcionados para:

\`\`\`text

dados/quarentena/

\`\`\`

e utilizar:

\`\`\`text

hop/pipelines/reprocessar_quarentena.hpl

\`\`\`

para realizar o processamento posterior dos registros corrigidos.

**## 28. Execução completa e reprodução**

A reprodução completa deve seguir esta ordem.

**### 28.1 Preparar o ambiente**

\`\`\`cmd

git clone https\://github.com/ofmaurinho/Fic_Dev_IA_desafio_dados_2.git

cd Fic_Dev_IA_desafio_dados_2

python -m venv .venv

.venv\Scripts\activate

python -m pip install --upgrade pip

python -m pip install -r requirements.txt

\`\`\`

**### 28.2 Configurar o ambiente**

Criar:

\`\`\`text

.env

\`\`\`

a partir de:

\`\`\`text

.env.example

\`\`\`

Configurar PostgreSQL e demais serviços externos.

**### 28.3 Preparar o Apache Hop**

Abrir o Apache Hop, configurar o ambiente \`DEV\` e apontar o projeto para o diretório clonado.

Associar ao ambiente \`DEV\` o arquivo:

\`\`\`text

${PROJECT_HOME}/hop/config/DEV-config.json

\`\`\`

Verificar:

\`\`\`text

PROJECT_HOME
DATA_HOME
BRONZE_HOME
SILVER_HOME
GOLD_HOME
QUARENTENA_HOME
DATA_INPUT
D1_POSTGRES_HOST
D1_POSTGRES_PORT
D1_POSTGRES_DATABASE
D1_POSTGRES_USERNAME
D1_POSTGRES_PASSWORD

\`\`\`

**### 28.4 Preparar as fontes**

Colocar:

\`\`\`text

dados/entrada/catalogo.csv

dados/entrada/interacoes.json

dados/entrada/comentarios.json

\`\`\`

**### 28.5 Validar PostgreSQL**

Executar:

\`\`\`cmd

.venv\Scripts\python.exe -c "import os, psycopg; from dotenv import load_dotenv; load_dotenv(); conn=psycopg.connect(host=os.getenv('PGHOST','localhost'), port=os.getenv('PGPORT','5433'), dbname=os.getenv('PGDATABASE','desafio_dados'), user=os.getenv('PGUSER','postgres'), password=os.getenv('PGPASSWORD')); print('PostgreSQL OK'); conn.close()"

\`\`\`

**### 28.6 Executar o workflow**

No Apache Hop, abrir:

\`\`\`text

hop/workflows/pipeline_principal.hwf

\`\`\`

Executar o workflow.

A sequência deve ser:

\`\`\`text

Bronze

→ Silver

→ Qualidade

→ Dados Mestres

→ Exportar Parquet

→ Beam

→ Publicar Gold

→ Fim

\`\`\`

**### 28.7 Validar as saídas**

Verificar:

\`\`\`text

dados/bronze/

dados/silver/

dados/silver/parquet/

dados/gold/

dados/quarentena/

qualidade/resultados/

dados_mestres/evidencias/

gold/evidencias/

beam/evidencias/

openmetadata/evidencias/

superset/exportacao_e_evidencias/

\`\`\`

**### 28.8 Validar a Gold**

Consultar as tabelas e views utilizando SQL Lab, PostgreSQL ou Superset.

Exemplos:

\`\`\`sql

SELECT COUNT(\*) FROM gold.dim_conteudo;

SELECT COUNT(\*) FROM gold.dim_usuario;

SELECT COUNT(\*) FROM gold.fato_interacao;

SELECT COUNT(\*) FROM gold.fato_comentario;

SELECT COUNT(\*) FROM gold.fato_recomendacao;

SELECT \* FROM gold.vw_kpi_mensal;

\`\`\`

**### 28.9 Validar governança**

No OpenMetadata:

1\. verificar o serviço PostgreSQL;

2\. executar/validar a ingestão;

3\. consultar os ativos;

4\. verificar descrições;

5\. verificar proprietários;

6\. verificar classificações;

7\. consultar o glossário;

8\. consultar a linhagem.

**### 28.10 Validar o Superset**

Iniciar:

\`\`\`cmd

cd superset

docker compose up -d --build

\`\`\`

Configurar a conexão com o PostgreSQL e validar os datasets Gold e os dashboards/documentos previstos.

**## 29. Execução das etapas individualmente**

As etapas também podem ser reproduzidas separadamente.

Bronze:

\`\`\`text

hop/pipelines/bronze_catalogo.hpl

hop/pipelines/bronze_interacoes.hpl

hop/pipelines/bronze_comentarios.hpl

\`\`\`

Silver:

\`\`\`text

hop/pipelines/silver_catalogo.hpl

hop/pipelines/silver_interacoes.hpl

hop/pipelines/silver_comentarios.hpl

\`\`\`

Qualidade:

\`\`\`cmd

.venv\Scripts\python.exe qualidade\executar_testes.py --id-execucao TESTE-QUALIDADE

\`\`\`

Dados Mestres:

\`\`\`cmd

.venv\Scripts\python.exe dados_mestres\consolidar_conteudo.py --id-execucao TESTE-MESTRES

\`\`\`

Parquet:

\`\`\`cmd

.venv\Scripts\python.exe beam\exportar_parquet.py

\`\`\`

Beam:

\`\`\`cmd

.venv\Scripts\python.exe beam\pipeline.py --id-execucao TESTE-BEAM

\`\`\`

Gold:

\`\`\`cmd

.venv\Scripts\python.exe gold\publicar_gold.py --id-execucao TESTE-GOLD

\`\`\`

**## 30. Desempenho e volume**

Os scripts auxiliares para avaliação de volume e desempenho são:

\`\`\`text

beam/gerar_volume.py

beam/benchmark_parquet.py

beam/comparar_runtimes.py

\`\`\`

Eles permitem gerar volumes de teste e comparar a execução utilizando os formatos e runtimes definidos no projeto.

As evidências de execução ficam em:

\`\`\`text

beam/evidencias/

\`\`\`

**## 31. Segurança e versionamento**

O projeto utiliza Git:

\`\`\`text

https\://github.com/ofmaurinho/Fic_Dev_IA_desafio_dados_2.git

\`\`\`

Devem ser versionados:

\- código;

\- pipelines;

\- workflows;

\- SQL;

\- documentação;

\- arquivos de configuração não sensíveis;

\- evidências necessárias à entrega.

Não devem ser versionados:

\- \`.env\`;

\- senhas e credenciais reais de ambientes externos/produção;

\- chaves;

\- tokens;

\- dados pessoais brutos;

\- arquivos temporários sensíveis.

O \`.gitignore\` foi configurado para proteger esses conteúdos.

A exceção documentada para a configuração acadêmica local é a senha padrão \`postgres\` utilizada pelo PostgreSQL do Desafio Prático 1. Ela é necessária para a reprodução local e não representa uma credencial de produção.

O arquivo \`metadata/D1_POSTGRES.json\` deve ser versionado porque os pipelines e workflows dependem da conexão de metadata \`D1_POSTGRES\`. Seus parâmetros de conexão são referenciados por variáveis do ambiente \`DEV\`.

**## 32. Requisitos funcionais contemplados**

A solução contempla os requisitos do desafio relacionados a:

\- continuidade e configuração;

\- arquitetura ETL/ELT;

\- ingestão Bronze;

\- transformação Silver;

\- workflow e orquestração;

\- tratamento de erros;

\- quarentena;

\- reprocessamento;

\- Parquet;

\- Apache Beam;

\- camada Gold;

\- dados mestres;

\- qualidade de dados;

\- governança no OpenMetadata;

\- catálogo;

\- glossário;

\- classificação;

\- linhagem;

\- Superset e SQL Lab;

\- LGPD;

\- evidências e documentação.

A implementação é integrada para que as etapas de processamento, qualidade, governança e consumo possam ser reproduzidas como uma única solução.

**## 33. Documentação complementar**

Os materiais de documentação ficam em:

\`\`\`text

documentacao/

\`\`\`

e incluem:

\`\`\`text

arquitetura.pdf

linhagem.pdf

storytelling.pdf

\`\`\`

Esses documentos complementam o README com a visão arquitetural, a representação da linhagem e a apresentação dos resultados.

**## 34. Checklist de reprodução**

\`\`\`text

[ ] Instalar Windows/WSL2/Docker/JDK/Python/Apache Hop

[ ] Clonar o repositório

[ ] Criar .venv

[ ] Instalar requirements.txt

[ ] Criar .env

[ ] Configurar PostgreSQL

[ ] Validar conexão

[ ] Configurar Apache Hop Environment DEV

[ ] Associar `${PROJECT_HOME}/hop/config/DEV-config.json` ao ambiente DEV

[ ] Validar as variáveis `D1_POSTGRES_*` no ambiente DEV

[ ] Validar a conexão `D1_POSTGRES`

[ ] Configurar PROJECT_HOME

[ ] Disponibilizar dados/entrada

[ ] Validar pipelines Bronze

[ ] Validar pipelines Silver

[ ] Executar Qualidade

[ ] Executar Dados Mestres

[ ] Gerar Parquet

[ ] Executar Beam

[ ] Publicar Gold

[ ] Executar/validar ingestão OpenMetadata

[ ] Validar catálogo, glossário e classificações

[ ] Validar linhagem

[ ] Iniciar Superset

[ ] Validar SQL Lab/datasets/dashboards

[ ] Conferir evidências

[ ] Conferir documentação

\`\`\`

**## 35. Critério de reprodução**

Uma nova execução deve ser possível a partir de:

1\. ambiente instalado;

2\. repositório clonado;

3\. dependências instaladas;

4\. \`.env\` configurado;

5\. PostgreSQL disponível;

6\. fontes em \`dados/entrada/\`;

7\. ambiente \`DEV\` do Apache Hop configurado;

8\. serviços Docker iniciados;

9\. workflow principal executado.

Os caminhos específicos do computador devem ser derivados de \`PROJECT_HOME\` e das variáveis de ambiente/configuração.

Credenciais e segredos devem ser fornecidos somente no ambiente local de reprodução.

**## 36. Entrega**

A entrega deve conter o código, pipelines, workflows, SQL, dados de entrada permitidos, documentação, evidências e configurações não sensíveis necessárias para reproduzir o projeto.

Também devem acompanhar o projeto a metadata `metadata/D1_POSTGRES.json` e o arquivo `hop/config/DEV-config.json`, pois são necessários para resolver a conexão PostgreSQL utilizada pelos pipelines e workflows.

A estrutura final mantém separadas:

\`\`\`text

dados de entrada

      ↓

Bronze

      ↓

Silver

      ↓

Qualidade/Quarentena

      ↓

Dados Mestres

      ↓

Parquet/Beam

      ↓

Gold

      ↓

Superset/SQL Lab

      ↓

OpenMetadata

\`\`\`

Essa organização permite rastreabilidade ponta a ponta, governança dos ativos, controle de qualidade, isolamento de falhas e reprodução do processamento em outro ambiente.
