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
        if not ucontrol_main.User.query.filter_by(username="tester").first():
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

    # /dashboard exige sessão autenticada; client (sem login explícito)
    # segue com o cookie de sessão que o POST acima já deixou setado.
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


def test_bible_verse_lookup_returns_joao_3_16(logged_in_client):
    response = logged_in_client.get(
        "/api/bible/verse",
        query_string={"book": "jo", "chapter": 3, "verse_start": 16},
    )
    data = response.get_json()
    assert "Deus amou o mundo" in data["verses"][0]["text"]
    assert data["reference"] == "João 3:16"


def test_bible_search_by_reference_resolves_to_joao_3_16(logged_in_client):
    response = logged_in_client.get("/api/bible/search", query_string={"q": "Jo 3:16"})
    data = response.get_json()
    assert data["type"] == "reference"
    assert any("Deus amou o mundo" in r["text"] for r in data["results"])


def test_update_bible_broadcasts_and_appends_to_display_log(app):
    socket_client = ucontrol_main.socketio.test_client(app)
    socket_client.emit("update_bible", {"reference": "João 3:16", "text": "..."})
    received = socket_client.get_received()
    events = [msg["name"] for msg in received]
    assert "update_bible" in events
    socket_client.disconnect()


def test_bible_add_and_remove_from_order_use_isolated_order_file(
    logged_in_client, tmp_path, monkeypatch
):
    order_file = tmp_path / "order_of_service.json"
    monkeypatch.chdir(tmp_path)

    add_response = logged_in_client.post(
        "/api/bible/add_to_order", json={"reference": "João 3:16"}
    )
    assert add_response.get_json()["success"] is True
    assert order_file.exists()
    saved = order_file.read_text(encoding="utf-8")
    assert "João 3:16" in saved

    remove_response = logged_in_client.post(
        "/api/bible/remove_from_order", json={"reference": "João 3:16"}
    )
    assert remove_response.get_json()["success"] is True
    assert order_file.read_text(encoding="utf-8") == "[]"


def test_list_audio_returns_json_structure(client):
    response = client.get("/list_audio")
    assert response.status_code == 200
    assert "audios" in response.get_json()


def test_download_audio_without_url_returns_400(client):
    response = client.post("/download_audio", json={})
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_delete_audio_requires_login(client):
    response = client.delete("/delete_audio/nao-existe.mp3")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_delete_audio_returns_404_for_missing_file(logged_in_client):
    response = logged_in_client.delete("/delete_audio/nao-existe.mp3")
    assert response.status_code == 404


def test_add_search_and_delete_song_use_isolated_songs_file(client, tmp_path, monkeypatch):
    songs_file = tmp_path / "songs.json"
    monkeypatch.chdir(tmp_path)

    add_response = client.post(
        "/add_song",
        data={
            "title": "Música de Teste",
            "author": "Autor de Teste",
            "sections[]": ["Verso 1"],
            "texts[]": ["Letra de teste aqui"],
        },
    )
    assert add_response.status_code == 200
    assert songs_file.exists()

    search_response = client.get("/search", query_string={"q": "Teste"})
    results = search_response.get_json()
    assert len(results) == 1
    song_id = results[0]["id"]
    assert results[0]["title"] == "Música de Teste"

    delete_response = client.post(f"/delete_song/{song_id}")
    assert delete_response.status_code == 200

    empty_search = client.get("/search", query_string={"q": "Teste"})
    assert empty_search.get_json() == []


def test_clock_and_help_pages_load(client):
    assert client.get("/clock").status_code == 200
    assert client.get("/help").status_code == 200


