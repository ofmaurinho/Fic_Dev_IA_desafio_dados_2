# Regras de qualidade de dados

Responsável: Estudante 2 (RF31). Implementação: `qualidade/executar_testes.py`.

## Quando e sobre o quê

Os testes rodam depois da Silver e antes da Gold. Eles avaliam os arquivos
Silver gerados pelo Apache Hop e os comparam com a Bronze e a quarentena. As
regras são aplicadas **por fonte** (`catalogo`, `interacoes`, `comentarios`).
Os resultados são gravados **por execução e por fonte**:

- **Banco:** tabela `qualidade.resultado_teste`, uma linha por regra e fonte,
  e tabela `qualidade.execucao`, uma linha por execução com o status final.
  O DDL está em `sql/qualidade.sql`.
- **Arquivo:** `qualidade/resultados/<data>_<id>.json`, com uma amostra de até
  5 registros violados por regra (identificador e mensagem).
- **Histórico:** `qualidade/resultados/evolucao.md`, com a evolução das
  métricas entre execuções.

## Severidade e bloqueio da Gold

| Severidade | Efeito | Status da execução |
|---|---|---|
| `critica` | Bloqueia a publicação da Gold | `falha` (código de saída 1) |
| `alerta` | Publica a Gold com ressalva registrada | `sucesso_com_ressalvas` (código 0) |

- **Sem violações:** status `sucesso` (código 0).
- **Erro de arquivo ou banco:** a execução não é concluída (código 2) e a Gold
  também fica bloqueada.

O workflow chama `qualidade/executar_testes.py --id-execucao <id do workflow>`
e só segue para a Gold com código 0. A decisão também fica registrada em
`qualidade.execucao.gold_liberada`, e a publicação da Gold pode conferir
`qualidade.v_ultima_execucao`.

## Catálogo de regras

As métricas são percentuais de 0 a 100. A tabela abaixo é gerada a partir do
código com `python qualidade/executar_testes.py --documentar`.

<!-- regras:inicio -->
| Regra | Dimensão | Descrição | Fontes | Fórmula | Limite | Severidade | Ação |
|---|---|---|---|---|---|---|---|
| QD01 | Completude | Campos obrigatórios preenchidos na Silver | catalogo, interacoes, comentarios | registros sem campo obrigatório vazio / registros × 100 | >= 100% | critica | Bloquear a publicação da Gold. Corrigir a regra de campos obrigatórios da Silver e reprocessar. |
| QD02 | Validade | Formato, domínio e faixa dos valores (tipos, níveis, percentuais, notas, datas não futuras) | catalogo, interacoes, comentarios | registros com todos os valores válidos / registros × 100 | >= 100% | critica | Bloquear a publicação da Gold. Enviar os registros inválidos à quarentena e reprocessar. |
| QD03 | Unicidade | Chave de negócio única por fonte | catalogo, interacoes, comentarios | registros não duplicados na chave / registros × 100 | >= 100% | critica | Bloquear a publicação da Gold. Revisar a deduplicação da Silver e reprocessar. |
| QD04 | Integridade referencial | conteudo_id existe no catálogo Silver e usuario_id existe em public.usuario | interacoes, comentarios | registros com referências válidas / registros × 100 | >= 100% | critica | Bloquear a publicação da Gold. Colocar os órfãos em quarentena ou carregar o cadastro faltante. |
| QD05 | Consistência | Tipo da interação coerente com as medidas (conclusão ⇔ 100%; avaliação ⇒ nota) | interacoes | registros coerentes / registros × 100 | >= 100% | critica | Bloquear a publicação da Gold. Revisar a origem das interações; a taxa de conclusão ficaria incorreta. |
| QD06 | Consistência | Evento (interação ou comentário) não anterior à publicação do conteúdo | interacoes, comentarios | eventos na data de publicação ou depois / eventos × 100 | >= 95% | alerta | Publicar a Gold com ressalva e acionar a curadoria do catálogo para revisar as datas. |
| QD07 | Consistência | Conservação de volume: Bronze = Silver + quarentena | catalogo, interacoes, comentarios | (1 − |bronze − silver − quarentena| / bronze) × 100 | >= 100% | critica | Bloquear a publicação da Gold. Há registros perdidos ou criados entre as camadas; revisar o pipeline Silver. |
| QD08 | Validade | Taxa de rejeição para a quarentena | catalogo, interacoes, comentarios | registros em quarentena / registros na Bronze × 100 | <= 5% | alerta | Publicar a Gold com ressalva, analisar a quarentena e reprocessar os corrigidos. |
<!-- regras:fim -->

