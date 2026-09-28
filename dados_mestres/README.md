# Dados mestres — Conteúdo

Responsável: Estudante 2 (RF30). Implementação:
`dados_mestres/consolidar_conteudo.py`. Estrutura no banco:
`sql/dados_mestres.sql` (schema `mestre`).

## Entidade e definição

**Conteúdo** é cada material educacional publicado na plataforma (curso,
vídeo, artigo ou podcast). É a entidade que liga interações, comentários,
recomendações e KPIs, e é a dimensão principal da Gold. Um cadastro duplicado
divide o engajamento de um mesmo material entre dois identificadores.

| Item | Definição |
|---|---|
| Identificador mestre | `conteudo_mestre_id` (`CM-000001`), atribuído pelo processo e estável entre execuções |
| Chave de negócio | Título, tipo, autor (sem titulação), nível e descrição, todos normalizados. O hash SHA-256 fica em `chave_correspondencia` |
| Chave de origem | `conteudo_id` de cada fonte, mapeado em `mestre.conteudo_correspondencia` |
| Atributos essenciais | titulo, tipo, categoria, nivel, carga_horaria_min, data_publicacao, descricao, autor |
| Fonte de referência | `silver_catalogo`: catálogo Silver do Apache Hop, validado pelos testes de qualidade (RF31) e atualizado a cada execução |
| Fonte secundária | `d1_postgres`: `public.conteudo` + `public.categoria` do Desafio 1, que é o cadastro usado pelas recomendações |

**Normalização:** minúsculas, sem acentos, pontuação e espaços colapsados. No
autor, as titulações iniciais (Prof., Profa., Dr., Dra., Eng. etc.) são
removidas, para que "Dr. Fulano" e "Fulano" correspondam.

## Regras de correspondência

| Regra | Condição | Resultado |
|---|---|---|
| **M1** | Mesmo `conteudo_id` nas duas fontes | Mesmo conteúdo. Os atributos são resolvidos pela prioridade da fonte |
| **M2** | Mesma chave de negócio com `conteudo_id` diferentes | Cadastros duplicados, fundidos em um único conteúdo mestre |
| Candidato não fundido | Mesmo título, tipo e autor, mas nível ou descrição diferentes | Conteúdos distintos (edições de níveis diferentes), listados para revisão da curadoria |

A regra M2 exige nível e descrição iguais porque o catálogo tem 11 pares com
o mesmo título, tipo e autor. Em 8 deles o nível e a descrição mudam, por
exemplo um curso Básico e outro Avançado, e fundi-los apagaria conteúdos
reais. Nos 3 pares restantes, só a carga horária e a data de publicação
divergem, o que caracteriza o mesmo material cadastrado duas vezes.

## Deduplicação e sobrevivência

**Entre fontes (M1):** vale o valor da fonte de maior prioridade
(`silver_catalogo` > `d1_postgres`). Um valor nulo na fonte prioritária é
preenchido pela seguinte.

**Entre duplicatas (M2):**

| Atributo | Regra de sobrevivência | Justificativa |
|---|---|---|
| `conteudo_id` canônico | Registro com a menor `data_publicacao`; no empate, o menor `conteudo_id` | O primeiro cadastro é o original |
| titulo, tipo, autor, nivel, descricao | Valor do registro sobrevivente | São iguais após a normalização, pela própria regra de correspondência |
| categoria, carga_horaria_min | Registro publicado mais recentemente | Reflete a versão vigente do material |
| data_publicacao | Data mais antiga | Data em que o conteúdo passou a existir |

Todo conflito resolvido é registrado em `mestre.conteudo_conflito`, com os
valores de cada registro, o valor escolhido e a regra aplicada.

## Estrutura no banco (schema `mestre`)

| Objeto | Conteúdo |
|---|---|
| `conteudo_correspondencia` | (fonte, id_origem) → `conteudo_mestre_id`, com a regra aplicada e se o registro é o sobrevivente. É **persistente**: o upsert preserva `primeira_vez_em` |
| `conteudo` | Registro de ouro, uma linha por conteúdo mestre. É reconstruído a cada execução |
| `conteudo_conflito` | Auditoria dos conflitos da execução mais recente |
| `seq_conteudo_mestre` | Sequência que gera novos identificadores |

**Estabilidade do identificador:** antes de criar um identificador novo, o
processo procura os membros do grupo na tabela de correspondência.
- **Identificador existente:** se algum membro já tem identificador mestre, o
  grupo reutiliza esse identificador.
- **Fusão de mestres:** se membros de mestres diferentes passam a formar um
  só grupo, mantém-se o menor identificador e a fusão é registrada nas
  evidências.

## Demonstração (`dados_mestres/evidencias/consolidacao_conteudo.md`)

| Indicador | Valor |
|---|---:|
| Registros por fonte | 1000 (Silver) + 1000 (D1) |
| Correspondências M1 | 1000, com 0 conflitos entre fontes, pois as duas estão idênticas hoje |
| Grupos de duplicatas M2 | 3, com 6 conflitos resolvidos |
| Conteúdos mestres | 997 |
| Candidatos não fundidos | 8 |

Exemplo de dois registros conflitantes, os `conteudo_id` 77 e 124 do vídeo
"Solucionando Desafios do Dia a Dia em Monitoramento de Performance…":

| Atributo | 77 | 124 | Registro de ouro (CM-000042) | Regra |
|---|---|---|---|---|
| carga_horaria_min | 72 | 89 | **89** | Mais recente (versão vigente) |
| data_publicacao | 2024-01-30 | 2026-06-05 | **2024-01-30** | Mais antiga (primeira publicação) |

O `conteudo_id` canônico é o 77, o primeiro cadastro, e os dois registros de
origem apontam para CM-000042 em `mestre.conteudo_correspondencia`.

**Estabilidade verificada:** a segunda execução reutilizou os 997
identificadores e a tabela de correspondência ficou idêntica, pelo mesmo hash.

A regra de prioridade entre fontes foi verificada com dados alterados em
memória, sem gravar no banco:
- **Nível divergente no D1:** mantém o valor da Silver.
- **Autor nulo na Silver:** preenchido pelo D1.

## Execução

Depende do `.env` com a conexão do PostgreSQL (ver `.env.example`) e da Silver
aprovada nos testes de qualidade.

```bash
.venv/Scripts/python dados_mestres/consolidar_conteudo.py [--id-execucao <id do workflow>]
```

No workflow, a etapa roda depois do quality gate e antes da Gold. A Gold usa
`conteudo_mestre_id` como chave da dimensão de conteúdo e traduz o
`conteudo_id` das interações, comentários e recomendações pela tabela de
correspondência. Assim, o engajamento dos cadastros duplicados é somado no
mesmo conteúdo.

## Limitações

- **Correspondência exata:** a correspondência é exata sobre a chave
  normalizada. Variações de grafia no título (erros de digitação, abreviações)
  não são detectadas; uma evolução seria usar similaridade de texto com
  revisão manual.
- **Candidatos sem fluxo de aprovação:** os candidatos não fundidos só são
  listados. Não há um fluxo de aprovação da curadoria para forçar ou impedir
  uma fusão.
- **Registros removidos:** um registro que sai das fontes continua na tabela
  de correspondência (histórico), mas deixa de gerar registro de ouro.
