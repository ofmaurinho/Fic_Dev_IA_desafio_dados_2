-- 1. Quantidade de registros por tabela

SELECT COUNT(*) AS total_categorias
FROM categoria;

SELECT COUNT(*) AS total_conteudos
FROM conteudo;

SELECT COUNT(*) AS total_usuarios
FROM usuario;

SELECT COUNT(*) AS total_interacoes
FROM interacao;


-- 2. Conteúdos por categoria

SELECT
    c.nome AS categoria,
    COUNT(co.conteudo_id) AS total_conteudos
FROM categoria c
LEFT JOIN conteudo co
    ON co.categoria_id = c.categoria_id
GROUP BY c.nome
ORDER BY total_conteudos DESC;


-- 3. Interações por tipo

SELECT
    tipo_interacao,
    COUNT(*) AS total_interacoes
FROM interacao
GROUP BY tipo_interacao
ORDER BY total_interacoes DESC;


-- 4. Conteúdos mais avaliados

SELECT
    co.conteudo_id,
    co.titulo,
    AVG(i.avaliacao_atribuida) AS avaliacao_media
FROM conteudo co
JOIN interacao i
    ON i.conteudo_id = co.conteudo_id
WHERE i.avaliacao_atribuida IS NOT NULL
GROUP BY co.conteudo_id, co.titulo
ORDER BY avaliacao_media DESC;


-- 5. Verificar integridade das interações

SELECT COUNT(*) AS interacoes_sem_conteudo
FROM interacao i
LEFT JOIN conteudo c
    ON c.conteudo_id = i.conteudo_id
WHERE c.conteudo_id IS NULL;


-- 6. Verificar integridade dos usuários

SELECT COUNT(*) AS interacoes_sem_usuario
FROM interacao i
LEFT JOIN usuario u
    ON u.usuario_id = i.usuario_id
WHERE u.usuario_id IS NULL;


-- ============================================================
-- Estudante 02 — embeddings, busca vetorial e recomendações
-- ============================================================


-- 7. Embeddings armazenados por modelo

SELECT
    modelo,
    COUNT(*) AS total_embeddings,
    MIN(gerado_em) AS primeiro,
    MAX(gerado_em) AS ultimo
FROM conteudo_embedding
GROUP BY modelo;


-- 8. Conteúdos sem embedding

SELECT COUNT(*) AS conteudos_sem_embedding
FROM conteudo co
LEFT JOIN conteudo_embedding ce
    ON ce.conteudo_id = co.conteudo_id
WHERE ce.conteudo_id IS NULL;


-- 9. Conteúdos mais semelhantes a um conteúdo (busca vetorial com pgvector)

SELECT
    co.conteudo_id,
    co.titulo,
    ca.nome AS categoria,
    co.tipo,
    1 - (ce.embedding <=> (
        SELECT embedding
        FROM conteudo_embedding
        WHERE conteudo_id = 1
    )) AS similaridade
FROM conteudo_embedding ce
JOIN conteudo co
    ON co.conteudo_id = ce.conteudo_id
JOIN categoria ca
    ON ca.categoria_id = co.categoria_id
WHERE ce.conteudo_id <> 1
ORDER BY ce.embedding <=> (
    SELECT embedding
    FROM conteudo_embedding
    WHERE conteudo_id = 1
)
LIMIT 5;


-- 9.1 Comparação das métricas de similaridade da Aula 04 para o conteúdo 1
--     <-> distância euclidiana (L2), <=> distância cosseno,
--     <#> produto escalar negativo (ordenar ASC para os maiores produtos).
--     Como os vetores são normalizados (norma 1), as três ordenações coincidem.

WITH referencia AS (
    SELECT embedding
    FROM conteudo_embedding
    WHERE conteudo_id = 1
)
SELECT
    co.conteudo_id,
    co.titulo,
    ROUND((ce.embedding <-> r.embedding)::numeric, 4) AS distancia_euclidiana,
    ROUND((ce.embedding <=> r.embedding)::numeric, 4) AS distancia_cosseno,
    ROUND(((ce.embedding <#> r.embedding) * -1)::numeric, 4) AS produto_escalar
FROM conteudo_embedding ce
JOIN conteudo co
    ON co.conteudo_id = ce.conteudo_id
CROSS JOIN referencia r
WHERE ce.conteudo_id <> 1
ORDER BY ce.embedding <=> r.embedding
LIMIT 5;


-- 9.2 Uso do índice HNSW (busca aproximada de vizinhos, ANN)
--     O plano deve mostrar "Index Scan using idx_conteudo_embedding_hnsw".
--     Em tabelas pequenas o PostgreSQL pode preferir a leitura sequencial;
--     SET enable_seqscan = off força o uso do índice apenas para demonstração.

SET enable_seqscan = off;

EXPLAIN
SELECT conteudo_id
FROM conteudo_embedding
ORDER BY embedding <=> (
    SELECT embedding
    FROM conteudo_embedding
    WHERE conteudo_id = 1
)
LIMIT 5;

RESET enable_seqscan;


-- 10. Recomendações de um usuário na execução mais recente do pipeline
--     (a execução é a última geral; usuário sem recomendações nela retorna vazio)

SELECT
    r.posicao,
    r.usuario_id,
    r.conteudo_id,
    co.titulo,
    r.pontuacao,
    r.i_vis,
    r.i_cur,
    r.status,
    r.data_geracao
FROM recomendacao r
JOIN conteudo co
    ON co.conteudo_id = r.conteudo_id
WHERE r.usuario_id = 3
  AND r.data_geracao = (
      SELECT MAX(data_geracao)
      FROM recomendacao
  )
ORDER BY r.posicao;


-- 11. Recomendações por execução e status

SELECT
    data_geracao,
    status,
    COUNT(*) AS total_recomendacoes,
    ROUND(AVG(pontuacao), 2) AS pontuacao_media
FROM recomendacao
GROUP BY data_geracao, status
ORDER BY data_geracao DESC, status;


-- 12. Verificar que nenhum conteúdo concluído foi recomendado

SELECT COUNT(*) AS recomendacoes_de_conteudos_concluidos
FROM recomendacao r
JOIN interacao i
    ON i.usuario_id = r.usuario_id
   AND i.conteudo_id = r.conteudo_id
WHERE i.tipo_interacao = 'conclusão'
   OR i.percentual_conclusao >= 100;