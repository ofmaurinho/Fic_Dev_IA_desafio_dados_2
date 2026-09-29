-- Camada Gold para consumo analítico (RF26).
--
-- Executado por gold/publicar_gold.py em uma única transação, depois de:
--   1. confirmar que o último quality gate liberou a Gold (qualidade.execucao);
--   2. recarregar o schema silver (sql/camada_silver.sql);
--   3. definir a chave de pseudonimização na sessão (app.chave_pseudonimizacao),
--      lida do .env e nunca gravada no banco nem no repositório.
-- Se qualquer comando falhar, nada é publicado (sem carga parcial).
--
-- Fontes: silver.* (Silver do Hop e saída do Beam), mestre.* (dados mestres
-- de conteúdo, RF30) e public.recomendacao (Desafio 1).
-- Minimização (LGPD): o usuario_id não chega à Gold, só o pseudônimo
-- usuario_chave; o texto livre dos comentários não é publicado.

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS gold;

-- Pseudônimo estável do usuário: HMAC-SHA256 do usuario_id com chave secreta
-- (16 primeiros caracteres hexadecimais). Sem a chave não é possível
-- recalcular nem reverter o pseudônimo.
CREATE OR REPLACE FUNCTION gold.pseudonimo_usuario(usuario_id INTEGER)
RETURNS VARCHAR(16)
LANGUAGE sql STABLE
AS $$
    SELECT left(encode(public.hmac(usuario_id::TEXT,
                                   current_setting('app.chave_pseudonimizacao'),
                                   'sha256'), 'hex'), 16)
$$;

-- Tipos de interação que representam consumo do conteúdo.
CREATE OR REPLACE FUNCTION gold.eh_consumo(tipo_interacao VARCHAR)
RETURNS BOOLEAN
LANGUAGE sql IMMUTABLE
AS $$ SELECT tipo_interacao IN ('início', 'visualização', 'conclusão') $$;

-- ---------------------------------------------------------------------------
-- Dimensões
-- ---------------------------------------------------------------------------

-- Grão: um conteúdo mestre. Chave: conteudo_mestre_id.
CREATE TABLE IF NOT EXISTS gold.dim_conteudo (
    conteudo_mestre_id   VARCHAR(12)  PRIMARY KEY,
    conteudo_id_canonico INTEGER      NOT NULL,
    titulo               VARCHAR(255) NOT NULL,
    tipo                 VARCHAR(50)  NOT NULL,
    categoria            VARCHAR(100) NOT NULL,
    nivel                VARCHAR(50)  NOT NULL,
    carga_horaria_min    INTEGER      NOT NULL,
    faixa_duracao        VARCHAR(10)  NOT NULL,  -- curta (< 30), média (30–180), longa (> 180)
    data_publicacao      DATE         NOT NULL,
    ano_publicacao       INTEGER      NOT NULL,
    autor                VARCHAR(255) NOT NULL,
    qtd_registros_origem INTEGER      NOT NULL
);

-- Grão: um usuário (pseudonimizado). Chave: usuario_chave.
CREATE TABLE IF NOT EXISTS gold.dim_usuario (
    usuario_chave        VARCHAR(16) PRIMARY KEY,
    primeira_interacao   TIMESTAMP,
    ultima_interacao     TIMESTAMP,
    total_interacoes     INTEGER     NOT NULL,
    meses_ativos         INTEGER     NOT NULL,
    conteudos_concluidos INTEGER     NOT NULL
);

-- ---------------------------------------------------------------------------
-- Fatos
-- ---------------------------------------------------------------------------

-- Grão: uma interação. Chave: (usuario_chave, conteudo_id_origem, tipo_interacao, data_hora).
CREATE TABLE IF NOT EXISTS gold.fato_interacao (
    usuario_chave         VARCHAR(16)   NOT NULL,
    conteudo_mestre_id    VARCHAR(12)   NOT NULL REFERENCES gold.dim_conteudo,
    conteudo_id_origem    INTEGER       NOT NULL,  -- rastreabilidade até a Silver
    tipo_interacao        VARCHAR(50)   NOT NULL,
    data_hora             TIMESTAMP     NOT NULL,
    data                  DATE          NOT NULL,
    ano_mes               CHAR(7)       NOT NULL,
    tempo_consumido       NUMERIC       NOT NULL,
    percentual_conclusao  NUMERIC(5, 2) NOT NULL,
    avaliacao_atribuida   NUMERIC(3, 1),
    eh_consumo            BOOLEAN       NOT NULL,
    eh_conclusao          BOOLEAN       NOT NULL,
    -- ressalva de qualidade QD06: interação anterior à publicação do conteúdo
    anterior_a_publicacao BOOLEAN       NOT NULL,
    id_execucao_silver    VARCHAR(64)   NOT NULL,

    PRIMARY KEY (usuario_chave, conteudo_id_origem, tipo_interacao, data_hora)
);