## Decisões

- **Verificação independente:** a Silver já filtra nulos, domínios e
  duplicidades no Hop. Os testes verificam o **resultado** com regras
  próprias, e não a configuração do pipeline, detectando erros de
  configuração ou de regra do próprio Hop.
- **Limite de QD06 (≥ 95%):** o dado atual tem 7,7% das interações e 5,2% dos
  comentários com data anterior à publicação do conteúdo. A causa provável é o
  gerador de dados fictícios, não o pipeline. O problema é real, mas não
  invalida os KPIs de engajamento, então vira ressalva e não bloqueio. O
  limite de 95% separa um desvio pontual de um problema sistemático.
- **Limite de QD08 (≤ 5%):** até 5% de rejeição é tratada como ruído
  operacional. Acima disso, a quarentena precisa de análise antes do próximo
  ciclo.
- **QD04 contra o catálogo Silver:** a Silver valida referências contra
  `public.conteudo` (Desafio 1). O teste confere contra o catálogo **Silver**,
  que é o que a Gold usa como dimensão.

## Execução

Pré-requisitos: dependências de `requirements.txt` e um arquivo `.env` na
raiz, criado a partir de `.env.example` com a conexão do PostgreSQL. O schema
`qualidade` é criado automaticamente.

```bash
.venv/Scripts/python qualidade/executar_testes.py                    # Silver atual
.venv/Scripts/python qualidade/executar_testes.py --id-execucao <id> # id do workflow
.venv/Scripts/python qualidade/simular_lote_com_defeitos.py          # demonstra o bloqueio
.venv/Scripts/python qualidade/executar_testes.py --documentar       # atualiza a tabela acima
```

**Integração com o workflow do Hop:** adicionar uma ação *Shell* entre a
Silver e a Gold, com o comando acima e o `id_execucao` do workflow. A ação só
segue para a Gold com código 0. Os códigos 1 e 2 levam ao desvio de falha.

## Evidências

`qualidade/resultados/evolucao.md` mostra três execuções.

| # | Lote | Status | O que mostra |
|---|---|---|---|
| 1 | Silver real | `sucesso_com_ressalvas` | Só QD06 abaixo do limite (interações 92,3%, comentários 94,8%). Gold liberada |
| 2 | Lote simulado com defeitos (`simular_lote_com_defeitos.py`) | `falha` | Todos os defeitos injetados foram detectados com a contagem exata. Gold bloqueada (código 1) |
| 3 | Silver real, após o lote rejeitado | `sucesso_com_ressalvas` | Métricas voltam ao patamar da execução 1 |

Métricas acompanhadas na evolução:

- **QD08 (taxa de quarentena de interações):** 0% → 7,4% → 0%.
- **QD03 (unicidade de interações):** 100% → 99,5% → 100%.
- **QD07 (conservação de volume):** 100% → 99,5% → 100%.
- **QD06 (consistência temporal):** estável em 92,3%, pois é uma ressalva
  conhecida da fonte.

As mesmas séries estão em `qualidade.v_evolucao_metricas`, fonte do gráfico
de evolução no Superset (RF18).

Cada arquivo `qualidade/resultados/<data>_<id>.json` traz o resultado de cada
regra e fonte, com amostras de registros violados, por exemplo
`usuario_id=5|conteudo_id=99999|tipo_interacao=conclusão|data_hora=...` →
"conteudo_id ausente no catálogo Silver".
