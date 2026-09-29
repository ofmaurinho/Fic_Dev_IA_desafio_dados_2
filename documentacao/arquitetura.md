# Arquitetura de Dados

## 1. Visão Geral da Arquitetura
A arquitetura de dados desenvolvida substitui scripts isolados por um fluxo automatizado, governado e escalável. O modelo adota uma separação clara em camadas (Bronze, Silver e Gold), integrando orquestração com Apache Hop, processamento distribuído com Apache Beam e consumo analítico via Apache Superset.

## 2. Classificação: Arquitetura Híbrida (ETL + ELT)
O fluxo principal é classificado como uma arquitetura híbrida (ETL e ELT), desenhada para equilibrar custo, governança, desempenho e facilidade de reprocessamento:
* **Extração (E):** O Apache Hop extrai os dados legados a partir de arquivos CSV, JSON e bancos de dados PostgreSQL e MongoDB.
* **Carga (L) - Bronze:** Os dados são carregados em seu estado bruto para a camada Bronze, sem transformações destrutivas, garantindo um repositório auditável com campos de origem e data da ingestão.
* **Transformação (T) - Silver:** O Apache Hop executa transformações de padronização, limpeza, tratamento de valores ausentes e gestão de quarentena, gravando o resultado no formato Parquet.
* **Transformação (T) - Gold:** O Apache Beam processa os dados em Parquet em ambiente distribuído para executar agregações. O SQL Lab do Superset atua como motor complementar ao criar conjuntos de dados virtuais e modelagens orientadas às perguntas de negócio.

## 3. Limitações da Solução Anterior
A arquitetura baseada apenas em scripts isolados apresentava limitações operacionais severas:
* Falta de rastreabilidade e incapacidade de orquestrar interrupções seguras diante de falhas em etapas dependentes.
* Inexistência de segregação entre dados brutos e padronizados, dificultando cargas parciais e correções.
* Ausência de mecanismos de governança, proteção de dados pessoais e gestão automatizada de registros inválidos.