-- Grão: um comentário. Chave: comentario_hash (MD5 da chave natural, que
-- inclui o texto; o texto em si não é publicado).
CREATE TABLE IF NOT EXISTS gold.fato_comentario (
    comentario_hash       CHAR(32)      PRIMARY KEY,
    usuario_chave         VARCHAR(16)   NOT NULL,
    conteudo_mestre_id    VARCHAR(12)   NOT NULL REFERENCES gold.dim_conteudo,
    conteudo_id_origem    INTEGER       NOT NULL,
    data                  DATE          NOT NULL,
    ano_mes               CHAR(7)       NOT NULL,
    avaliacao             NUMERIC(3, 1) NOT NULL,
    tags                  TEXT[]        NOT NULL,
    qtd_tags              INTEGER       NOT NULL,
    anterior_a_publicacao BOOLEAN       NOT NULL,
    id_execucao_silver    VARCHAR(64)   NOT NULL
);

-- Grão: uma recomendação gerada pelo motor do Desafio 1. Chave: recomendacao_id.
-- convertida: o usuário consumiu (início, visualização ou conclusão) o
--   conteúdo mestre recomendado em qualquer data. Regra acordada pela equipe,
--   porque todas as recomendações foram geradas depois das interações
--   disponíveis.
-- convertida_apos_geracao: regra estrita, com consumo depois de data_geracao.
CREATE TABLE IF NOT EXISTS gold.fato_recomendacao (
    recomendacao_id         INTEGER       PRIMARY KEY,
    usuario_chave           VARCHAR(16)   NOT NULL,
    conteudo_mestre_id      VARCHAR(12)   NOT NULL REFERENCES gold.dim_conteudo,
    conteudo_id_origem      INTEGER       NOT NULL,
    posicao                 INTEGER       NOT NULL,
    pontuacao               NUMERIC(5, 2) NOT NULL,
    status                  VARCHAR(10)   NOT NULL,
    data_geracao            TIMESTAMP     NOT NULL,
    geracao_vigente         BOOLEAN       NOT NULL,  -- última geração do usuário
    convertida              BOOLEAN       NOT NULL,
    convertida_apos_geracao BOOLEAN       NOT NULL,
    concluida               BOOLEAN       NOT NULL
);

-- Grão: mês × categoria. Chave: (ano_mes, categoria). Produzida pelo pipeline
-- Apache Beam (beam/pipeline.py). conteudos_consumidos conta conteudo_id de
-- origem, não conteúdo mestre.
CREATE TABLE IF NOT EXISTS gold.kpi_engajamento_mensal_categoria (
    LIKE silver.engajamento_categoria_mensal INCLUDING ALL
);

-- Auditoria das publicações da Gold.
CREATE TABLE IF NOT EXISTS gold.publicacao (
    id_execucao            VARCHAR(64) PRIMARY KEY,
    id_execucao_qualidade  VARCHAR(64) NOT NULL,
    status_qualidade       VARCHAR(25) NOT NULL,
    publicado_em           TIMESTAMP   NOT NULL,
    linhas                 JSONB       NOT NULL
);

-- ---------------------------------------------------------------------------
-- Carga (substituição completa, dentro da transação da publicação)
-- ---------------------------------------------------------------------------

TRUNCATE gold.fato_interacao, gold.fato_comentario, gold.fato_recomendacao,
         gold.dim_usuario, gold.dim_conteudo, gold.kpi_engajamento_mensal_categoria;

INSERT INTO gold.dim_conteudo
SELECT
    conteudo_mestre_id,
    conteudo_id_canonico,
    titulo,
    tipo,
    categoria,
    nivel,
    carga_horaria_min,
    CASE
        WHEN carga_horaria_min < 30 THEN 'curta'
        WHEN carga_horaria_min <= 180 THEN 'média'
        ELSE 'longa'
    END,
    data_publicacao,
    EXTRACT(YEAR FROM data_publicacao)::INTEGER,
    autor,
    qtd_registros_origem
FROM mestre.conteudo;

-- Tradução do conteudo_id de cada fonte para o conteúdo mestre.
CREATE TEMPORARY TABLE mapa_conteudo ON COMMIT DROP AS
SELECT fonte, id_origem AS conteudo_id, conteudo_mestre_id
FROM mestre.conteudo_correspondencia;

INSERT INTO gold.fato_interacao
SELECT
    gold.pseudonimo_usuario(i.usuario_id),
    m.conteudo_mestre_id,
    i.conteudo_id,
    i.tipo_interacao,
    i.data_hora,
    i.data_hora::DATE,
    to_char(i.data_hora, 'YYYY-MM'),
    i.tempo_consumido,
    i.percentual_conclusao,
    i.avaliacao_atribuida,
    gold.eh_consumo(i.tipo_interacao),
    i.tipo_interacao = 'conclusão',
    i.data_hora::DATE < c.data_publicacao,
    i.id_execucao
