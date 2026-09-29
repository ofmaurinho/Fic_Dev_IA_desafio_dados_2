# Consolidação de dados mestres — Conteúdo

Execução `f1ad24ee-4d9e-4291-abb2-73050ea7840e` em 2026-09-29T04:05:50.

| Indicador | Valor |
|---|---:|
| registros na fonte silver_catalogo | 1000 |
| registros na fonte d1_postgres | 1000 |
| conteudo_ids distintos | 1000 |
| correspondências M1 (mesmo id nas duas fontes) | 1000 |
| grupos de duplicatas M2 | 3 |
| registros absorvidos por M2 | 3 |
| conteúdos mestres | 997 |
| identificadores mestres novos | 0 |
| identificadores mestres reutilizados | 997 |
| fusões de mestres existentes | 0 |
| conflitos resolvidos entre fontes | 0 |
| conflitos resolvidos entre duplicatas | 6 |
| candidatos não fundidos | 8 |

## Registros conflitantes consolidados (M2)

Cada grupo reúne cadastros duplicados do mesmo conteúdo, com a mesma chave de
correspondência. Os atributos em conflito foram resolvidos pelas regras de
sobrevivência.

### CM-000042 — Solucionando Desafios do Dia a Dia em Monitoramento de Performance e Acompanhamento de Metas

Registros de origem: 77, 124 → id canônico **77** (menor data_publicacao; empate: menor conteudo_id (registro original)).

| Atributo | conteudo_id 77 | conteudo_id 124 | Registro de ouro | Regra |
|---|---|---|---|---|
| carga_horaria_min | 72 | 89 | **89** | registro publicado mais recentemente (versão vigente) |
| data_publicacao | 2024-01-30 | 2026-06-05 | **2024-01-30** | data mais antiga (primeira publicação do conteúdo) |

### CM-000051 — Melhores Práticas e Arquitetura de Processamento Distribuído com Apache Spark

Registros de origem: 39, 480 → id canônico **39** (menor data_publicacao; empate: menor conteudo_id (registro original)).

| Atributo | conteudo_id 39 | conteudo_id 480 | Registro de ouro | Regra |
|---|---|---|---|---|
| carga_horaria_min | 17 | 29 | **29** | registro publicado mais recentemente (versão vigente) |
| data_publicacao | 2024-02-08 | 2024-04-13 | **2024-02-08** | data mais antiga (primeira publicação do conteúdo) |

### CM-000076 — Princípios Essenciais e Arquitetura de Engenharia de Prompts e Agentes Inteligentes

Registros de origem: 948, 455 → id canônico **948** (menor data_publicacao; empate: menor conteudo_id (registro original)).

| Atributo | conteudo_id 948 | conteudo_id 455 | Registro de ouro | Regra |
|---|---|---|---|---|
| carga_horaria_min | 28 | 16 | **16** | registro publicado mais recentemente (versão vigente) |
| data_publicacao | 2024-03-06 | 2026-01-07 | **2024-03-06** | data mais antiga (primeira publicação do conteúdo) |

## Candidatos não fundidos

Mesmo título, tipo e autor, mas com chave de correspondência diferente. São
tratados como conteúdos distintos (por exemplo, edições de níveis diferentes)
e ficam listados para revisão da curadoria.

| conteudo_ids | Título | Autor | Motivo |
|---|---|---|---|
| 552, 830 | Análise Prática e Demonstração de Previsão de Séries Temporais e Tendências | Eng. Vanessa Cristina Ramos | diferem em nivel e descricao |
| 70, 702 | Construindo Aplicações Robustas com Integração de Conectores com SQLAlchemy e Psycopg3 | Prof. Elmo Batista de Faria | diferem em nivel e descricao |
| 235, 714 | Curso Completo de Auditoria e Monitoramento de Logs de Acesso: Da Teoria à Prática | Dra. Renata Figueiredo Melo | diferem em nivel e descricao |
| 137, 878 | Curso Completo de Gestão de Metadados e Qualidade de Dados Mestres: Da Teoria à Prática | Dr. Marcelo Silveira Neves | diferem em nivel e descricao |
| 94, 179 | Curso Completo de Storytelling com Dados para Apresentações Executivas: Da Teoria à Prática | Eng. Vanessa Cristina Ramos | diferem em nivel e descricao |
| 267, 554 | Especialização em Controle de Acesso Baseado em Papéis (RBAC) com Projetos Práticos | Eng. Bruno César Pires | diferem em nivel e descricao |
| 249, 417 | Guia Definitivo e Boas Práticas sobre Conteinerização com Docker e Docker Compose | Prof. Gabriel Santana Ribeiro | diferem em nivel e descricao |
| 452, 736 | Tech Talk Ep. 138: Melhores Práticas em Métricas de Avaliação de Modelos Preditivos | Profa. Beatriz Helena Nogueira | diferem em nivel e descricao |

## Conflitos entre fontes (M1)

0 conflito(s) entre `silver_catalogo` e `d1_postgres` para o mesmo conteudo_id; resolvidos pela prioridade da fonte.
