-- Migração para bancos criados antes da etapa do Estudante 02.
-- Habilita o pgvector, cria a tabela de embeddings (512 dimensões, modelo
-- clip-ViT-B-32) com índice HNSW e recria a tabela de recomendações com
-- posição, índices da fórmula, status e data de geração.
-- Pode ser executada mais de uma vez. Em bancos novos, basta executar
-- sql/criar_banco.sql.

BEGIN;

CREATE EXTENSION IF NOT EXISTS vector;

-- Recria a tabela de embeddings se ela existir com outra dimensão (por
-- exemplo, 384 da versão com embeddings simulados). Os vetores são
-- regenerados pelo pipeline.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_attribute
        WHERE attrelid = to_regclass('public.conteudo_embedding')
          AND attname = 'embedding'
          AND atttypmod <> 512
    ) THEN
        DROP TABLE conteudo_embedding;
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS conteudo_embedding (
    conteudo_id INTEGER PRIMARY KEY,
    embedding VECTOR(512) NOT NULL,
    modelo VARCHAR(100) NOT NULL,
    texto_hash CHAR(64) NOT NULL,
    gerado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_embedding_conteudo
        FOREIGN KEY (conteudo_id)
        REFERENCES conteudo (conteudo_id)
);

CREATE INDEX IF NOT EXISTS idx_conteudo_embedding_hnsw
    ON conteudo_embedding
    USING hnsw (embedding vector_cosine_ops);

-- Recria a tabela somente se ela ainda estiver no esquema antigo (sem a
-- coluna posicao), que não possuía registros. Executar a migração novamente
-- depois do pipeline preserva o histórico de recomendações.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = 'recomendacao'
    )
    AND NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'recomendacao'
          AND column_name = 'posicao'
    ) THEN
        DROP TABLE recomendacao;
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS recomendacao (
    recomendacao_id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL,
    conteudo_id INTEGER NOT NULL,
    pontuacao NUMERIC(5, 2) NOT NULL,
    posicao INTEGER NOT NULL,
    i_vis NUMERIC(6, 4) NOT NULL,
    i_cur NUMERIC(6, 4) NOT NULL,
    i_conc SMALLINT NOT NULL,
    status VARCHAR(10) NOT NULL,
    data_geracao TIMESTAMP NOT NULL,

    CONSTRAINT fk_recomendacao_usuario
        FOREIGN KEY (usuario_id)
        REFERENCES usuario (usuario_id),

    CONSTRAINT fk_recomendacao_conteudo
        FOREIGN KEY (conteudo_id)
        REFERENCES conteudo (conteudo_id),

    CONSTRAINT uq_recomendacao_execucao
        UNIQUE (usuario_id, conteudo_id, data_geracao),

    CONSTRAINT ck_recomendacao_pontuacao
        CHECK (pontuacao BETWEEN 0 AND 100),

    CONSTRAINT ck_recomendacao_posicao
        CHECK (posicao > 0),

    CONSTRAINT ck_recomendacao_i_conc
        CHECK (i_conc IN (0, 1)),

    CONSTRAINT ck_recomendacao_status
        CHECK (status IN ('Positivo', 'Estável', 'Negativo'))
);

COMMIT;
