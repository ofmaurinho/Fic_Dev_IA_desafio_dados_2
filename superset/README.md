# Apache Superset — SQL Lab, dashboard, filtros e alerta

Responsável: Estudante 2 (RF17 e RF18). Versão: **Apache Superset 6.1.0**.

## Ambiente

| Serviço | Função | Acesso |
|---|---|---|
| `superset` | Aplicação web (imagem 6.1.0 + driver `psycopg2-binary`, ver `Dockerfile`) | http://localhost:8088 (usuário `admin`) |
| `superset-worker`, `superset-beat` | Celery: executa e agenda os alertas | — |
| `redis` | Fila do Celery | — |
| `superset-db` | Banco de metadados do Superset (PostgreSQL 16) | — |
| `mailpit` | Servidor SMTP de teste que recebe os e-mails dos alertas | http://localhost:8025 |

Segredos em `superset/.env` (não versionado): `SUPERSET_SECRET_KEY`,
`SUPERSET_META_SENHA`, `SUPERSET_ADMIN_SENHA` e `SUPERSET_DB_SENHA`, a senha
do usuário somente leitura. Para criar o arquivo, gere valores aleatórios,
por exemplo com `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

```bash
# Pré-requisitos: PostgreSQL do Desafio 1 no ar e Gold publicada (gold/publicar_gold.py)
docker compose -f superset/docker-compose.yml up -d --build
.venv/Scripts/python superset/configurar_superset.py                        # alerta diário
.venv/Scripts/python superset/configurar_superset.py --alerta-demonstracao  # alerta a cada minuto
```

`configurar_superset.py` recria toda a configuração a partir do repositório.
Pode ser executado várias vezes, porque cria ou atualiza cada objeto pelo
nome. Ele faz, nesta ordem:

1. Usuário somente leitura no PostgreSQL.
2. Conexão, consultas salvas, datasets e métricas.
3. Gráficos, dashboard e filtros.
4. Alerta.
5. Verificação da consulta de cada gráfico.
6. Exportações e evidências.

## Acesso aos dados

O Superset conecta com o usuário **`superset_leitura`**
(`sql/acesso_superset.sql`), com transações somente leitura. O script
verifica o acesso real desse usuário a cada execução:

| Objeto | Acesso |
|---|---|
| `gold.*` | permitido |
| `qualidade.v_evolucao_metricas`, `qualidade.v_ultima_execucao` | permitido |
| `silver.*` | negado |
| `mestre.*` (tabela de correspondência de IDs) | negado |
| `public.*` (Desafio 1, com `usuario_id`) | negado |

A Bronze não está no banco. O dashboard só consegue consultar a Gold (RF26).
Na conexão do Superset, DML, CTAS e CVAS também estão desabilitados.

## RF17 — SQL Lab e conjuntos de dados virtuais

As consultas estão em `sql/sql_lab.sql`. Cada bloco traz a finalidade e os
campos calculados, e é cadastrado como consulta salva no SQL Lab, com a
documentação na descrição. Todas leem apenas o schema `gold`, então os
resultados podem ser reproduzidos a partir da Gold.

| Consulta | Dataset virtual | Junção | Agregação | Condicional | Data | Finalidade |
|---|---|:-:|:-:|:-:|:-:|---|
| `vds_engajamento_interacoes` | sim | ✔ | | ✔ `periodo_do_dia`, `consumo`, `conclusao` | ✔ `date_trunc`, `EXTRACT`, `to_char` | Base do engajamento: interação + atributos do conteúdo |
| `vds_conversao_recomendacao` | sim | ✔ | ✔ `COUNT`, `SUM`, `AVG` | ✔ `faixa_posicao`, convertidas | ✔ `date_trunc` | Conversão por categoria, faixa de posição e status |
| `lista_acao_conteudos` | sim | ✔ | ✔ + mediana (`PERCENTILE_CONT`) | ✔ `classificacao` | ✔ `age`, `EXTRACT` | Lista de ação da curadoria (promover, divulgar, revisar) |
| `alerta_conversao_recomendacao` | não | | ✔ | ✔ `FILTER` | | Valor único avaliado pelo alerta |

**Métricas dos datasets** (definidas no Superset):

| Dataset | Métricas |
|---|---|
| `vds_engajamento_interacoes` | `interacoes`, `usuarios_ativos` = COUNT(DISTINCT usuario_chave), `conclusoes`, `taxa_conclusao` = SUM(conclusao)/SUM(consumo), `avaliacao_media` |
| `vds_conversao_recomendacao` | `total_recomendacoes`, `total_convertidas`, `taxa_conversao` = SUM(convertidas)/SUM(recomendacoes) |
| `lista_acao_conteudos` | `conteudos` |
| `v_evolucao_metricas` (físico) | `metrica_pior` |

As taxas são recalculadas a partir das somas. Por isso continuam corretas com
qualquer filtro, sem média de médias. O `vds_engajamento_interacoes` fica no
grão da interação para que usuários distintos nunca sejam somados entre
grupos.

## RF18 — Dashboard, filtros cruzados e alerta

**Dashboard:** "Engajamento e Recomendações — Visão Analítica" (slug
`engajamento-recomendacoes`).

| Linha | Gráficos |
|---|---|
| 1 | Nota de leitura: definições e como filtrar |
| 2 | Usuários ativos por mês (número com tendência) · Taxa de conclusão mensal (linha) |
| 3 | Interações por categoria (barras) · Taxa de conclusão por tipo de conteúdo (barras) |
| 4 | Conversão de recomendações por categoria (barras) · Conversão por faixa de posição (tabela) |
| 5 | Lista de ação da curadoria (tabela) · Evolução da qualidade QD06 e QD08 (linha, RF31) |

**Filtros cruzados:** estão habilitados nos 7 gráficos de negócio, com escopo
global. Clicar em uma categoria ou em um tipo filtra os demais gráficos que
têm a mesma coluna, inclusive os de conversão e a lista de ação. O gráfico de
qualidade fica fora do escopo.

**Filtros globais (nativos):**

| Filtro | Tipo | Coluna | Gráficos |
|---|---|---|---|
| Período | intervalo de tempo | `data_hora` das interações | Os 4 gráficos de engajamento |
| Categoria | seleção múltipla | `categoria` | Os 7 gráficos de negócio |
| Tipo de conteúdo | seleção múltipla | `tipo` | Os 7 gráficos de negócio |

O filtro de período não se aplica à conversão, porque todas as recomendações
têm a mesma data de geração, nem à lista de ação, que é um retrato
acumulado.

**Alerta:**

| Item | Configuração |
|---|---|
| Nome | Conversão de recomendações abaixo de 5% |
| Consulta | `alerta_conversao_recomendacao`: taxa de conversão (%) das recomendações vigentes |
| Condição | valor `< 5` |
| Periodicidade | Diária às 08:00, America/Sao_Paulo (`0 8 * * *`). Carência de 24 h entre avisos |
| Destinatário fictício | `curadoria@plataforma-educacional.example` |
| Conteúdo | E-mail com a tabela "Conversão por faixa de posição" (formato texto) |
| Ação esperada | A curadoria revisa os parâmetros do motor de recomendação (pesos de visualização, curtida e conclusão) e prioriza conteúdos com histórico de consumo na categoria do usuário |

**Demonstração:** o alerta foi executado a cada minuto
(`--alerta-demonstracao`) e depois voltou para a periodicidade diária.
- **Execução:** a condição foi avaliada com o valor **2,6**, o alerta disparou
  e o e-mail foi entregue ao Mailpit.
- **Carência:** nas execuções dentro do período de carência, o alerta não
  reenviou o e-mail (estado "On Grace").
- **Registros:** execuções em `exportacao_e_evidencias/alerta/execucoes_alerta.json`
  e e-mail recebido em `exportacao_e_evidencias/alerta/email_alerta.html`.

A tabela do e-mail já traz um achado para a narrativa. A conversão cai com a
posição no ranking: **4,7%** no topo (1–3), 2,0% em 4–6 e 1,5% em 7–10.

## Evidências (`superset/exportacao_e_evidencias/`)

| Arquivo | Conteúdo |
|---|---|
| `dashboard_engajamento_recomendacoes.zip` | Exportação oficial do dashboard, gráficos, datasets e conexão (senha mascarada) |
| `consultas_sql_lab.zip` | Exportação das consultas salvas do SQL Lab |
| `alerta/execucoes_alerta.json` | Configuração e histórico de execuções do alerta |
| `alerta/email_alerta.html` | E-mail do alerta capturado pelo Mailpit |

**Capturas de tela (`capturas/`):**

| Arquivo | Mostra |
|---|---|
| `01_dashboard_visao_geral.png` | Usuários ativos (71 em ago/2026, −15,5%), taxa de conclusão mensal, interações por categoria e conclusão por tipo |
| `02_dashboard_filtros_globais_aplicados.png` | Filtros globais de período (último ano), categoria (3 selecionadas) e tipo (Vídeo) aplicados; os gráficos indicam 3 filtros ativos |
| `03_sql_lab_consultas_salvas.png` | As 4 consultas salvas no SQL Lab, todas sobre o schema `gold` |
| `04_alerta_configurado.png` | Alerta ativo, diário às 08:00 (America/Sao_Paulo), com última execução bem-sucedida |
| `05_mailpit_emails_alerta.png` | E-mails do alerta entregues a `curadoria@plataforma-educacional.example` |

## Problema conhecido: tela preta

Na imagem "lean", o Superset escolhe o idioma pelo navegador (pt-BR), mas não
traz as traduções compiladas. Se o idioma pedido não estiver em `LANGUAGES`,
o frontend falha ao montar o menu de idiomas (`Cannot read properties of
undefined (reading 'flag')`) e a página fica **preta**, inclusive no login.

`config/superset_config.py` declara `en` e `pt_BR` em `LANGUAGES`. Com isso a
página carrega, e a interface aparece em inglês, porque não há pacote de
tradução compilado. Os títulos, gráficos e textos do dashboard estão em
português.

## Limitações

- **Gráficos criados pela API:** os parâmetros visuais foram definidos no
  código. As consultas de todos os gráficos são verificadas pela API a cada
  execução, e a renderização dos 8 gráficos foi conferida no navegador.
  Ajustes de aparência feitos na interface precisam ser exportados de novo
  para o ZIP.
- **Interface em inglês:** ver "Problema conhecido: tela preta".
- **Alerta:** o e-mail vai para um SMTP de teste (Mailpit). Em produção, basta
  trocar `SMTP_*` em `config/superset_config.py`.
- **Relatórios com imagem (PNG/PDF):** exigem um navegador headless no worker,
  que a imagem lean não traz. Por isso o alerta usa o formato texto.
