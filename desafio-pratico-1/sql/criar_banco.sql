CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE usuario (
    usuario_id INTEGER PRIMARY KEY
);

CREATE TABLE categoria (
    categoria_id SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE conteudo (
    conteudo_id INTEGER PRIMARY KEY,
    titulo VARCHAR(255) NOT NULL,
    tipo VARCHAR(50) NOT NULL,
    categoria_id INTEGER NOT NULL,
    nivel VARCHAR(50) NOT NULL,
    carga_horaria_min NUMERIC NOT NULL,
    data_publicacao DATE NOT NULL,
    descricao TEXT NOT NULL,
    autor VARCHAR(255) NOT NULL,

    CONSTRAINT fk_conteudo_categoria
        FOREIGN KEY (categoria_id)
        REFERENCES categoria (categoria_id)
);

CREATE TABLE interacao (
    usuario_id INTEGER NOT NULL,
    conteudo_id INTEGER NOT NULL,
    tipo_interacao VARCHAR(50) NOT NULL,
    data_hora TIMESTAMP NOT NULL,
    tempo_consumido NUMERIC NOT NULL,
    percentual_conclusao NUMERIC NOT NULL,
    avaliacao_atribuida NUMERIC,

    PRIMARY KEY (
        usuario_id,
        conteudo_id,
        tipo_interacao,
        data_hora
    ),

    CONSTRAINT fk_interacao_usuario
        FOREIGN KEY (usuario_id)
        REFERENCES usuario (usuario_id),

    CONSTRAINT fk_interacao_conteudo
        FOREIGN KEY (conteudo_id)
        REFERENCES conteudo (conteudo_id)
);

CREATE TABLE conteudo_embedding (
    conteudo_id INTEGER PRIMARY KEY,
    embedding VECTOR(512) NOT NULL,
    modelo VARCHAR(100) NOT NULL,
    texto_hash CHAR(64) NOT NULL,
    gerado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_embedding_conteudo
        FOREIGN KEY (conteudo_id)
        REFERENCES conteudo (conteudo_id)
);

-- Índice ANN (busca aproximada de vizinhos) para a distância cosseno.
CREATE INDEX idx_conteudo_embedding_hnsw
    ON conteudo_embedding
    USING hnsw (embedding vector_cosine_ops);

CREATE TABLE recomendacao (
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