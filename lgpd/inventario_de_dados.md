# Inventário de Dados Pessoais (LGPD)

Este documento mapeia os dados processados no pipeline analítico, classificando-os conforme as diretrizes da Lei Geral de Proteção de Dados (LGPD) para garantir transparência, adequação de finalidade e controle rigoroso de retenção.

| Campo Origem | Tipo de Dado | Classificação LGPD | Finalidade no Tratamento Analítico | Tempo de Retenção |
| :--- | :--- | :--- | :--- | :--- |
| `email` | String | Dado Pessoal Direto | Identificação única nos sistemas transacionais e comunicação. Não possui finalidade analítica na camada Gold. | Até o término da relação com o usuário ou solicitação de exclusão (Art. 15, LGPD). Destruído em trânsito no ETL. |
| `usuario_id` | Inteiro | Dado Pessoal Direto | Chave primária de relacionamento entre usuários e suas interações com a plataforma. | Até solicitação de exclusão. Substituído por pseudônimo antes da consolidação analítica. |
| `usuario_chave` | String (Hash/UUID) | Dado Pseudonimizado | Permitir a contagem de usuários distintos (ativos) e rastreamento de engajamento sem exposição da identidade real. | Indeterminado na camada Gold, pois o dado é irreversível sem acesso à tabela de correspondência (De-Para). |
| `data_hora` | Timestamp | Dado Comportamental | Análise de padrões de acesso, sazonalidade e cálculo de retenção. | Agregado mensalmente na camada Gold. Os logs brutos são retidos por 5 anos para auditoria de segurança. |