FROM silver.interacao i
JOIN mapa_conteudo m ON m.fonte = 'silver_catalogo' AND m.conteudo_id = i.conteudo_id
JOIN silver.catalogo c ON c.conteudo_id = i.conteudo_id;

INSERT INTO gold.fato_comentario
SELECT
    md5(concat_ws('|', co.usuario_id, co.conteudo_id, co.data, co.comentario)),
    gold.pseudonimo_usuario(co.usuario_id),
    m.conteudo_mestre_id,
    co.conteudo_id,
    co.data,
    to_char(co.data, 'YYYY-MM'),
    co.avaliacao,
    ARRAY(SELECT jsonb_array_elements_text(co.tags)),
    jsonb_array_length(co.tags),
    co.data < c.data_publicacao,
    co.id_execucao
FROM silver.comentario co
JOIN mapa_conteudo m ON m.fonte = 'silver_catalogo' AND m.conteudo_id = co.conteudo_id
JOIN silver.catalogo c ON c.conteudo_id = co.conteudo_id;

-- Consumo por usuário e conteúdo mestre, calculado com o usuario_id ainda
-- dentro do banco, antes da pseudonimização.
CREATE TEMPORARY TABLE consumo ON COMMIT DROP AS
SELECT
    i.usuario_id,
    m.conteudo_mestre_id,
    MIN(i.data_hora) FILTER (WHERE gold.eh_consumo(i.tipo_interacao)) AS primeiro_consumo,
    MAX(i.data_hora) FILTER (WHERE gold.eh_consumo(i.tipo_interacao)) AS ultimo_consumo,
    BOOL_OR(i.tipo_interacao = 'conclusão') AS concluiu
FROM silver.interacao i
JOIN mapa_conteudo m ON m.fonte = 'silver_catalogo' AND m.conteudo_id = i.conteudo_id
GROUP BY i.usuario_id, m.conteudo_mestre_id;

INSERT INTO gold.fato_recomendacao
SELECT
    r.recomendacao_id,
    gold.pseudonimo_usuario(r.usuario_id),
    m.conteudo_mestre_id,
    r.conteudo_id,
    r.posicao,
    r.pontuacao,
    r.status,
    r.data_geracao,
    r.data_geracao = MAX(r.data_geracao) OVER (PARTITION BY r.usuario_id),
    COALESCE(cs.primeiro_consumo IS NOT NULL, FALSE),
    COALESCE(cs.ultimo_consumo > r.data_geracao, FALSE),
    COALESCE(cs.concluiu, FALSE)
FROM public.recomendacao r
JOIN mapa_conteudo m ON m.fonte = 'd1_postgres' AND m.conteudo_id = r.conteudo_id
LEFT JOIN consumo cs
       ON cs.usuario_id = r.usuario_id AND cs.conteudo_mestre_id = m.conteudo_mestre_id;

INSERT INTO gold.dim_usuario
SELECT
    gold.pseudonimo_usuario(u.usuario_id),
    MIN(i.data_hora),
    MAX(i.data_hora),
    COUNT(i.usuario_id),
    COUNT(DISTINCT to_char(i.data_hora, 'YYYY-MM')),
    COUNT(DISTINCT i.conteudo_id) FILTER (WHERE i.tipo_interacao = 'conclusão')
FROM public.usuario u
LEFT JOIN silver.interacao i ON i.usuario_id = u.usuario_id
GROUP BY u.usuario_id;

INSERT INTO gold.kpi_engajamento_mensal_categoria
SELECT * FROM silver.engajamento_categoria_mensal;

-- ---------------------------------------------------------------------------
-- Visões orientadas às perguntas de negócio
-- ---------------------------------------------------------------------------

-- Como evolui o engajamento mês a mês? Grão: ano_mes.
-- usuario_ativo: usuário com ao menos uma interação de qualquer tipo no mês.
-- taxa_conclusao: conclusões / interações de consumo.
CREATE OR REPLACE VIEW gold.vw_kpi_mensal AS
SELECT
    ano_mes,
    COUNT(*)                                        AS total_interacoes,
    COUNT(DISTINCT usuario_chave)                   AS usuarios_ativos,
    COUNT(DISTINCT conteudo_mestre_id)              AS conteudos_consumidos,
    COUNT(*) FILTER (WHERE eh_consumo)              AS interacoes_consumo,
    COUNT(*) FILTER (WHERE eh_conclusao)            AS conclusoes,
    ROUND(COUNT(*) FILTER (WHERE eh_conclusao)::NUMERIC
          / NULLIF(COUNT(*) FILTER (WHERE eh_consumo), 0), 4) AS taxa_conclusao,
    ROUND(AVG(avaliacao_atribuida), 2)              AS avaliacao_media,
    COUNT(*) FILTER (WHERE anterior_a_publicacao)   AS interacoes_com_ressalva
