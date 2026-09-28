-- Resultados dos testes de qualidade de dados (RF31).
-- Criado e mantido por qualidade/executar_testes.py; pode ser executado mais
-- de uma vez.

CREATE SCHEMA IF NOT EXISTS qualidade;

-- Uma linha por execução do conjunto de testes.
CREATE TABLE IF NOT EXISTS qualidade.execucao (
    id_execucao   VARCHAR(64) PRIMARY KEY,
    inicio        TIMESTAMP   NOT NULL,
    fim           TIMESTAMP   NOT NULL,
    -- sucesso | sucesso_com_ressalvas | falha
    status        VARCHAR(25) NOT NULL,
    gold_liberada BOOLEAN     NOT NULL,
    -- silver (dados do pipeline) ou simulacao (lote com defeitos injetados)
    origem_dados  VARCHAR(20) NOT NULL,
    silver_home   TEXT        NOT NULL,

    CONSTRAINT ck_execucao_status
        CHECK (status IN ('sucesso', 'sucesso_com_ressalvas', 'falha'))
);

-- Uma linha por regra e por fonte avaliada em cada execução.
CREATE TABLE IF NOT EXISTS qualidade.resultado_teste (
    id_execucao         VARCHAR(64)   NOT NULL REFERENCES qualidade.execucao,
    id_regra            VARCHAR(10)   NOT NULL,
    fonte               VARCHAR(30)   NOT NULL,
    dimensao            VARCHAR(30)   NOT NULL,
    descricao           TEXT          NOT NULL,
    severidade          VARCHAR(10)   NOT NULL,
    registros_avaliados INTEGER       NOT NULL,
    registros_violados  INTEGER       NOT NULL,
    -- percentual de conformidade (0 a 100); para taxas de rejeição, o valor medido
    metrica             NUMERIC(7, 3) NOT NULL,
    operador            VARCHAR(2)    NOT NULL,
    limite              NUMERIC(7, 3) NOT NULL,
    aprovado            BOOLEAN       NOT NULL,
    acao                TEXT          NOT NULL,
    -- até 5 registros violados, com identificador e mensagem, para diagnóstico
    amostra_violacoes   JSONB         NOT NULL DEFAULT '[]',
    executado_em        TIMESTAMP     NOT NULL,

    PRIMARY KEY (id_execucao, id_regra, fonte),

    CONSTRAINT ck_resultado_severidade CHECK (severidade IN ('critica', 'alerta')),
    CONSTRAINT ck_resultado_operador CHECK (operador IN ('>=', '<='))
);

-- Última execução: consultada antes de publicar a camada Gold.
CREATE OR REPLACE VIEW qualidade.v_ultima_execucao AS
SELECT *
FROM qualidade.execucao
ORDER BY fim DESC
LIMIT 1;

-- Evolução das métricas ao longo das execuções (base para o Superset).
CREATE OR REPLACE VIEW qualidade.v_evolucao_metricas AS
SELECT
    e.fim AS data_execucao,
    e.id_execucao,
    e.origem_dados,
    e.status,
    r.id_regra,
    r.fonte,
    r.dimensao,
    r.severidade,
    r.metrica,
    r.operador,
    r.limite,
    r.aprovado
FROM qualidade.resultado_teste r
JOIN qualidade.execucao e USING (id_execucao);
