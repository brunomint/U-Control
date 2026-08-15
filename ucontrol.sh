#!/bin/bash
set -e

# Caminho do próprio script, não um valor fixo — assim continua
# funcionando não importa o nome/local da pasta do deploy (ex: a
# migração do Pi de 14.3_calendario_U-Control pra ucontrol-v2 em
# 2026-08-15 não teria exigido editar isso).
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$PROJECT_DIR" || exit 1

venv/bin/flask --app main db upgrade

exec venv/bin/gunicorn -c gunicorn.conf.py main:app


