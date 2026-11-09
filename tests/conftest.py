import os

# Precisa vir antes do `import main`: create_app() lê essas env vars na
# importação do módulo pra usar SQLite em memória e não abrir o navegador.
os.environ.setdefault("UCONTROL_TESTING", "1")
os.environ.setdefault("UCONTROL_NO_BROWSER", "1")

import pytest

import main as ucontrol_main
from models import User


@pytest.fixture
def app():
    return ucontrol_main.app


@pytest.fixture(autouse=True)
def sem_preparado_nem_follow():
    """Cada teste tem seu aparelho: sem isto, o preparado de um sobrava pro
    seguinte (antes um único por tipo era sobrescrito)."""
    import display_state
    from models import StagedContent

    with ucontrol_main.app.app_context():
        StagedContent.query.delete()
        ucontrol_main.db.session.commit()
    display_state._follows.clear()
    # Quem cuida de cada tela (destinos.py): cada teste começa sem dono.
    # Os testes escritos antes de existir o dono contam com "Os dois" de
    # padrão; os de tests/test_destinos.py voltam pro padrão de verdade.
    import destinos
    display_state._device_modes.clear()
    destinos._donos.update({'public': None, 'monitor': None})
    # Sem seguir a passagem, cada tela só muda pelo modo de quem mexe (a regra
    # que os testes antigos descrevem); tests/test_destinos.py liga de volta
    destinos._seguindo.update({'public': False, 'monitor': False})
    destinos._seguia_antes_do_preto.update({'public': False, 'monitor': False})
    destinos._passagem = None
    destinos._palco_na_biblia = False
    destinos._palco_sem_cifra = False
    destinos._ultimo_clicado.clear()
    display_state.MODO_INICIAL = 'all'
    yield
    display_state.MODO_INICIAL = 'none'


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
        user = User.query.filter_by(username="tester").first()
        if not user:
            user = User(
                username="tester",
                password=generate_password_hash("senha123", method="pbkdf2:sha256"),
            )
            ucontrol_main.db.session.add(user)
            ucontrol_main.db.session.commit()

    test_client = app.test_client()
    test_client.post("/login", data={"username": "tester", "password": "senha123"})
    return test_client


class _InlineThread:
    """Roda o alvo na hora, na mesma thread. Os handlers de show_image/
    show_video/show_two_urls gravam o DisplayState numa thread de fundo;
    nos testes (SQLite em memória, conexão compartilhada) essa gravação
    disputava o banco com o teste seguinte e derrubava testes ao acaso
    ("cannot rollback - no transaction is active")."""

    def __init__(self, target=None, args=(), kwargs=None, daemon=None, **_):
        self._target, self._args, self._kwargs = target, args, kwargs or {}

    def start(self):
        if self._target:
            self._target(*self._args, **self._kwargs)


@pytest.fixture(autouse=True)
def _display_saves_inline(monkeypatch):
    import types
    from blueprints import display
    monkeypatch.setattr(display, "threading", types.SimpleNamespace(Thread=_InlineThread))
