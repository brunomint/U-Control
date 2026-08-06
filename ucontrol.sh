#!/bin/bash
set -e

PROJECT_DIR="/home/piano-25/14.3_calendario_U-Control"

cd "$PROJECT_DIR" || exit 1

exec /usr/bin/python3 main.py


