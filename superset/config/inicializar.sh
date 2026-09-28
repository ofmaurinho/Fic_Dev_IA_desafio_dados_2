#!/bin/sh
# Prepara o banco de metadados do Superset e o usuário administrador.
set -e
superset db upgrade
superset fab create-admin \
    --username admin --firstname Admin --lastname Desafio \
    --email admin@plataforma-educacional.example \
    --password "$SUPERSET_ADMIN_SENHA" || true
superset init
