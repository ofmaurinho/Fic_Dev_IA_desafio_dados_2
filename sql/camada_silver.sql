-- Camada Silver no PostgreSQL (RF26).
-- Espelha os arquivos Silver do Apache Hop e a saída do pipeline Beam para
-- que a Gold seja produzida em SQL e para que a Silver possa ser catalogada.
-- As tabelas são recarregadas por gold/publicar_gold.py na mesma transação
-- que publica a Gold. Pode ser executado mais de uma vez.

CREATE SCHEMA IF NOT EXISTS silver;

CREATE TABLE IF NOT EXISTS silver.catalogo (
    conteudo_id       INTEGER      PRIMARY KEY,
    titulo            VARCHAR(255) NOT NULL,
    tipo              VARCHAR(50)  NOT NULL,
    categoria         VARCHAR(100) NOT NULL,
    nivel             VARCHAR(50)  NOT NULL,
    carga_horaria_min INTEGER      NOT NULL,
    data_publicacao   DATE         NOT NULL,
    descricao         TEXT         NOT NULL,
    autor             VARCHAR(255) NOT NULL,
    origem            VARCHAR(100) NOT NULL,
    data_ingestao     TIMESTAMP    NOT NULL,
    id_execucao       VARCHAR(64)  NOT NULL
);

CREATE TABLE IF NOT EXISTS silver.interacao (
    usuario_id           INTEGER      NOT NULL,
    conteudo_id          INTEGER      NOT NULL,
    tipo_interacao       VARCHAR(50)  NOT NULL,
    data_hora            TIMESTAMP    NOT NULL,
    tempo_consumido      NUMERIC      NOT NULL,
    percentual_conclusao NUMERIC(5, 2) NOT NULL,
    avaliacao_atribuida  NUMERIC(3, 1),
    origem               VARCHAR(100) NOT NULL,
    data_ingestao        TIMESTAMP    NOT NULL,
    id_execucao          VARCHAR(64)  NOT NULL,

    PRIMARY KEY (usuario_id, conteudo_id, tipo_interacao, data_hora)
);

CREATE TABLE IF NOT EXISTS silver.comentario (
    usuario_id    INTEGER      NOT NULL,
    conteudo_id   INTEGER      NOT NULL,
    avaliacao     NUMERIC(3, 1) NOT NULL,
    comentario    TEXT         NOT NULL,  -- texto livre: pode conter dado pessoal
    tags          JSONB        NOT NULL,
    data          DATE         NOT NULL,
    origem        VARCHAR(100) NOT NULL,
    data_ingestao TIMESTAMP    NOT NULL,
    id_execucao   VARCHAR(64)  NOT NULL,

    PRIMARY KEY (usuario_id, conteudo_id, data, comentario)
);

-- Saída do pipeline Apache Beam (beam/pipeline.py), lida do Parquet.
CREATE TABLE IF NOT EXISTS silver.engajamento_categoria_mensal (
    ano_mes                    CHAR(7)      NOT NULL,
    categoria                  VARCHAR(100) NOT NULL,
    total_interacoes           INTEGER      NOT NULL,
    usuarios_ativos            INTEGER      NOT NULL,
    conteudos_consumidos       INTEGER      NOT NULL,
    interacoes_consumo         INTEGER      NOT NULL,
    conclusoes                 INTEGER      NOT NULL,
    taxa_conclusao             NUMERIC(6, 4),
    percentual_conclusao_medio NUMERIC(5, 2) NOT NULL,
    tempo_consumido_total      NUMERIC      NOT NULL,
    curtidas                   INTEGER      NOT NULL,
    compartilhamentos          INTEGER      NOT NULL,
    avaliacoes                 INTEGER      NOT NULL,
    avaliacao_media            NUMERIC(3, 2),
    id_execucao                VARCHAR(64)  NOT NULL,
    runtime                    VARCHAR(20)  NOT NULL,

    PRIMARY KEY (ano_mes, categoria)
);
