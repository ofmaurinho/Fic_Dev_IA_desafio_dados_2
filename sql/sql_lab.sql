-- Consultas do SQL Lab (RF17).
--
-- Todas leem apenas a camada Gold (schema gold) e podem ser reproduzidas a
-- partir dela. superset/configurar_superset.py cadastra cada bloco abaixo
-- como consulta salva no SQL Lab e, quando indicado, como conjunto de dados
-- virtual do dashboard. Cada bloco começa com "-- @consulta: <nome>" e traz
-- os metadados em linhas "-- @<chave>: <valor>".
--
-- Recursos exigidos:  Q1 junção, expressão condicional, função de data
--                     Q2 junção, agregação, expressão condicional, função de data
--                     Q3 junção, agregação, expressão condicional, função de data


-- @consulta: vds_engajamento_interacoes
-- @titulo: Engajamento por interação com atributos do conteúdo
-- @dataset_virtual: sim
-- @finalidade: Base do dashboard de engajamento. Uma linha por interação,
--   enriquecida com os atributos do conteúdo mestre, para filtrar por período,
--   categoria, tipo e nível e calcular usuários ativos e taxa de conclusão.
-- @campos_calculados:
--   mes              = date_trunc('month', data_hora), eixo temporal mensal
--   dia_semana       = nome do dia da semana (to_char ... 'TMDay')
--   periodo_do_dia   = CASE sobre a hora: madrugada (0–5), manhã (6–11),
--                      tarde (12–17), noite (18–23)
--   consumo          = 1 se a interação é de consumo (início, visualização, conclusão)
--   conclusao        = 1 se a interação é conclusão
--   dias_desde_publicacao = data da interação − data de publicação do conteúdo
-- @metricas_no_superset:
--   usuarios_ativos  = COUNT(DISTINCT usuario_chave)
--   taxa_conclusao   = SUM(conclusao) / NULLIF(SUM(consumo), 0)
SELECT
    f.data_hora,
    date_trunc('month', f.data_hora)::DATE             AS mes,
    to_char(f.data_hora, 'TMDay')                       AS dia_semana,
    CASE
        WHEN EXTRACT(HOUR FROM f.data_hora) < 6  THEN 'madrugada'
        WHEN EXTRACT(HOUR FROM f.data_hora) < 12 THEN 'manhã'
        WHEN EXTRACT(HOUR FROM f.data_hora) < 18 THEN 'tarde'
        ELSE 'noite'
    END                                                 AS periodo_do_dia,
    f.usuario_chave,
    f.conteudo_mestre_id,
    d.titulo,
    d.tipo,
    d.categoria,
    d.nivel,
    d.faixa_duracao,
    f.tipo_interacao,
    CASE WHEN f.eh_consumo THEN 1 ELSE 0 END            AS consumo,
    CASE WHEN f.eh_conclusao THEN 1 ELSE 0 END          AS conclusao,
    f.percentual_conclusao,
    f.tempo_consumido,
    f.avaliacao_atribuida,
    f.data - d.data_publicacao                          AS dias_desde_publicacao,
    f.anterior_a_publicacao
FROM gold.fato_interacao f
JOIN gold.dim_conteudo d USING (conteudo_mestre_id);


-- @consulta: vds_conversao_recomendacao
-- @titulo: Conversão das recomendações por categoria e faixa de posição
-- @dataset_virtual: sim
-- @finalidade: Avaliar se o motor de recomendação acerta o que o usuário
--   consome, por categoria, faixa de posição no ranking e status. Considera
--   só a geração vigente (a mais recente de cada usuário).
-- @campos_calculados:
--   faixa_posicao    = CASE: "1–3 (topo)", "4–6", "7–10"
--   mes_geracao      = date_trunc('month', data_geracao)
--   recomendacoes    = COUNT(*)
--   convertidas      = SUM(CASE WHEN convertida THEN 1 ELSE 0 END)
--   concluidas       = SUM(CASE WHEN concluida THEN 1 ELSE 0 END)
--   pontuacao_media  = AVG(pontuacao)
-- @metricas_no_superset:
--   taxa_conversao   = SUM(convertidas) / NULLIF(SUM(recomendacoes), 0)
SELECT
    date_trunc('month', r.data_geracao)::DATE           AS mes_geracao,
    d.categoria,
    d.tipo,
    CASE
        WHEN r.posicao <= 3 THEN '1–3 (topo)'
        WHEN r.posicao <= 6 THEN '4–6'
        ELSE '7–10'
    END                                                 AS faixa_posicao,
    r.status,
    COUNT(*)                                            AS recomendacoes,
    SUM(CASE WHEN r.convertida THEN 1 ELSE 0 END)       AS convertidas,
    SUM(CASE WHEN r.concluida THEN 1 ELSE 0 END)        AS concluidas,
    ROUND(AVG(r.pontuacao), 2)                          AS pontuacao_media