def test_historico_requires_login(client):
    response = client.get("/historico")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_api_historico_clear_empties_the_log(logged_in_client, tmp_path, monkeypatch):
    # load_display_log() (GET) resolve o path no namespace de display_log;
    # api_historico_clear (DELETE) usa o nome já importado em
    # blueprints.utils — os dois precisam ser trocados separadamente.
    log_file = tmp_path / "display_log.json"
    log_file.write_text('[{"type": "song", "title": "x", "ts": "2026-01-01T00:00:00"}]', encoding="utf-8")
    monkeypatch.setattr("display_log.DISPLAY_LOG_PATH", str(log_file))
    monkeypatch.setattr("blueprints.utils.DISPLAY_LOG_PATH", str(log_file))

    before = logged_in_client.get("/api/historico").get_json()
    assert len(before) == 1

    clear_response = logged_in_client.delete("/api/historico")
    assert clear_response.get_json() == {"ok": True}
    assert log_file.read_text(encoding="utf-8") == "[]"


def test_download_monitor_launcher_invalid_os_returns_400(client):
    response = client.get("/download-monitor-launcher/xyz")
    assert response.status_code == 400


def test_download_monitor_launcher_windows_returns_bat_attachment(client):
    response = client.get("/download-monitor-launcher/windows")
    assert response.status_code == 200
    assert ".bat" in response.headers["Content-Disposition"]


def test_connect_and_disconnect_update_client_tracking(app):
    import connections

    before = connections.socketio_clients_connected
    socket_client = ucontrol_main.socketio.test_client(app)
    assert connections.socketio_clients_connected == before + 1

    socket_client.disconnect()
    assert connections.socketio_clients_connected == before


def test_identify_as_monitor_is_returned_by_get_monitor_sids(app):
    import connections

    socket_client = ucontrol_main.socketio.test_client(app)
    socket_client.emit("identify", {"role": "monitor"})

    monitor_sids = connections._get_monitor_sids()
    assert len(monitor_sids) >= 1

    socket_client.disconnect()


def test_api_system_status_returns_expected_payload(logged_in_client):
    response = logged_in_client.get("/api/system/status")
    assert response.status_code == 200
    data = response.get_json()
    assert data["online"] is True
    assert data["port"] == 8585
    assert "socketio_clients" in data
    assert "socketio_by_role" in data


def test_orphaned_photo_navigation_handlers_were_removed():
    assert not hasattr(ucontrol_main, "handle_proxima_foto")
    assert not hasattr(ucontrol_main, "handle_anterior_foto")
    assert not hasattr(ucontrol_main, "obter_proxima_foto")


def test_list_image_folders_always_includes_root(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    response = client.get("/api/image_folders")
    assert response.get_json() == ["Geral"]


def test_create_image_folder_and_see_it_listed(logged_in_client, tmp_path, monkeypatch):
    (tmp_path / "static" / "imagens").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    create_response = logged_in_client.post("/api/image_folders", json={"name": "Louvor"})
    assert create_response.get_json()["status"] == "success"

    folders = logged_in_client.get("/api/image_folders").get_json()
    assert "Louvor" in folders


def test_upload_list_and_delete_image_round_trip(client, tmp_path, monkeypatch):
    import io
    from PIL import Image

    (tmp_path / "static" / "imagens").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), color="red").save(buffer, format="PNG")
    buffer.seek(0)

    upload_response = client.post(
        "/upload",
        data={"images": (buffer, "teste.png")},
        content_type="multipart/form-data",
    )
    assert upload_response.status_code == 200
    saved = upload_response.get_json()["saved_files"]
    assert saved == ["teste.png"]

    images = client.get("/imagens").get_json()
    assert images == ["/static/imagens/teste.png"]

    delete_response = client.post("/delete_image", json={"image_name": "teste.png"})
    assert delete_response.get_json()["status"] == "success"
    assert client.get("/imagens").get_json() == []


def test_orders_store_save_and_load_round_trip(tmp_path, monkeypatch):
    import orders_store

    monkeypatch.chdir(tmp_path)
    assert orders_store.load_orders() == {}

    sample = {"2026-08-09": {"tipo": "culto", "itens": []}}
    assert orders_store.save_orders(sample) is True
    assert orders_store.load_orders() == sample


