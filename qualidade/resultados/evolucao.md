# Evolução das métricas de qualidade

Pior valor de cada regra entre as fontes em cada execução, em %: mínimo
para regras de conformidade (≥) e máximo para a taxa de quarentena
(QD08, ≤). ✖ = limite violado em ao menos uma fonte. Gerado por
`qualidade/executar_testes.py` a partir de `qualidade.v_evolucao_metricas`.

| Execução | Origem | Status | QD01 | QD02 | QD03 | QD04 | QD05 | QD06 | QD07 | QD08 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-09-27 19:56:46 `0ed0aa03` | silver | sucesso_com_ressalvas | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 92.3 ✖ | 100.0 | 0.0 |
| 2026-09-27 19:56:48 `045645df` | simulacao | falha | 99.8 ✖ | 99.7 ✖ | 99.5 ✖ | 99.8 ✖ | 99.8 ✖ | 92.3 ✖ | 99.5 ✖ | 7.4 ✖ |
| 2026-09-27 19:56:49 `b8f874c2` | silver | sucesso_com_ressalvas | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 92.3 ✖ | 100.0 | 0.0 |
