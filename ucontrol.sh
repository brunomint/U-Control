#!/bin/bash
set -e

PROJECT_DIR="/home/piano-25/14.3_calendario_U-Control"

cd "$PROJECT_DIR" || exit 1

venv/bin/flask --app main db upgrade

exec venv/bin/gunicorn -c gunicorn.conf.py main:app


