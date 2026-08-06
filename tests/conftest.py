import os

# Precisa vir antes do `import main`: create_app() lê essas env vars na
# importação do módulo pra usar SQLite em memória e não abrir o navegador.
os.environ.setdefault("UCONTROL_TESTING", "1")
os.environ.setdefault("UCONTROL_NO_BROWSER", "1")

import pytest

import main as ucontrol_main


@pytest.fixture
def app():
    return ucontrol_main.app


@pytest.fixture
def client(app):
    return app.test_client()
