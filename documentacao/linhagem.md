# Linhagem de Dados (Data Lineage)

## 1. Fluxo de Transformação
Este mapeamento documenta o caminho percorrido pelos dados desde as fontes até o consumo analítico. A catalogação, as classificações e os termos de negócio estão registrados no OpenMetadata.
* **Fontes:** Arquivos estáticos (CSV/JSON) e bases transacionais herdadas do Desafio 1.
* **Camada Bronze:** Ingestão literal sem transformações destrutivas, recebendo campos de auditoria de ingestão e execução.
* **Camada Silver:** Dados padronizados, validados e deduplicados por chaves de negócio. Registros inconsistentes são enviados à quarentena, e identificadores pessoais recebem pseudonimização, mascaramento ou hashing. O armazenamento utiliza formato Parquet.
* **Processamento (Apache Beam):** Agregações temporais e cálculos distribuídos utilizando DirectRunner ou runtime Spark.
* **Camada Gold:** Tabelas de fatos e dimensões consolidadas sem exposição direta de dados pessoais não tratados, estruturadas para o consumo dos KPIs.
* **Consumo (Superset):** Conjuntos de dados virtuais modelados e documentados no SQL Lab, alimentando os gráficos e alertas do dashboard.

## 2. Rastreabilidade de Indicador (Exemplo: Usuários Ativos)
Para localizar a origem da métrica "Usuários Ativos" consumida pelo negócio:
1. **Consumo:** O dashboard exibe a contagem distinta obtida a partir do dataset virtual estruturado no SQL Lab.
2. **Ouro (Gold):** O dataset virtual consulta exclusivamente a tabela agregada de interações e engajamento disponível na camada Gold.
3. **Prata (Silver):** O identificador agrupado na Gold corresponde à chave pseudonimizada gerada na camada Silver, substituindo a identificação direta do usuário por questões de privacidade (LGPD).
4. **Bronze/Fonte:** A origem técnica da chave rastreia de volta ao identificador original bruto, armazenado de forma isolada na camada Bronze a partir dos arquivos JSON de interações.