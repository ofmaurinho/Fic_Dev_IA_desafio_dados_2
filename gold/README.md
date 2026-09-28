# Camada Gold

Responsável: Estudante 2 (RF26).

| Arquivo | Conteúdo |
|---|---|
| `gold/publicar_gold.py` | Orquestra a publicação |
| `sql/camada_silver.sql` | Schema `silver` no PostgreSQL |
| `sql/camada_gold.sql` | Schema `gold`: tabelas, carga e visões |

## Perguntas de negócio

| # | Pergunta | Objeto da Gold |
|---|---|---|
| P1 | Como evoluem os usuários ativos, o consumo e a taxa de conclusão mês a mês? | `gold.vw_kpi_mensal` |
| P2 | Quais categorias engajam mais em cada mês? | `gold.kpi_engajamento_mensal_categoria` (Apache Beam) |
| P3 | Quais conteúdos engajam, são bem avaliados e convertem recomendações? | `gold.vw_desempenho_conteudo` |
| P4 | As recomendações convertem? A posição e o status influenciam? | `gold.vw_conversao_recomendacao` |

## Modelo

Esquema estrela: a chave de conteúdo é o **identificador mestre** (RF30), e o
usuário aparece apenas como **pseudônimo**.

| Objeto | Tipo | Grão | Chave | Origem |
|---|---|---|---|---|
| `dim_conteudo` | Dimensão | Conteúdo mestre | `conteudo_mestre_id` | `mestre.conteudo` |
| `dim_usuario` | Dimensão | Usuário | `usuario_chave` | `public.usuario` + `silver.interacao` |
| `fato_interacao` | Fato | Uma interação | (`usuario_chave`, `conteudo_id_origem`, `tipo_interacao`, `data_hora`) | `silver.interacao` |
| `fato_comentario` | Fato | Um comentário | `comentario_hash` | `silver.comentario` |
| `fato_recomendacao` | Fato | Uma recomendação | `recomendacao_id` | `public.recomendacao` (Desafio 1) |
| `kpi_engajamento_mensal_categoria` | Agregado | Mês × categoria | (`ano_mes`, `categoria`) | Pipeline Beam (`beam/pipeline.py`) |
| `vw_kpi_mensal` | Visão | Mês | `ano_mes` | `fato_interacao` |
| `vw_desempenho_conteudo` | Visão | Conteúdo mestre | `conteudo_mestre_id` | Dimensão e fatos |
| `vw_conversao_recomendacao` | Visão | Posição × status (geração vigente) | (`posicao`, `status`) | `fato_recomendacao` |
| `publicacao` | Auditoria | Uma publicação | `id_execucao` | `gold/publicar_gold.py` |

As colunas `conteudo_id_origem` e `id_execucao_silver` dos fatos permitem
rastrear um valor do dashboard até o registro Silver que o originou (RF29).

## Regras de cálculo (base do glossário, RF28)

| Termo | Regra | Onde |
|---|---|---|
| **Usuário ativo** | Usuário com ao menos uma interação de qualquer tipo no período (mês) | `vw_kpi_mensal.usuarios_ativos`, `kpi_engajamento_mensal_categoria.usuarios_ativos` |
| **Interação de consumo** | Interação do tipo início, visualização ou conclusão (`gold.eh_consumo`) | `fato_interacao.eh_consumo` |
| **Taxa de conclusão** | Conclusões / interações de consumo, com 4 casas decimais | `vw_kpi_mensal`, `vw_desempenho_conteudo`, `kpi_engajamento_mensal_categoria` |
| **Conversão de recomendação** | Recomendação cujo usuário consumiu o conteúdo mestre recomendado em qualquer data. Conta só a geração vigente, a mais recente de cada usuário. Taxa = convertidas / recomendações | `fato_recomendacao.convertida`, `vw_conversao_recomendacao.taxa_conversao` |
| Conversão estrita | Consumo **depois** de `data_geracao` | `fato_recomendacao.convertida_apos_geracao` |
| Avaliação média | Média das notas atribuídas nas interações (nulas ignoradas) | `vw_kpi_mensal`, `vw_desempenho_conteudo` |
| Faixa de duração | curta (< 30 min), média (30–180 min), longa (> 180 min) de `carga_horaria_min` | `dim_conteudo.faixa_duracao` |