FROM gold.fato_recomendacao r
JOIN gold.dim_conteudo d USING (conteudo_mestre_id)
WHERE r.geracao_vigente
GROUP BY 1, 2, 3, 4, 5;


-- @consulta: lista_acao_conteudos
-- @titulo: Conteúdos para ação: engajamento × avaliação
-- @dataset_virtual: sim
-- @finalidade: Lista de ação para a curadoria. Classifica cada conteúdo com
--   interações pelo engajamento (acima ou abaixo da mediana de usuários) e pela
--   nota média (interações e comentários), indicando o que promover, revisar
--   ou reavaliar.
-- @campos_calculados:
--   usuarios         = COUNT(DISTINCT usuario_chave) nas interações
--   nota_media       = média das notas de interações e comentários
--   meses_publicado  = meses entre a publicação e a última interação (age)
--   classificacao    = CASE: "Promover" (engajamento alto, nota ≥ 4),
--                      "Revisar conteúdo" (engajamento alto, nota < 3,5),
--                      "Divulgar" (engajamento baixo, nota ≥ 4),
--                      "Reavaliar no catálogo" (engajamento baixo, nota < 3,5),
--                      "Acompanhar" (demais)
WITH notas AS (
    SELECT conteudo_mestre_id, avaliacao_atribuida AS nota
    FROM gold.fato_interacao
    WHERE avaliacao_atribuida IS NOT NULL
    UNION ALL
    SELECT conteudo_mestre_id, avaliacao
    FROM gold.fato_comentario
),
engajamento AS (
    SELECT
        conteudo_mestre_id,
        COUNT(DISTINCT usuario_chave) AS usuarios,
        COUNT(*)                      AS interacoes,
        MAX(data_hora)                AS ultima_interacao
    FROM gold.fato_interacao
    GROUP BY conteudo_mestre_id
),
mediana AS (
    SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY usuarios) AS mediana_usuarios
    FROM engajamento
),
base AS (
    SELECT
        d.conteudo_mestre_id,
        d.titulo,
        d.tipo,
        d.categoria,
        d.nivel,
        e.usuarios,
        e.interacoes,
        ROUND(AVG(n.nota), 2)          AS nota_media,
        COUNT(n.nota)                  AS qtd_notas,
        EXTRACT(YEAR FROM age(e.ultima_interacao, d.data_publicacao)) * 12
          + EXTRACT(MONTH FROM age(e.ultima_interacao, d.data_publicacao)) AS meses_publicado,
        m.mediana_usuarios
    FROM gold.dim_conteudo d
    JOIN engajamento e USING (conteudo_mestre_id)
    CROSS JOIN mediana m
    LEFT JOIN notas n USING (conteudo_mestre_id)
    GROUP BY d.conteudo_mestre_id, d.titulo, d.tipo, d.categoria, d.nivel,
             e.usuarios, e.interacoes, e.ultima_interacao, d.data_publicacao, m.mediana_usuarios
)
SELECT
    conteudo_mestre_id,
    titulo,
    tipo,
    categoria,
    nivel,
    usuarios,
    interacoes,
    nota_media,
    qtd_notas,
    meses_publicado,
    CASE
        WHEN usuarios > mediana_usuarios AND nota_media >= 4   THEN 'Promover'
        WHEN usuarios > mediana_usuarios AND nota_media < 3.5  THEN 'Revisar conteúdo'
        WHEN usuarios <= mediana_usuarios AND nota_media >= 4  THEN 'Divulgar'
        WHEN usuarios <= mediana_usuarios AND nota_media < 3.5 THEN 'Reavaliar no catálogo'
        ELSE 'Acompanhar'
    END AS classificacao
FROM base
ORDER BY usuarios DESC, nota_media DESC;


-- @consulta: alerta_conversao_recomendacao
-- @titulo: Alerta — taxa de conversão das recomendações vigentes
-- @dataset_virtual: não
-- @finalidade: Consulta do alerta do Superset (RF18). Devolve um único valor:
--   a taxa de conversão (%) das recomendações da geração vigente. O alerta
--   dispara quando o valor fica abaixo de 5%.
-- @campos_calculados:
--   taxa_conversao_pct = 100 × convertidas / recomendações (geração vigente)
SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE convertida) / NULLIF(COUNT(*), 0), 2)
       AS taxa_conversao_pct
FROM gold.fato_recomendacao
WHERE geracao_vigente;
