#!/bin/sh
set -e

flask --app main db upgrade
exec gunicorn -c gunicorn.conf.py main:app
