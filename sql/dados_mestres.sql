-- Dados mestres da entidade Conteúdo (RF30).
-- Criado e mantido por dados_mestres/consolidar_conteudo.py; pode ser
-- executado mais de uma vez.

CREATE SCHEMA IF NOT EXISTS mestre;

CREATE SEQUENCE IF NOT EXISTS mestre.seq_conteudo_mestre;

-- Tabela de correspondência: cada registro de origem aponta para o seu
-- conteúdo mestre. É persistente, o que mantém o identificador mestre
-- estável entre execuções.
CREATE TABLE IF NOT EXISTS mestre.conteudo_correspondencia (
    fonte               VARCHAR(20) NOT NULL,  -- silver_catalogo | d1_postgres
    id_origem           INTEGER     NOT NULL,  -- conteudo_id na fonte
    conteudo_mestre_id  VARCHAR(12) NOT NULL,  -- CM-000001
    -- M1 = mesmo conteudo_id entre fontes; M2 = duplicata por atributos;
    -- UNICO = sem outro registro correspondente
    regra_correspondencia VARCHAR(5) NOT NULL,
    sobrevivente        BOOLEAN     NOT NULL,  -- registro que fornece o id canônico
    primeira_vez_em     TIMESTAMP   NOT NULL,
    atualizado_em       TIMESTAMP   NOT NULL,
    id_execucao         VARCHAR(64) NOT NULL,

    PRIMARY KEY (fonte, id_origem),

    CONSTRAINT ck_correspondencia_regra
        CHECK (regra_correspondencia IN ('M1', 'M2', 'UNICO'))
);

CREATE INDEX IF NOT EXISTS idx_correspondencia_mestre
    ON mestre.conteudo_correspondencia (conteudo_mestre_id);

-- Registro de ouro: uma linha por conteúdo mestre, com os atributos
-- escolhidos pelas regras de sobrevivência.
CREATE TABLE IF NOT EXISTS mestre.conteudo (
    conteudo_mestre_id  VARCHAR(12)  PRIMARY KEY,
    conteudo_id_canonico INTEGER     NOT NULL,
    titulo              VARCHAR(255) NOT NULL,
    tipo                VARCHAR(50)  NOT NULL,
    categoria           VARCHAR(100) NOT NULL,
    nivel               VARCHAR(50)  NOT NULL,
    carga_horaria_min   INTEGER      NOT NULL,
    data_publicacao     DATE         NOT NULL,
    descricao           TEXT         NOT NULL,
    autor               VARCHAR(255) NOT NULL,
    chave_correspondencia VARCHAR(64) NOT NULL,  -- hash da chave de negócio normalizada
    qtd_registros_origem INTEGER     NOT NULL,
    atualizado_em       TIMESTAMP    NOT NULL,
    id_execucao         VARCHAR(64)  NOT NULL
);

-- Conflitos de atributos resolvidos pela sobrevivência (auditoria).
CREATE TABLE IF NOT EXISTS mestre.conteudo_conflito (
    conteudo_mestre_id  VARCHAR(12) NOT NULL,
    atributo            VARCHAR(30) NOT NULL,
    -- entre_fontes (mesmo conteudo_id) | entre_duplicatas (M2)
    nivel               VARCHAR(20) NOT NULL,
    valores             JSONB       NOT NULL,  -- [{"fonte", "id_origem", "valor"}]
    valor_escolhido     TEXT        NOT NULL,
    regra_sobrevivencia TEXT        NOT NULL,
    id_execucao         VARCHAR(64) NOT NULL,

    PRIMARY KEY (conteudo_mestre_id, atributo, nivel)
);