FROM gold.fato_interacao
GROUP BY ano_mes;

-- Quais conteúdos engajam, são bem avaliados e convertem? Grão: conteúdo mestre.
CREATE OR REPLACE VIEW gold.vw_desempenho_conteudo AS
WITH interacoes AS (
    SELECT
        conteudo_mestre_id,
        COUNT(*)                             AS total_interacoes,
        COUNT(DISTINCT usuario_chave)        AS usuarios,
        COUNT(*) FILTER (WHERE eh_consumo)   AS interacoes_consumo,
        COUNT(*) FILTER (WHERE eh_conclusao) AS conclusoes,
        AVG(avaliacao_atribuida)             AS avaliacao_media
    FROM gold.fato_interacao
    GROUP BY conteudo_mestre_id
),
comentarios AS (
    SELECT conteudo_mestre_id, COUNT(*) AS comentarios, AVG(avaliacao) AS nota_media_comentarios
    FROM gold.fato_comentario
    GROUP BY conteudo_mestre_id
),
recomendacoes AS (
    SELECT
        conteudo_mestre_id,
        COUNT(*)                          AS recomendacoes,
        COUNT(*) FILTER (WHERE convertida) AS recomendacoes_convertidas
    FROM gold.fato_recomendacao
    WHERE geracao_vigente
    GROUP BY conteudo_mestre_id
)
SELECT
    d.conteudo_mestre_id,
    d.titulo,
    d.tipo,
    d.categoria,
    d.nivel,
    d.faixa_duracao,
    d.autor,
    d.data_publicacao,
    COALESCE(i.total_interacoes, 0)      AS total_interacoes,
    COALESCE(i.usuarios, 0)              AS usuarios,
    COALESCE(i.conclusoes, 0)            AS conclusoes,
    ROUND(i.conclusoes::NUMERIC / NULLIF(i.interacoes_consumo, 0), 4) AS taxa_conclusao,
    ROUND(i.avaliacao_media, 2)          AS avaliacao_media,
    COALESCE(c.comentarios, 0)           AS comentarios,
    ROUND(c.nota_media_comentarios, 2)   AS nota_media_comentarios,
    COALESCE(r.recomendacoes, 0)         AS recomendacoes,
    COALESCE(r.recomendacoes_convertidas, 0) AS recomendacoes_convertidas,
    ROUND(r.recomendacoes_convertidas::NUMERIC / NULLIF(r.recomendacoes, 0), 4) AS taxa_conversao
FROM gold.dim_conteudo d
LEFT JOIN interacoes i USING (conteudo_mestre_id)
LEFT JOIN comentarios c USING (conteudo_mestre_id)
LEFT JOIN recomendacoes r USING (conteudo_mestre_id);

-- As recomendações convertem? Grão: posição × status, geração vigente.
-- conversao_recomendacao: recomendações convertidas / recomendações.
CREATE OR REPLACE VIEW gold.vw_conversao_recomendacao AS
SELECT
    posicao,
    status,
    COUNT(*)                                          AS recomendacoes,
    COUNT(*) FILTER (WHERE convertida)                AS convertidas,
    ROUND(COUNT(*) FILTER (WHERE convertida)::NUMERIC / COUNT(*), 4) AS taxa_conversao,
    COUNT(*) FILTER (WHERE convertida_apos_geracao)   AS convertidas_apos_geracao,
    COUNT(*) FILTER (WHERE concluida)                 AS concluidas,
    ROUND(AVG(pontuacao), 2)                          AS pontuacao_media
FROM gold.fato_recomendacao
WHERE geracao_vigente
GROUP BY posicao, status;

-- ---------------------------------------------------------------------------
-- Visões adicionais de minimização e mascaramento (LGPD - RF32 e RF33)
-- ---------------------------------------------------------------------------

-- Perfil de engajamento do usuário minimizado e mascarado. Grão: usuário.
-- Remove o acesso às datas exatas de comportamento e expõe apenas um ID ofuscado.
CREATE OR REPLACE VIEW gold.vw_perfil_usuario_mascarado AS
SELECT
    CONCAT('usr_', LEFT(usuario_chave, 4), '***', RIGHT(usuario_chave, 4)) AS usuario_mascarado,
    total_interacoes,
    meses_ativos,
    conteudos_concluidos,
    CASE 
        WHEN conteudos_concluidos = 0 THEN 'Inativo/Explorador'
        WHEN conteudos_concluidos BETWEEN 1 AND 5 THEN 'Casual'
        ELSE 'Engajado'
    END AS perfil_engajamento
FROM gold.dim_usuario;