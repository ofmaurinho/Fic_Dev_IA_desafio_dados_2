-- Usuário somente leitura do Apache Superset (RF18, RF26).
-- Enxerga apenas a camada Gold e as visões de qualidade; não tem acesso a
-- silver, mestre (tabela de correspondência) nem public (dados do Desafio 1
-- com usuario_id). A senha é definida por superset/configurar_superset.py a
-- partir de superset/.env. Pode ser executado mais de uma vez.

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'superset_leitura') THEN
        CREATE ROLE superset_leitura LOGIN;
    END IF;
END
$$;

ALTER ROLE superset_leitura SET default_transaction_read_only = on;
ALTER ROLE superset_leitura SET search_path = gold;

GRANT CONNECT ON DATABASE desafio_dados TO superset_leitura;
REVOKE ALL ON SCHEMA public FROM superset_leitura;

GRANT USAGE ON SCHEMA gold TO superset_leitura;
GRANT SELECT ON ALL TABLES IN SCHEMA gold TO superset_leitura;
ALTER DEFAULT PRIVILEGES IN SCHEMA gold GRANT SELECT ON TABLES TO superset_leitura;

-- A função de pseudonimização não é de uso do consumo.
REVOKE EXECUTE ON FUNCTION gold.pseudonimo_usuario(INTEGER) FROM PUBLIC;

-- Evolução das métricas de qualidade (RF31), exibida no dashboard.
GRANT USAGE ON SCHEMA qualidade TO superset_leitura;
GRANT SELECT ON qualidade.v_evolucao_metricas, qualidade.v_ultima_execucao TO superset_leitura;
