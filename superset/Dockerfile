# Superset 6.1.0 (imagem "lean") + driver do PostgreSQL, que não vem na imagem oficial.
FROM apache/superset:6.1.0

USER root
RUN uv pip install --no-cache --python /app/.venv/bin/python psycopg2-binary==2.9.10
USER superset