**Sobre a conversão:** a equipe escolheu a regra "em qualquer data" porque as
3000 recomendações do Desafio 1 foram geradas em 12/09/2026, depois de todas
as interações (jan–ago/2026), e a regra estrita daria 0%.
- **O que a regra mede:** se o motor recomenda conteúdos que o usuário de fato
  consome. Não mede se a recomendação causou o consumo.
- **Resultado atual:** 39 de 1500 recomendações vigentes (2,6%).
- **Próximos ciclos:** a regra estrita já é calculada e passa a fazer sentido
  quando chegarem interações posteriores à geração.

## Controles

- **Quality gate:** a publicação só ocorre se a execução de qualidade (RF31)
  liberou a Gold **e** avaliou exatamente os arquivos Silver atuais. Na
  execução, os testes gravam a impressão SHA-256 dos arquivos, e a publicação
  a recalcula antes de publicar.
  - Com o `--id-execucao` do workflow, vale a execução de qualidade de mesmo id.
  - Sem ele, vale a mais recente sobre a Silver real.
- **Sem carga parcial:** a carga da Silver no banco, a Gold e o registro em
  `gold.publicacao` estão na mesma transação. Qualquer erro desfaz tudo.
- **Minimização de dados pessoais (LGPD, RF32):**
  - O `usuario_id` não chega à Gold. No lugar dele vai `usuario_chave`, um
    HMAC-SHA256 com chave secreta (`PSEUDONIMIZACAO_CHAVE` no `.env`, fora do
    repositório). A chave só existe durante a transação
    (`set_config(..., true)`).
  - O texto livre dos comentários fica só na Silver.
- **Sem acesso à Bronze:** a Bronze existe só em arquivo e não está no banco.
  O Superset terá um usuário somente leitura restrito ao schema `gold`,
  configurado no RF17/RF18.

## Verificações realizadas

| Verificação | Resultado |
|---|---|
| Reconciliação Gold (SQL) × pipeline Beam | Total de interações e taxa de conclusão idênticos nos 8 meses |
| Dado mestre na Gold | CM-000042 soma as interações dos cadastros duplicados 77 e 124 |
| Colunas `usuario_id` ou `comentario` na Gold | Nenhuma |
| Quality gate reprovado (lote simulado) | Publicação bloqueada, código 1 |
| Silver alterada depois dos testes | Publicação bloqueada, código 1 |
| Falha no fim da transação (`SELECT 1/0` injetado) | Nada publicado; Silver e Gold inalteradas |
| Chave de pseudonimização ausente | Publicação recusada, código 2 |

Contagens e amostras em `gold/evidencias/`.

## Execução

Ordem no workflow:

1. Silver no Hop
2. `qualidade/executar_testes.py`
3. `beam/exportar_parquet.py`
4. `beam/pipeline.py`
5. `dados_mestres/consolidar_conteudo.py`
6. `gold/publicar_gold.py`

```bash
.venv/Scripts/python gold/publicar_gold.py [--id-execucao <id do workflow>]
```

Códigos de saída:
- **0:** publicada.
- **1:** bloqueada pelo quality gate ou por pré-requisito ausente (dados
  mestres, saída do Beam).
- **2:** erro. Nada foi publicado.

## Limitações

- **Carga da Silver no banco:** a Silver do Hop é gravada em arquivo, e o
  banco recebe essa Silver por este script. Se o workflow do Hop passar a
  gravar a Silver direto no PostgreSQL, a etapa de cópia pode ser retirada.
- **Atualidade da saída do Beam:** a publicação exige que a saída do Beam
  exista, mas não confere se ela foi gerada a partir da mesma Silver. No
  workflow, o mesmo `id_execucao` fica gravado na saída do Beam
  (`kpi_engajamento_mensal_categoria.id_execucao`).
- **`conteudos_consumidos` no agregado do Beam:** conta o `conteudo_id` de
  origem. Nas visões em SQL, conta o conteúdo mestre, e a diferença aparece só
  nos 3 conteúdos duplicados.
- **Troca da chave de pseudonimização:** trocar a chave muda todos os
  pseudônimos. Os históricos que dependem de `usuario_chave` precisam ser
  republicados juntos.
