# Benchmark CSV × Parquet — interações Silver

- Execução: `db1bf214-2001-483a-ae3c-1d71415ad5e3` em 2026-09-27T19:16:12
- Ambiente: Windows-11-10.0.26200-SP0, 12 CPUs, Python 3.13.5, pyarrow 25.0.1, pandas 3.0.6
- Compressão Parquet: snappy; mês da leitura seletiva: 2026-03
- Repetições por medição: 5 (após 1 aquecimento); tempos = mediana

## Fator 1 — 1.000 linhas

| Formato | Tamanho | % do CSV | Leitura completa | Leitura seletiva |
|---|---:|---:|---:|---:|
| csv | 127.4 KB | 100% | 9.6 ms | 6.0 ms |
| parquet_particionado (8 arquivos) | 55.2 KB | 43% | 7.9 ms | 3.8 ms |
| parquet_unico | 23.6 KB | 19% | 2.6 ms | 2.3 ms |

## Fator 100 — 100.000 linhas

| Formato | Tamanho | % do CSV | Leitura completa | Leitura seletiva |
|---|---:|---:|---:|---:|
| csv | 12.62 MB | 100% | 387.0 ms | 132.5 ms |
| parquet_particionado (8 arquivos) | 653.7 KB | 5% | 15.0 ms | 4.8 ms |
| parquet_unico | 248.5 KB | 2% | 13.8 ms | 7.9 ms |

## Fator 1000 — 1.000.000 linhas

| Formato | Tamanho | % do CSV | Leitura completa | Leitura seletiva |
|---|---:|---:|---:|---:|
| csv | 127.13 MB | 100% | 3818.2 ms | 1147.1 ms |
| parquet_particionado (8 arquivos) | 5.93 MB | 5% | 89.2 ms | 9.7 ms |
| parquet_unico | 2.64 MB | 2% | 104.7 ms | 43.2 ms |
