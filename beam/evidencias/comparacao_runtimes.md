# Execução do pipeline Beam: DirectRunner × Spark

Regra: engajamento mensal por categoria (`beam/pipeline.py`), lendo a Silver em
Parquet e gravando Parquet. A comparação ignora os campos de auditoria
(`id_execucao`, `runtime`).

| Linhas de entrada | Runtime | Estado | Duração | Interações lidas | Linhas de saída | Saídas iguais |
|---:|---|---|---:|---:|---:|---|
| 1.000 | direct | DONE | 1.0 s | 1.000 | 64 | sim |
| 1.000 | spark | DONE | 49.4 s | 1.000 | 64 | sim |
| 100.000 | direct | DONE | 2.3 s | 100.000 | 64 | sim |
| 100.000 | spark | DONE | 32.2 s | 100.000 | 64 | sim |

## Configuração

- **direct** (1.000 linhas): 
- **spark** (1.000 linhas): `runner=PortableRunner`, `job_endpoint=localhost:8099`, `artifact_endpoint=localhost:8098`, `environment_type=EXTERNAL`, `environment_config=localhost:50000`, `environment_cache_millis=60000`
- **direct** (100.000 linhas): `runner=DirectRunner`
- **spark** (100.000 linhas): `runner=PortableRunner`, `job_endpoint=localhost:8099`, `artifact_endpoint=localhost:8098`, `environment_type=EXTERNAL`, `environment_config=localhost:50000`, `environment_cache_millis=60000`
- Cliente: Python 3.13.5, Apache Beam 2.76.0, pyarrow 25.0.1, Windows-11-10.0.26200-SP0

## Cluster Spark

- Master `spark://spark-master:7077` (ALIVE), 2 workers: 172.30.0.3 (2 cores, 1024 MB), 172.30.0.4 (2 cores, 1024 MB)

| Aplicação | Cores | Duração | Estado |
|---|---:|---:|---|
| BeamApp-root-0927233844-d1e750a5_671b35af-599f-4b84-a659-936c003906b1 | 4 | 36.6 s | FINISHED |
| BeamApp-root-0927234014-90c294ee_28637131-c157-4ccc-a059-b80692b759dc | 4 | 47.6 s | FINISHED |
| BeamApp-root-0927234114-4fe71d8f_080e67fd-db66-4e5e-b20e-c745fd751ada | 4 | 30.5 s | FINISHED |
