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


@pytest.fixture
def logged_in_client(app):
    # O app de teste é uma única instância compartilhada entre todos os
    # testes da sessão (SQLite em memória, mas o mesmo processo) — busca
    # antes de criar pra não colidir com outro teste que já tenha logado
    # esse mesmo usuário.
    from werkzeug.security import generate_password_hash

    with app.app_context():
        user = ucontrol_main.User.query.filter_by(username="tester").first()
        if not user:
            user = ucontrol_main.User(
                username="tester",
                password=generate_password_hash("senha123", method="pbkdf2:sha256"),
            )
            ucontrol_main.db.session.add(user)
            ucontrol_main.db.session.commit()

    test_client = app.test_client()
    test_client.post("/login", data={"username": "tester", "password": "senha123"})
    return test_client
