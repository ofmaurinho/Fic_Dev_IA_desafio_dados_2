# Técnicas de Proteção de Dados e Privacidade (Privacy by Design)

As estratégias de proteção de dados implementadas no pipeline de engenharia (Apache Beam) e na camada de consumo (Superset/SQL) visam mitigar riscos de vazamento de Identificadores Pessoais (PII). As decisões arquiteturais descritas abaixo garantem conformidade técnica com os princípios de segurança e minimização da LGPD.

## 1. Comparativo das Técnicas Aplicadas

| Técnica | Propósito Principal | Reversibilidade | Aplicação Arquitetural no Projeto |
| :--- | :--- | :--- | :--- |
| **Hashing com Salt** | Invalidação de dados diretos (ex: e-mail) | Irreversível | Transformação no Apache Beam. Impede que o e-mail real chegue ao Data Lake/Data Warehouse. |
| **Pseudonimização** | Substituição de chaves de identificação | Reversível (exclusivamente via tabela De-Para) | Apache Beam (Saídas Múltiplas). Substitui o `usuario_id` por um hash consistente no fluxo principal analítico. |
| **Mascaramento** | Ofuscação visual para o analista final | Irreversível na exibição | Apache Superset / Camada Ouro (SQL). Oculta partes do pseudônimo no dashboard. |
| **Minimização** | Redução da granularidade e risco | Irreversível | Views do banco de dados e rotinas de ETL. Uso restrito a agregações (`COUNT`, `SUM`). |

## 2. Justificativas e Implementação Técnica

### Hashing com Salt
A técnica de hashing criptográfico (SHA-256) combinada com um *Salt* (chave secreta injetada via variável de ambiente) foi escolhida para campos que transitam no fluxo, mas não possuem valor analítico direto para os dashboards.
* **Justificativa:** O hashing simples é vulnerável a ataques de dicionário (Rainbow Tables). A adição do *Salt* garante que a ofuscação seja robusta e determinística apenas dentro do escopo do projeto, inviabilizando o processo de engenharia reversa para descobrir os e-mails originais.
* **Implementação:** Executado em memória pela classe transformadora no Apache Beam (`pipeline.py`). O campo original é deletado do registro imediatamente após a conversão, não sendo gravado em nenhum arquivo Parquet da camada final.

### Pseudonimização e Segregação de Acessos (De-Para)
O campo `usuario_id` foi transformado em um identificador alfanumérico (`usuario_chave`).
* **Justificativa:** O cálculo de métricas como "Usuários Ativos Mensais" ou "Taxa de Conclusão por Usuário" exige um identificador persistente. A pseudonimização atende a esse requisito sem expor a identidade real, cumprindo o Art. 13 da LGPD (dados anonimizados/pseudonimizados não são considerados dados pessoais se as chaves de reversão estiverem estritamente controladas).
* **Implementação:** Implementado no Apache Beam utilizando *Side Outputs* (Saídas Secundárias). O pipeline emite o registro protegido para o fluxo analítico principal (camada Gold) e desvia a relação `usuario_id_real` <=> `usuario_chave` para uma tabela "De-Para". Este arquivo de mapeamento é salvo em um bucket/diretório isolado, acessível apenas por administradores de segurança e Data Protection Officers (DPOs), garantindo que os analistas de dados não consigam reverter os dados.

### Mascaramento Visual e Minimização Analítica
A proteção em nível de visualização foi applied nas consultas do Apache Superset e nas Views da camada Gold.
* **Justificativa:** O Princípio do Privilégio Mínimo dita que usuários de negócios e analistas de BI devem acessar apenas o nível de detalhe necessário para suas funções. Mesmo o pseudônimo completo não precisa ser exposto em relatórios de linha a linha.
* **Implementação:** No arquivo `sql_lab.sql` e na criação das *Views*, as datas exatas de interação foram convertidas em faixas de comportamento (ex: "Inativo/Explorador", "Engajado"). O identificador já pseudonimizado sofreu uma ofuscação de string via SQL (`CONCAT('usr_', LEFT(usuario_chave, 4), '***', RIGHT(usuario_chave, 4))`), assegurando que planilhas exportadas diretamente do dashboard do Superset não contenham dados rastreáveis ou reconstituíveis em hipótese alguma.