def test_api_order_save_get_delete_round_trip(logged_in_client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    payload = {
        "tipo": "culto",
        "horario_culto": "19:00",
        "dirigente": "João",
        "pregador": "Pedro",
        "itens": [{"title": "Abertura"}],
    }

    save_response = logged_in_client.post("/api/orders/2026-08-09", json=payload)
    assert save_response.status_code == 200

    get_response = logged_in_client.get("/api/orders/2026-08-09")
    assert get_response.get_json()["dirigente"] == "João"

    delete_response = logged_in_client.delete("/api/orders/2026-08-09")
    assert delete_response.status_code == 200
    assert logged_in_client.get("/api/orders/2026-08-09").status_code == 404


def test_api_template_save_and_delete_round_trip(logged_in_client, tmp_path, monkeypatch):
    # TEMPLATES_FILE é relativo ao __file__ de orders_store.py, não ao cwd
    # — monkeypatch.chdir sozinho não isola; precisa trocar o caminho
    # direto, senão o teste escreve em order_templates.json de verdade.
    monkeypatch.setattr("orders_store.TEMPLATES_FILE", str(tmp_path / "order_templates.json"))

    save_response = logged_in_client.post(
        "/api/templates", json={"name": "Padrão", "items": ["Abertura", "Louvor"]}
    )
    assert save_response.get_json()["ok"] is True
    assert "Padrão" in logged_in_client.get("/api/templates").get_json()

    logged_in_client.delete("/api/templates/Padrão")
    assert "Padrão" not in logged_in_client.get("/api/templates").get_json()


def test_api_section_template_save_and_delete_round_trip(logged_in_client, tmp_path, monkeypatch):
    # Mesmo cuidado do teste acima, pra SECTION_TEMPLATES_FILE.
    monkeypatch.setattr("orders_store.SECTION_TEMPLATES_FILE", str(tmp_path / "section_templates.json"))

    save_response = logged_in_client.post(
        "/api/section-templates/louvor",
        json={"name": "Padrão", "fields": {"dirigente": "João"}},
    )
    assert save_response.get_json()["ok"] is True
    section = logged_in_client.get("/api/section-templates/louvor").get_json()
    assert section["Padrão"]["dirigente"] == "João"

    logged_in_client.delete("/api/section-templates/louvor/Padrão")
    section = logged_in_client.get("/api/section-templates/louvor").get_json()
    assert "Padrão" not in section


def test_legacy_save_and_load_compat_routes(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    save_response = client.post("/save", json=[{"title": "Item legado"}])
    assert save_response.status_code == 200

    load_response = client.get("/load")
    assert load_response.get_json() == [{"title": "Item legado"}]


def test_order_pages_load_with_login(logged_in_client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert logged_in_client.get("/order").status_code == 200
    assert logged_in_client.get("/order/new").status_code == 200
    assert logged_in_client.get("/order/2026-08-09").status_code == 200


def test_agenda_calendar_dashboard_and_edit_selector_load(logged_in_client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert logged_in_client.get("/agenda").status_code == 200
    assert logged_in_client.get("/agenda/dashboard").status_code == 200
    assert logged_in_client.get("/agenda/edit").status_code == 200


def test_agenda_detail_shows_real_order_data(logged_in_client, tmp_path, monkeypatch):
    import orders_store

    monkeypatch.chdir(tmp_path)
    orders_store.save_orders({"2026-08-09": {"dirigente": "João", "itens": []}})

    response = logged_in_client.get("/agenda/2026-08-09")
    assert response.status_code == 200
    assert "João".encode() in response.data


def test_agenda_edit_renders_same_template_as_order_edit(logged_in_client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    agenda_response = logged_in_client.get("/agenda/2026-08-09/edit")
    order_response = logged_in_client.get("/order/2026-08-09")
    assert agenda_response.status_code == 200
    assert order_response.status_code == 200
    # Mesmo template (order_edit.html) por trás das duas rotas — o mesmo
    # título gerado pelo template confirma isso.
    title = "Editar Ordem - 2026-08-09".encode()
    assert title in agenda_response.data
    assert title in order_response.data
