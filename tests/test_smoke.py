from werkzeug.security import generate_password_hash

import main as ucontrol_main


def test_create_app_uses_in_memory_db_when_testing(app):
    assert app.config["TESTING"] is True
    assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///:memory:"


def test_root_redirects_to_login(client):
    response = client.get("/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_login_page_loads(client):
    response = client.get("/login")
    assert response.status_code == 200


def test_data_pt_formats_date_in_portuguese():
    assert ucontrol_main.data_pt("2026-07-08") == "Quarta-feira, 8 de julho de 2026"


def test_data_pt_returns_input_unchanged_on_invalid_date():
    assert ucontrol_main.data_pt("not-a-date") == "not-a-date"


def test_display_state_table_has_media_type_column(app):
    with app.app_context():
        columns = [c.name for c in ucontrol_main.DisplayState.__table__.columns]
    assert "media_type" in columns


def test_countdown_page_route_resolves_to_blueprint(client):
    response = client.get("/countdown")
    assert response.status_code == 200


def test_start_countdown_broadcasts_and_updates_state(app):
    socket_client = ucontrol_main.socketio.test_client(app)
    socket_client.emit("start_countdown", {"duration_seconds": 60, "label": "Sermão"})
    received = socket_client.get_received()
    events = [msg["name"] for msg in received]
    assert "countdown_start" in events

    state_response = app.test_client().get("/api/countdown/state")
    assert state_response.get_json()["active"] is True
    socket_client.disconnect()


def test_set_ticker_broadcasts_and_updates_state(app):
    socket_client = ucontrol_main.socketio.test_client(app)
    socket_client.emit("set_ticker", {"text": "Bem-vindos!", "target": "all"})
    received = socket_client.get_received()
    events = [msg["name"] for msg in received]
    assert "ticker_update" in events

    ticker_response = app.test_client().get("/api/ticker")
    data = ticker_response.get_json()
    assert data["text"] == "Bem-vindos!"
    assert data["active"] is True
    socket_client.disconnect()


def test_login_redirects_to_dashboard_and_authenticates(app, client):
    with app.app_context():
        user = ucontrol_main.User(
            username="tester",
            password=generate_password_hash("senha123", method="pbkdf2:sha256"),
        )
        ucontrol_main.db.session.add(user)
        ucontrol_main.db.session.commit()

    response = client.post(
        "/login", data={"username": "tester", "password": "senha123"}
    )
    assert response.status_code == 302
    assert "/dashboard" in response.headers["Location"]

    dashboard_response = client.get("/dashboard")
    assert dashboard_response.status_code == 200


def test_login_with_wrong_password_shows_flash_message(client):
    response = client.post(
        "/login",
        data={"username": "nao-existe", "password": "errada"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "incorretos".encode() in response.data
