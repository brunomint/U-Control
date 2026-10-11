from werkzeug.security import generate_password_hash

import main as ucontrol_main
from models import DisplayState, User


def _operator_socket(app):
    """Cliente Socket.IO de um operador logado — os eventos de controle
    do telão exigem login (extensions.OperatorSocketIO)."""
    with app.app_context():
        if not User.query.filter_by(username="tester").first():
            ucontrol_main.db.session.add(User(
                username="tester",
                password=generate_password_hash("senha123", method="pbkdf2:sha256"),
            ))
            ucontrol_main.db.session.commit()
    http = app.test_client()
    http.post("/login", data={"username": "tester", "password": "senha123"})
    return ucontrol_main.socketio.test_client(app, flask_test_client=http)


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
        columns = [c.name for c in DisplayState.__table__.columns]
    assert "media_type" in columns


def test_countdown_page_route_resolves_to_blueprint(client):
    response = client.get("/countdown")
    assert response.status_code == 200


def test_start_countdown_broadcasts_and_updates_state(app):
    socket_client = _operator_socket(app)
    socket_client.emit("start_countdown", {"duration_seconds": 60, "label": "Sermão"})
    received = socket_client.get_received()
    events = [msg["name"] for msg in received]
    assert "countdown_start" in events

    state_response = app.test_client().get("/api/countdown/state")
    assert state_response.get_json()["active"] is True
    socket_client.disconnect()


def test_set_ticker_broadcasts_and_updates_state(app):
    socket_client = _operator_socket(app)
    socket_client.emit("set_ticker", {"text": "Bem-vindos!", "target": "all"})
    received = socket_client.get_received()
    events = [msg["name"] for msg in received]
    assert "ticker_update" in events

    ticker_response = app.test_client().get("/api/ticker")
    data = ticker_response.get_json()
    assert data["text"] == "Bem-vindos!"
    assert data["active"] is True
    socket_client.disconnect()


def test_init_countdown_and_ticker_state_hydrate_from_db(app):
    # Simula o que create_app() faz no startup real: lê o rótulo/texto
    # salvos no banco pro estado em memória. Não pode rodar no import do
    # módulo (blueprints/countdown.py, ticker.py) — precisa de app_context.
    from blueprints.countdown import _countdown_state, _save_countdown_config, init_countdown_state
    from blueprints.ticker import _save_ticker_config, init_ticker_state
    import blueprints.ticker as ticker_module

    with app.app_context():
        _save_countdown_config({"label": "Rótulo salvo"})
        _save_ticker_config("Texto salvo")

        init_countdown_state()
        init_ticker_state()

    assert _countdown_state["label"] == "Rótulo salvo"
    assert ticker_module._ticker_text == "Texto salvo"


def test_login_redirects_to_dashboard_and_authenticates(app, client):
    with app.app_context():
        if not User.query.filter_by(username="tester").first():
            user = User(
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
    socket_client = _operator_socket(app)
    socket_client.emit("update_bible", {"reference": "João 3:16", "text": "..."})
    received = socket_client.get_received()
    events = [msg["name"] for msg in received]
    assert "update_bible" in events
    socket_client.disconnect()


def test_bible_add_and_remove_from_order_target_todays_order(app, logged_in_client):
    # Fase 5.6: unificado na tabela Order (por data) — os botões de bíblia
    # não têm seletor de data, então miram sempre a ordem de hoje.
    import orders_store
    from datetime import date

    today = date.today().isoformat()

    with app.app_context():
        existing = orders_store.load_orders()

    add_response = logged_in_client.post(
        "/api/bible/add_to_order", json={"reference": "João 3:16"}
    )
    add_json = add_response.get_json()
    assert add_json["success"] is True
    assert add_json["date"] == today
    assert "hoje" in add_json["message"]

    with app.app_context():
        order = orders_store.load_orders().get(today, {})
        itens = order.get("itens") or []
        assert any(i.get("isBible") and i.get("reference") == "João 3:16" for i in itens)

    remove_response = logged_in_client.post(
        "/api/bible/remove_from_order", json={"reference": "João 3:16"}
    )
    assert remove_response.get_json()["success"] is True

    with app.app_context():
        order = orders_store.load_orders().get(today, {})
        itens = order.get("itens") or []
        assert not any(i.get("isBible") and i.get("reference") == "João 3:16" for i in itens)
        # limpeza — banco de teste é compartilhado entre todos os testes da sessão
        orders_store.save_orders(existing)


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


def test_visiting_lyrics_page_does_not_rewrite_unrelated_song_children(logged_in_client, app):
    # /lyrics/<id> chama save_songs() com a LISTA INTEIRA em toda visita,
    # só pra atualizar last_played de uma música — se o sync fosse um
    # "apaga tudo e reinsere" ingênuo, as seções desta música E das outras
    # 380 seriam recriadas (novos ids de linha) a cada visita.
    from models_songs import Song
    from songs_store import save_songs

    with app.app_context():
        save_songs([
            {"id": 90001, "title": "Música A", "author": "Autor", "sections": [{"title": "Verso", "text": ["la la"]}]},
            {"id": 90002, "title": "Música B", "author": "Autor", "sections": [{"title": "Verso", "text": ["la la"]}]},
        ])
        ids_before = {
            90001: [s.id for s in ucontrol_main.db.session.get(Song, 90001).sections],
            90002: [s.id for s in ucontrol_main.db.session.get(Song, 90002).sections],
        }

    logged_in_client.get("/lyrics/90001")
    logged_in_client.get("/lyrics/90001")

    with app.app_context():
        song_a = ucontrol_main.db.session.get(Song, 90001)
        last_played = song_a.last_played
        ids_after = {
            90001: [s.id for s in song_a.sections],
            90002: [s.id for s in ucontrol_main.db.session.get(Song, 90002).sections],
        }
        ucontrol_main.db.session.delete(song_a)
        ucontrol_main.db.session.delete(ucontrol_main.db.session.get(Song, 90002))
        ucontrol_main.db.session.commit()

    assert last_played is not None
    assert ids_after[90001] == ids_before[90001]
    assert ids_after[90002] == ids_before[90002]


def test_add_search_and_delete_song_round_trip(client):
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

    search_response = client.get("/search", query_string={"q": "Teste"})
    results = search_response.get_json()
    assert len(results) == 1
    song_id = results[0]["id"]
    assert results[0]["title"] == "Música de Teste"

    delete_response = client.post(f"/delete_song/{song_id}")
    assert delete_response.status_code == 200


def test_view_song_falls_back_to_todays_order_when_no_order_found(app, client):
    # /view/<id> sem ?order= e sem nenhuma ordem referenciando a música
    # cai no fallback pra ordem de hoje (Fase 5.6 — antes lia
    # order_of_service.json). Cobertura nova: essa rota nunca teve teste.
    # Usa um item bíblico porque é o único pedaço de order_data que o
    # template view_song.html realmente renderiza (bible_items).
    import orders_store
    import songs_store
    from datetime import date

    today = date.today().isoformat()
    with app.app_context():
        existing_orders = orders_store.load_orders()
        existing_songs = songs_store.load_songs()
        song_id = songs_store.get_next_id(existing_songs)
        songs_store.save_songs(existing_songs + [{
            "id": song_id, "title": "Música Fallback", "author": "Autor",
            "sections": [{"title": "Verso", "text": ["la la"]}],
        }])
        orders_store.save_orders(dict(existing_orders, **{
            today: {"itens": [{"isBible": True, "reference": "Salmos 23:1", "title": "📖 Salmos 23:1"}]},
        }))

    response = client.get(f"/view/{song_id}")
    assert response.status_code == 200
    assert "Salmos 23:1".encode() in response.data

    with app.app_context():
        songs_store.save_songs(existing_songs)
        orders_store.save_orders(existing_orders)

    empty_search = client.get("/search", query_string={"q": "Teste"})
    assert empty_search.get_json() == []


def test_clock_and_help_pages_load(client):
    assert client.get("/clock").status_code == 200
    assert client.get("/help").status_code == 200


def test_historico_requires_login(client):
    response = client.get("/historico")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_api_historico_clear_empties_the_log(logged_in_client, app):
    from datetime import datetime

    from models import DisplayLog

    with app.app_context():
        ucontrol_main.db.session.add(DisplayLog(type="song", title="x", ts=datetime(2026, 1, 1)))
        ucontrol_main.db.session.commit()

    before = logged_in_client.get("/api/historico").get_json()
    assert len(before) >= 1

    clear_response = logged_in_client.delete("/api/historico")
    assert clear_response.get_json() == {"ok": True}

    after = logged_in_client.get("/api/historico").get_json()
    assert after == []


def test_append_display_log_inserts_a_real_row(app):
    from display_log import append_display_log, clear_display_log, load_display_log

    with app.app_context():
        clear_display_log()
        append_display_log({"type": "bible", "title": "João 3:16"})
        log = load_display_log()

    assert len(log) == 1
    assert log[0]["type"] == "bible"
    assert log[0]["title"] == "João 3:16"
    assert log[0]["url"] is None
    assert "ts" in log[0]


def test_load_display_log_returns_oldest_first(app):
    from display_log import append_display_log, clear_display_log, load_display_log

    with app.app_context():
        clear_display_log()
        append_display_log({"type": "image", "title": "primeira"})
        append_display_log({"type": "image", "title": "segunda"})
        log = load_display_log()

    assert [entry["title"] for entry in log] == ["primeira", "segunda"]


def test_settings_store_save_and_load_round_trip(app):
    from settings_store import load_settings, save_settings

    with app.app_context():
        save_settings({"bible_translation": "nvi"})
        save_settings({"display_bg_dark": True})
        settings = load_settings()

    assert settings["bible_translation"] == "nvi"
    assert settings["display_bg_dark"] is True


def test_image_path_and_saved_urls_round_trip(app):
    from blueprints.display import load_image_path, load_urls, save_image_path, save_urls

    with app.app_context():
        save_image_path("/static/imagens/foo.jpg")
        save_urls({"url1": "http://a", "url2": "http://b", "url3": "", "name1": "Câmera"})
        image = load_image_path()
        urls = load_urls()

    assert image == {"image": "/static/imagens/foo.jpg"}
    assert urls == {"url1": "http://a", "url2": "http://b", "url3": "",
                    "name1": "Câmera", "name2": "", "name3": ""}


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
    socket_client = _operator_socket(app)
    assert connections.socketio_clients_connected == before + 1

    socket_client.disconnect()
    assert connections.socketio_clients_connected == before


def test_identify_as_monitor_is_returned_by_get_monitor_sids(app):
    import connections

    socket_client = _operator_socket(app)
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


def test_upload_list_and_delete_image_round_trip(logged_in_client, tmp_path, monkeypatch):
    import io
    from PIL import Image

    (tmp_path / "static" / "imagens").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), color="red").save(buffer, format="PNG")
    buffer.seek(0)

    upload_response = logged_in_client.post(
        "/upload",
        data={"images": (buffer, "teste.png")},
        content_type="multipart/form-data",
    )
    assert upload_response.status_code == 200
    saved = upload_response.get_json()["saved_files"]
    assert saved == ["teste.png"]

    images = logged_in_client.get("/imagens").get_json()
    assert images == ["/static/imagens/teste.png"]

    delete_response = logged_in_client.post("/delete_image", json={"image_name": "teste.png"})
    assert delete_response.get_json()["status"] == "success"
    assert logged_in_client.get("/imagens").get_json() == []


def test_delete_image_and_folder_reject_path_traversal(logged_in_client, tmp_path, monkeypatch):
    (tmp_path / "static" / "imagens").mkdir(parents=True)
    (tmp_path / "secret.txt").write_text("não deveria ser apagado")
    monkeypatch.chdir(tmp_path)

    delete_response = logged_in_client.post(
        "/delete_image", json={"image_name": "../secret.txt"}
    )
    assert delete_response.get_json()["status"] == "error"
    assert (tmp_path / "secret.txt").exists()

    folder_response = logged_in_client.delete("/api/image_folders/..")
    assert folder_response.status_code == 400
    assert (tmp_path / "static" / "imagens").exists()


def test_orders_store_save_and_load_round_trip(app):
    import orders_store

    with app.app_context():
        existing = orders_store.load_orders()
        # itens vazio é semanticamente "sem itens" (igual .pop('itens', None)
        # do sistema antigo) — por isso não entra na chave de volta, mesmo
        # padrão de chave-ausente-quando-vazio das Fases 5.2/5.4. Usa um
        # item de verdade aqui pra testar fidelidade do conteúdo, não essa
        # ambiguidade de lista vazia.
        sample = dict(existing, **{
            "2026-08-09-teste-store": {"tipo": "culto", "itens": [{"title": "Abertura", "url": "/order"}]},
        })
        assert orders_store.save_orders(sample) is True
        assert orders_store.load_orders().get("2026-08-09-teste-store") == sample["2026-08-09-teste-store"]
        # limpeza — banco de teste é compartilhado entre todos os testes da
        # sessão, remove só a entrada criada aqui, preserva o resto
        orders_store.save_orders(existing)
        assert "2026-08-09-teste-store" not in orders_store.load_orders()


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


def test_api_template_save_and_delete_round_trip(logged_in_client):
    save_response = logged_in_client.post(
        "/api/templates", json={"name": "Padrão", "items": ["Abertura", "Louvor"]}
    )
    assert save_response.get_json()["ok"] is True
    assert "Padrão" in logged_in_client.get("/api/templates").get_json()

    logged_in_client.delete("/api/templates/Padrão")
    assert "Padrão" not in logged_in_client.get("/api/templates").get_json()


def test_api_section_template_save_and_delete_round_trip(logged_in_client):
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


def test_legacy_save_and_load_compat_routes(app, client):
    # Fase 5.6: /save e /load (sem ?date=) miram a ordem de HOJE na tabela
    # Order, não mais o antigo order_of_service.json (bucket sem data).
    import orders_store
    from datetime import date

    today = date.today().isoformat()
    with app.app_context():
        existing = orders_store.load_orders()

    save_response = client.post("/save", json=[{"title": "Item legado", "url": "/order"}])
    assert save_response.status_code == 200

    load_response = client.get("/load")
    assert load_response.get_json() == [{"title": "Item legado", "url": "/order"}]

    with app.app_context():
        assert orders_store.load_orders().get(today, {}).get("itens") == [
            {"title": "Item legado", "url": "/order"}
        ]
        # limpeza — banco de teste é compartilhado entre todos os testes da sessão
        orders_store.save_orders(existing)


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


def test_agenda_detail_shows_real_order_data(logged_in_client, app):
    import orders_store

    with app.app_context():
        existing = orders_store.load_orders()
        orders_store.save_orders(dict(existing, **{"2026-08-09": {"dirigente": "João", "itens": []}}))

    response = logged_in_client.get("/agenda/2026-08-09")
    assert response.status_code == 200
    assert "João".encode() in response.data

    with app.app_context():
        orders_store.save_orders(existing)


def test_agenda_edit_renders_same_template_as_order_edit(logged_in_client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    agenda_response = logged_in_client.get("/agenda/2026-08-09/edit")
    order_response = logged_in_client.get("/order/2026-08-09")
    assert agenda_response.status_code == 200
    assert order_response.status_code == 200
    # Mesmo template (order_edit.html) por trás das duas rotas — o bloco
    # de dados que só esse template gera confirma isso.
    marker = b'id="order-edit-data"'
    assert marker in agenda_response.data
    assert marker in order_response.data


def test_save_route_and_duplicate_home_route_were_removed(client):
    assert not hasattr(ucontrol_main, "save_route")
    assert not hasattr(ucontrol_main, "home")
    # index() é quem responde em / (sempre venceu; home() nunca era alcançável)
    response = client.get("/")
    assert response.status_code == 302


def test_show_image_updates_display_state_module_live(app):
    # display_state._current_display_mode é reatribuído (não mutado em
    # lugar) pelos handlers — precisa ler via módulo pra pegar o valor
    # vivo, não um `from display_state import ...` que congelaria no
    # momento do import (mesma pegadinha do connections.py).
    import display_state

    socket_client = _operator_socket(app)
    socket_client.emit("show_image", {"image_url": "/static/imagens/teste.jpg"})

    assert display_state._current_display_mode == "image"
    assert display_state._last_image_url == "/static/imagens/teste.jpg"
    socket_client.disconnect()


def test_show_video_updates_display_state_module_live(app):
    import display_state

    socket_client = _operator_socket(app)
    socket_client.emit("show_video", {"video_url": "/static/videos/teste.mp4"})

    assert display_state._current_display_mode == "video"
    assert display_state._video_state["url"] == "/static/videos/teste.mp4"
    assert display_state._video_state["paused"] is False
    socket_client.disconnect()


def test_api_current_display_reflects_last_shown_image(app, client):
    socket_client = _operator_socket(app)
    socket_client.emit("show_image", {"image_url": "/static/imagens/atual.jpg"})
    socket_client.disconnect()

    response = client.get("/api/current-display")
    assert response.status_code == 200
    data = response.get_json()
    assert data["mode"] == "image"
    assert data["image_url"] == "/static/imagens/atual.jpg"


def test_api_monitor_sync_forwards_current_video_to_monitor_sids(app, logged_in_client):
    monitor_client = ucontrol_main.socketio.test_client(app)  # tela, sem login
    monitor_client.emit("identify", {"role": "monitor"})

    presenter_client = _operator_socket(app)
    presenter_client.emit("show_video", {"video_url": "/static/videos/sync.mp4"})
    presenter_client.disconnect()

    monitor_client.get_received()  # limpa os eventos já recebidos até aqui
    response = logged_in_client.post("/api/monitor/sync")
    assert response.status_code == 200

    received = monitor_client.get_received()
    events = [msg["name"] for msg in received]
    assert "display_monitor_video" in events
    payload = next(msg["args"][0] for msg in received if msg["name"] == "display_monitor_video")
    assert payload["video_url"] == "/static/videos/sync.mp4"

    monitor_client.disconnect()


def test_screen_share_offer_relays_to_target_sid(app):
    import connections

    # test_client.eio_sid é o sid de transporte do engine.io, não o
    # request.sid que os handlers usam — pega o sid de verdade via
    # connections.socketio_clients_by_sid (populado pelo handler connect),
    # conectando o receiver sozinho primeiro pra identificar sem ambiguidade.
    receiver = ucontrol_main.socketio.test_client(app)  # tela, sem login
    receiver_sid = next(iter(connections.socketio_clients_by_sid))
    sender = _operator_socket(app)

    sender.emit("screen_share_offer", {"sdp": "fake-sdp", "target_sid": receiver_sid})

    received = receiver.get_received()
    events = [msg["name"] for msg in received]
    assert "screen_share_offer" in events
    payload = next(msg["args"][0] for msg in received if msg["name"] == "screen_share_offer")
    assert payload["sdp"] == "fake-sdp"

    sender.disconnect()
    receiver.disconnect()


def test_update_lyrics_broadcasts_and_updates_display_state(app):
    import display_state

    socket_client = _operator_socket(app)
    socket_client.emit("update_lyrics", {"title": "Seção 1", "text": "Letra de teste"})

    received = socket_client.get_received()
    events = [msg["name"] for msg in received]
    assert "update_lyrics" in events
    assert display_state._current_display_mode == "lyrics"
    assert display_state._last_lyrics_payload == {"title": "Seção 1", "text": "Letra de teste"}
    socket_client.disconnect()


def test_api_lyrics_returns_song_data(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    add_response = client.post(
        "/add_song",
        data={
            "title": "Música de Letras",
            "author": "Autor",
            "sections[]": ["Verso 1"],
            "texts[]": ["Letra aqui"],
        },
    )
    assert add_response.status_code == 200
    songs = client.get("/search", query_string={"q": "Letras"}).get_json()
    song_id = songs[0]["id"]

    response = client.get(f"/api/lyrics/{song_id}")
    assert response.status_code == 200
    assert response.get_json()["title"] == "Música de Letras"


# ── "Preparar vs. liberar" (StagedContent) ─────────────────────────────

def test_stage_content_persists_and_broadcasts(app):
    from extensions import db
    from models import StagedContent

    socket_client = _operator_socket(app)
    socket_client.emit("stage_content", {
        "kind": "image",
        "payload": {"image_url": "/static/imagens/preparada.jpg"},
        "label": "foto de teste",
    })

    received = socket_client.get_received()
    events = [msg["name"] for msg in received]
    assert "content_staged" in events

    with app.app_context():
        staged = db.session.get(StagedContent, "image")
        assert staged is not None
        assert staged.payload == {"image_url": "/static/imagens/preparada.jpg"}
        assert staged.label == "foto de teste"

    socket_client.disconnect()


def test_release_staged_content_dispatches_to_real_handler_and_clears_staging(app):
    import display_state
    from extensions import db
    from models import StagedContent

    socket_client = _operator_socket(app)
    socket_client.emit("stage_content", {
        "kind": "image",
        "payload": {"image_url": "/static/imagens/liberar.jpg"},
        "label": "foto",
    })
    socket_client.get_received()

    socket_client.emit("release_staged_content", {"kind": "image"})
    received = socket_client.get_received()
    events = [msg["name"] for msg in received]
    # "display_image" só existe se release chamou o handle_show_image de
    # verdade (não uma reimplementação) — é o mesmo evento que o teste de
    # show_image direto (test_show_image_updates_display_state_module_live)
    # verifica indiretamente via display_state.
    assert "content_released" in events
    assert display_state._last_image_url == "/static/imagens/liberar.jpg"
    assert display_state._current_display_mode == "image"

    with app.app_context():
        assert db.session.get(StagedContent, "image") is None

    socket_client.disconnect()


def test_discard_staged_content_clears_without_going_live(app):
    import display_state
    from extensions import db
    from models import StagedContent

    socket_client = _operator_socket(app)
    socket_client.emit("stage_content", {
        "kind": "lyrics",
        "payload": {"title": "Nunca vai ao ar", "text": "..."},
        "label": "letra",
    })
    socket_client.get_received()

    socket_client.emit("discard_staged_content", {"kind": "lyrics"})
    received = socket_client.get_received()
    events = [msg["name"] for msg in received]
    assert "content_discarded" in events
    assert "update_lyrics" not in events  # não foi ao ar
    assert display_state._current_display_mode != "lyrics"

    with app.app_context():
        assert db.session.get(StagedContent, "lyrics") is None

    socket_client.disconnect()


def test_staged_content_kinds_do_not_clobber_each_other(app):
    import display_state
    from extensions import db
    from models import StagedContent

    # Reseta o live-follow (ver blueprints/display.py, _release_kind) —
    # sem isto, um teste anterior que liberou "image" deixaria esse kind
    # marcado como já confirmado, e o stage_content("image") abaixo iria
    # direto ao ar em vez de só preparar, quebrando a premissa deste teste
    # (que é justamente checar que PREPARAR dois kinds ao mesmo tempo não
    # atropela um ao outro).
    display_state._live_follow_kind = None

    socket_client = _operator_socket(app)
    socket_client.emit("stage_content", {"kind": "image", "payload": {"image_url": "/foto.jpg"}, "label": "foto"})
    socket_client.emit("stage_content", {"kind": "lyrics", "payload": {"title": "Refrão"}, "label": "letra"})
    socket_client.get_received()

    with app.app_context():
        assert db.session.get(StagedContent, "image") is not None
        assert db.session.get(StagedContent, "lyrics") is not None

    socket_client.disconnect()


def test_api_staged_content_reflects_current_state(app, client):
    socket_client = _operator_socket(app)
    socket_client.emit("stage_content", {
        "kind": "bible",
        "payload": {"reference": "João 3:16", "text": "..."},
        "label": "João 3:16",
    })
    socket_client.disconnect()

    response = client.get("/api/staged-content")
    assert response.status_code == 200
    data = response.get_json()
    assert "bible" in data
    assert data["bible"]["label"] == "João 3:16"


def test_get_next_order_skips_empty_calendar_rows(app):
    # O calendário cria linhas vazias pras datas sem culto marcado — o card
    # "Próximo culto" do dashboard tem que pular essas.
    import orders_store
    from extensions import db
    from models_orders import Order

    with app.app_context():
        db.session.add(Order(date="2099-01-02"))
        db.session.commit()
        orders_store.save_order("2099-01-03", {"tipo": "Culto Dominical", "itens": [{"title": "Abertura", "url": "/order"}]})

        found_date, order = orders_store.get_next_order("2099-01-01")
        assert found_date == "2099-01-03"
        assert order["tipo"] == "Culto Dominical"
        assert orders_store.get_next_order("2099-01-04") == (None, {})

        orders_store.save_order("2099-01-03", {})
        db.session.delete(db.session.get(Order, "2099-01-02"))
        db.session.commit()


def test_api_culto_proximo_splits_song_artist_and_builds_team(app, logged_in_client, monkeypatch):
    import datetime as real_datetime
    import blueprints.orders as orders_module
    import orders_store

    class FakeDate(real_datetime.date):
        @classmethod
        def today(cls):
            return cls(2099, 2, 1)

    monkeypatch.setattr(orders_module, "date", FakeDate)
    with app.app_context():
        orders_store.save_order("2099-02-03", {
            "tipo": "Culto Dominical",
            "horario_culto": "18:40",
            "dirigente": "Miquéias",
            "itens": [
                {"title": "Ele É Exaltado | Adhemar de Campos", "url": "/lyrics/349"},
                {"isBible": True, "reference": "Salmos 23", "title": "Salmos 23"},
            ],
            "louvor": {"cantores": ["Bel"], "musicos": [{"instrumento": "Teclado", "pessoa": "Jefferson"}]},
            "midia": {"lider": "Vitor", "palco": "", "visual": "Thaynara"},
        })

    data = logged_in_client.get("/api/culto/proximo").get_json()
    assert data["status"] == "ok"
    assert data["date"] == "2099-02-03"
    assert data["days_until"] == 2
    assert data["horario"] == "18:40"
    assert data["itens"][0] == {"kind": "song", "title": "Ele É Exaltado", "artist": "Adhemar de Campos", "url": "/lyrics/349"}
    assert data["itens"][1]["kind"] == "bible"
    assert {"funcao": "Mídia", "pessoa": "Vitor"} in data["equipe"]
    assert {"funcao": "Teclado", "pessoa": "Jefferson"} in data["equipe"]
    assert {"funcao": "Vozes", "pessoa": "Bel"} in data["equipe"]
    assert not any(e["funcao"] == "Palco" for e in data["equipe"])  # vazio não entra

    with app.app_context():
        orders_store.save_order("2099-02-03", {})


def test_group_activity_merges_consecutive_repeats():
    from blueprints.auth import group_activity

    log = [
        {"type": "image", "title": "/static/imagens/Geral/boas%20vindas.jpg", "ts": "2026-10-08T18:00:00"},
        {"type": "song", "title": "Ele É Exaltado", "ts": "2026-10-08T19:08:00"},
        {"type": "song", "title": "Ele É Exaltado", "ts": "2026-10-08T19:09:00"},
        {"type": "song", "title": "Ele É Exaltado", "ts": "2026-10-08T19:11:00"},
        {"type": "image", "title": "/lyrics/display + /clock", "ts": "2026-10-08T19:12:00"},
    ]
    groups = group_activity(log)

    assert [g["count"] for g in groups] == [1, 3, 1]
    assert groups[0]["target"] == "Cifra + Relógio"
    assert groups[1]["action"] == "Exibiu a letra de"
    assert (groups[1]["first_ts"], groups[1]["last_ts"]) == ("2026-10-08T19:08:00", "2026-10-08T19:11:00")
    assert groups[2]["target"] == "boas vindas.jpg"


def test_redesigned_pages_render_with_theme_and_nav(logged_in_client):
    for path in ("/dashboard", "/control", "/usuarios", "/songs", "/new_song", "/sheet_editor",
                 "/order", "/order/new", "/historico", "/links", "/help", "/bible",
                 "/bible/jo", "/bible/jo/3", "/bible/control/jo/3", "/presenter",
                 "/agenda/dashboard", "/agenda/edit", "/agenda/2099-01-01/admin",
                 "/agenda/2099-01-01/louvor"):
        response = logged_in_client.get(path)
        assert response.status_code == 200, path
        html = response.get_data(as_text=True)
        assert 'class="uc-app"' in html, path
        assert "css/app.css" in html, path
        assert 'class="site-nav"' in html, path
        assert "site-nav-link live" in html, path  # botão do Controle


def test_projector_screens_stay_outside_theme_and_nav(client):
    # Telas de projetor (monitor, cronômetro, relógio) têm visual próprio
    # e ninguém clica nelas — não recebem o app.css nem a barra.
    for path in ("/monitor", "/countdown", "/clock"):
        html = client.get(path).get_data(as_text=True)
        assert "css/app.css" not in html, path
        assert 'class="site-nav"' not in html, path


def test_public_pages_use_theme_without_operator_menu(client):
    # Páginas que a equipe abre sem login (agenda, cifras): tema novo, mas a
    # barra só mostra a marca e "Entrar" — nada do menu do operador.
    for path in ("/login", "/agenda", "/agenda/2099-01-01", "/view"):
        response = client.get(path)
        assert response.status_code == 200, path
        html = response.get_data(as_text=True)
        assert 'class="uc-app"' in html, path
        assert "site-nav-link live" not in html, path



def test_anonymous_socket_cannot_control_screens(app):
    """Sem login, comandos de controle do telão são ignorados — antes
    qualquer visitante do site podia trocar o que aparece no projetor."""
    screen = ucontrol_main.socketio.test_client(app)
    screen.emit("identify", {"role": "public"})
    screen.get_received()

    intruder = ucontrol_main.socketio.test_client(app)
    for event, data in (("show_image", {"image_url": "https://exemplo.com"}),
                        ("set_ticker", {"text": "invasão", "target": "all"}),
                        ("blackout", {"active": True}),
                        ("show_two_urls", {"url1": "/clock", "url2": "/img"}),
                        ("start_countdown", {"duration_seconds": 60}),
                        ("toggle_video_pause", {"paused": False})):
        intruder.emit(event, data)

    events = [msg["name"] for msg in screen.get_received()]
    for blocked in ("display_image", "ticker_update", "blackout", "display_two_urls",
                    "countdown_start", "video_pause"):
        assert blocked not in events, blocked

    intruder.disconnect()
    screen.disconnect()


def test_screens_without_login_can_still_sync_video_reset(app):
    """/monitor e /img não têm login e pedem "pausado no início" ao
    carregar um vídeo — essa forma específica continua aceita."""
    screen = ucontrol_main.socketio.test_client(app)
    screen.emit("identify", {"role": "monitor"})
    screen.emit("toggle_video_pause", {"paused": True})
    events = [msg["name"] for msg in screen.get_received()]
    assert "video_pause" in events
    screen.disconnect()


def test_logged_operator_socket_controls_screens(app):
    screen = ucontrol_main.socketio.test_client(app)
    operator = _operator_socket(app)
    operator.emit("blackout", {"active": False})
    events = [msg["name"] for msg in screen.get_received()]
    assert "blackout" in events
    operator.disconnect()
    screen.disconnect()


def test_presenter_requires_login(client):
    response = client.get("/presenter")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_blackout_state_is_sent_to_screen_that_connects_later(app):
    operator = _operator_socket(app)
    operator.emit("blackout", {"active": True})

    late_screen = ucontrol_main.socketio.test_client(app)
    late_screen.emit("identify", {"role": "public"})
    received = late_screen.get_received()
    assert any(m["name"] == "blackout" and m["args"][0]["active"] for m in received)

    operator.emit("blackout", {"active": False})
    other = ucontrol_main.socketio.test_client(app)
    other.emit("identify", {"role": "public"})
    assert not any(m["name"] == "blackout" for m in other.get_received())

    for c in (operator, late_screen, other):
        c.disconnect()


def test_display_public_has_full_screen_blackout_layer(client):
    html = client.get("/lyrics/display/public").get_data(as_text=True)
    assert 'id="blackout-layer"' in html


def _release_photo(op, url):
    op.emit("stage_content", {"kind": "image", "payload": {"image_url": url}, "label": "foto"})
    op.emit("release_staged_content", {"kind": "image"})
    op.get_received()


def test_control_switching_to_other_source_ends_photo_live_follow(app):
    """Depois de liberar uma foto do /presenter, pôr o relógio no telão
    pelo /control faz a próxima foto voltar a esperar o Liberar — antes
    ela entrava por cima do relógio na hora."""
    import display_state

    op = _operator_socket(app)
    _release_photo(op, "/static/imagens/a.jpg")
    assert display_state._live_follow_kind == "image"

    op.emit("show_image", {"image_url": "/clock"})
    assert display_state._live_follow_kind is None

    op.emit("stage_content", {"kind": "image", "payload": {"image_url": "/static/imagens/b.jpg"}, "label": "b"})
    events = [m["name"] for m in op.get_received()]
    assert "content_staged" in events
    assert display_state._last_image_url == "/clock"
    op.emit("discard_staged_content", {"kind": "image"})
    op.disconnect()


def test_control_staying_on_photos_keeps_live_follow(app):
    import display_state

    op = _operator_socket(app)
    _release_photo(op, "/static/imagens/a.jpg")
    op.emit("show_image", {"image_url": "/static/imagens/galeria.jpg"})
    op.emit("show_image", {"image_url": "/img"})
    assert display_state._live_follow_kind == "image"

    op.emit("stage_content", {"kind": "image", "payload": {"image_url": "/static/imagens/c.jpg"}, "label": "c"})
    assert display_state._last_image_url == "/static/imagens/c.jpg"

    op.emit("show_two_urls", {"url1": "/lyrics/display", "url2": "/clock"})
    assert display_state._live_follow_kind is None
    op.disconnect()


def _telao_status_events(client):
    return [m["args"][0] for m in client.get_received() if m["name"] == "telao_status"]


def test_telao_status_describes_live_staged_and_follow(app):
    import display_state

    op = _operator_socket(app)
    op.emit("show_image", {"image_url": "/clock"})
    status = _telao_status_events(op)[-1]
    assert status["live"]["label"] == "Relógio"
    assert status["monitor"] is None

    op.emit("stage_content", {"kind": "image", "payload": {"image_url": "/static/imagens/Culto%20Jovem.jpg"},
                              "label": "Culto Jovem.jpg"})
    status = _telao_status_events(op)[-1]
    assert {"kind": "image", "label": "Culto Jovem.jpg"} in status["staged"]

    op.emit("release_staged_content", {"kind": "image"})
    status = _telao_status_events(op)[-1]
    assert status["live"]["label"] == "Foto · Culto Jovem.jpg"
    assert not any(item["kind"] == "image" for item in status["staged"])
    assert status["follow"] == "image" and status["follow_label"] == "Fotos"

    op.emit("stop_live_follow", {})
    status = _telao_status_events(op)[-1]
    assert status["follow"] is None
    assert display_state._live_follow_kind is None
    op.disconnect()


def test_telao_status_shows_monitor_when_split_or_public_only(app):
    op = _operator_socket(app)
    op.emit("show_image", {"image_url": "/clock"})
    op.emit("show_two_urls", {"url1": "/lyrics/display", "url2": "/clock"})
    status = _telao_status_events(op)[-1]
    assert status["live"]["label"] == "Relógio"  # a tela pública não divide
    assert status["monitor"]["label"] == "Tela dividida · Cifra + Relógio"

    op.emit("show_image", {"image_url": "/bible/display"})
    assert _telao_status_events(op)[-1]["monitor"] is None

    op.emit("show_image", {"image_url": "/clock", "exclude_monitor": True})
    status = _telao_status_events(op)[-1]
    assert status["live"]["label"] == "Relógio"
    assert status["monitor"]["label"].startswith("Bíblia")
    op.disconnect()


def test_telao_status_route_requires_login(client, logged_in_client):
    assert client.get("/api/telao-status").status_code == 302
    data = logged_in_client.get("/api/telao-status").get_json()
    assert set(data) >= {"live", "monitor", "staged", "mode", "follow", "blackout"}


def test_telao_bar_only_for_logged_operator(client, logged_in_client):
    assert 'id="telao-bar"' in logged_in_client.get("/dashboard").get_data(as_text=True)
    assert 'id="telao-bar"' not in client.get("/agenda").get_data(as_text=True)
    assert 'id="telao-bar"' not in client.get("/lyrics/display/public").get_data(as_text=True)


def test_anonymous_cannot_stop_live_follow(app):
    import display_state

    op = _operator_socket(app)
    op.emit("stage_content", {"kind": "image", "payload": {"image_url": "/static/imagens/x.jpg"}, "label": "x"})
    op.emit("release_staged_content", {"kind": "image"})
    assert display_state._live_follow_kind == "image"
    intruder = ucontrol_main.socketio.test_client(app)
    intruder.emit("stop_live_follow", {})
    assert display_state._live_follow_kind == "image"
    op.emit("stop_live_follow", {})
    intruder.disconnect()
    op.disconnect()


def test_monitor_sync_copies_lyrics_released_from_other_page(app, client, logged_in_client):
    """Letra liberada pela página da música em Modo Público: o Sincronizar
    leva a letra pro monitor (antes mandava a última fonte do /control)."""
    monitor = ucontrol_main.socketio.test_client(app)  # tela, sem login
    monitor.emit("identify", {"role": "monitor"})
    op = _operator_socket(app)
    op.emit("show_image", {"image_url": "/bible/display"})
    op.emit("set_display_mode", {"exclude_monitor": True, "monitor_only": False})
    op.emit("stage_content", {"kind": "lyrics", "label": "Teu Povo — Coro",
                              "payload": {"songId": 1, "sectionIndex": 0, "title": "Coro", "text": "x", "type": "text"}})
    op.emit("release_staged_content", {"kind": "lyrics"})
    status = [m["args"][0] for m in op.get_received() if m["name"] == "telao_status"][-1]
    assert status["live"]["kind"] == "lyrics"
    assert status["monitor"]["label"].startswith("Bíblia")  # monitor congelado

    monitor.get_received()
    assert client.post("/api/monitor/sync").status_code in (302, 401)  # exige login
    assert logged_in_client.post("/api/monitor/sync").status_code == 200
    sent = [m["args"][0]["url"] for m in monitor.get_received() if m["name"] == "display_monitor_content"]
    assert sent == ["/lyrics/display/public"]

    op.emit("set_display_mode", {"exclude_monitor": False, "monitor_only": False})
    op.emit("stop_live_follow", {})
    op.disconnect()
    monitor.disconnect()


def test_bible_display_can_fetch_current_verse(app, client):
    op = _operator_socket(app)
    op.emit("update_bible", {"reference": "João 3:16", "text": "16 Porque Deus amou o mundo",
                             "verses": [{"num": 16, "text": "Porque Deus amou o mundo"}]})
    data = client.get("/api/bible/current").get_json()  # tela sem login
    assert data["reference"] == "João 3:16"
    op.disconnect()


def test_telao_ping_acks_for_operator(app):
    op = _operator_socket(app)
    assert op.emit("telao_ping", {}, callback=True) == {"ok": True}
    op.disconnect()


def test_command_pages_mark_their_command_area(logged_in_client):
    for path in ("/control", "/presenter", "/lyrics/1", "/bible/jo/3", "/bible/control/jo/3/16-16"):
        html = logged_in_client.get(path).get_data(as_text=True)
        assert "data-telao-commands" in html, path


def test_telao_status_shows_slideshow_ticker_countdown_and_stops_them(app):
    op = _operator_socket(app)
    control = _operator_socket(app)
    op.emit("stop_ticker", {"target": "all"})  # outro teste pode ter deixado aviso ligado
    control.emit("slideshow_state", {"running": True, "interval": 7, "count": 12})
    op.emit("set_ticker", {"text": "Bem-vindos", "target": "public"})
    op.emit("start_countdown", {"duration_seconds": 300, "label": "Culto"})
    status = _telao_status_events(op)[-1]
    assert status["slideshow"] == {"interval": 7, "count": 12}
    assert status["ticker"] == {"text": "Bem-vindos", "targets": ["public"]}
    assert status["countdown"]["label"] == "Culto" and not status["countdown"]["paused"]

    control.get_received()
    op.emit("stop_slideshow", {})
    assert any(m["name"] == "slideshow_stop" for m in control.get_received())
    op.emit("stop_ticker", {"target": "all"})
    op.emit("reset_countdown", {})
    status = _telao_status_events(op)[-1]
    assert status["slideshow"] is None and status["ticker"] is None and status["countdown"] is None
    op.disconnect()
    control.disconnect()


def test_slideshow_forgotten_when_its_control_tab_closes(app):
    op = _operator_socket(app)
    control = _operator_socket(app)
    control.emit("slideshow_state", {"running": True, "interval": 5, "count": 3})
    control.disconnect()
    op.emit("telao_ping", {})
    import telao
    assert telao.build_status()["slideshow"] is None
    op.disconnect()


def test_panel_song_api_and_order_bible_urls(logged_in_client):
    data = logged_in_client.get("/api/painel/musica").get_json()
    assert set(data) == {"song_id", "order_date"}


def test_embedded_pages_hide_nav_via_client_detection(logged_in_client):
    html = logged_in_client.get("/presenter").get_data(as_text=True)
    assert "uc-embed" in html  # script que detecta iframe e esconde menu/barra


def test_control_has_panel_tools_and_mode_choice(logged_in_client):
    html = logged_in_client.get("/control").get_data(as_text=True)
    for marker in ('id="ctl-panel"', 'data-page="musica"', 'data-page="biblia"', 'data-page="fotos"',
                   'data-page="ordem"', 'data-open-tool="timer"', 'data-open-tool="split"',
                   'data-mode="public"', 'data-mode="monitor"', 'id="name1"', 'data-slot="left"'):
        assert marker in html, marker
    assert "monitor-mode-btn" not in html  # interruptores antigos saíram


def test_save_urls_requires_login_and_keeps_names(app, client, logged_in_client):
    assert client.post("/save_urls", json={"url1": "x"}).status_code in (302, 400, 401)
    r = logged_in_client.post("/save_urls", json={"url1": "http://cam", "name1": "Câmera",
                                                  "url2": "", "url3": ""})
    assert r.get_json()["status"] == "success"
    assert logged_in_client.get("/load_urls").get_json()["name1"] == "Câmera"


def test_single_gallery_lives_in_presenter(logged_in_client):
    control = logged_in_client.get("/control").get_data(as_text=True)
    assert 'id="imageGallery"' not in control  # galeria do Controle saiu
    assert 'data-open-page="fotos"' in control
    presenter = logged_in_client.get("/presenter").get_data(as_text=True)
    for marker in ('id="imageGallery"', 'id="btnSlideshow"', 'id="slideshowInterval"', 'id="newFolderName"',
                   'id="deleteFolderBtn"', 'id="toggleSelectBtn"', 'id="deleteSelectedBtn"', 'id="fileInput"'):
        assert marker in presenter, marker


def test_slideshow_show_image_respects_server_mode(app):
    import display_state
    monitor = ucontrol_main.socketio.test_client(app)
    monitor.emit("identify", {"role": "monitor"})
    op = _operator_socket(app)
    op.emit("set_display_mode", {"exclude_monitor": False, "monitor_only": True})
    before = display_state._last_image_url
    monitor.get_received()
    op.emit("show_image", {"image_url": "/static/imagens/slide.jpg", "use_active_mode": True})
    got = [m for m in monitor.get_received() if m["name"] == "display_monitor_content"]
    assert got and got[0]["args"][0]["url"] == "/static/imagens/slide.jpg"
    assert display_state._last_image_url == before  # tela pública não mudou
    op.emit("set_display_mode", {"exclude_monitor": False, "monitor_only": False})
    op.disconnect()
    monitor.disconnect()


def test_letra_route_gives_current_lyrics_to_screens_opening_later(app, client):
    op = _operator_socket(app)
    op.emit("update_lyrics", {"title": "Coro", "text": "Santo, santo", "songId": 1, "type": "text"})
    op.emit("show_image", {"image_url": "/lyrics/display/public"})
    data = client.get("/api/current-display").get_json()
    assert data["mode"] == "lyrics" and data["text"] == "Santo, santo"
    op.disconnect()


def test_cifra_shows_lyrics_to_public_and_cifra_on_monitor(app):
    op = _operator_socket(app)
    op.emit("show_image", {"image_url": "/lyrics/display"})
    status = _telao_status_events(op)[-1]
    assert status["live"]["kind"] == "lyrics"
    assert status["live"]["url"] == "/lyrics/display/public"
    assert status["monitor"]["kind"] == "cifra"
    op.emit("show_image", {"image_url": "/lyrics/display/public"})
    assert _telao_status_events(op)[-1]["monitor"] is None
    op.disconnect()


def test_telao_status_gives_monitor_urls_for_preview(app):
    op = _operator_socket(app)
    op.emit("show_image", {"image_url": "/clock"})
    op.emit("show_monitor_content", {"url": "/lyrics/display"})
    mon = _telao_status_events(op)[-1]["monitor"]
    assert mon["kind"] == "cifra" and mon["url"] == "/lyrics/display"
    op.emit("show_two_urls", {"url1": "/lyrics/display", "url2": "/clock"})
    mon = _telao_status_events(op)[-1]["monitor"]
    assert (mon["url1"], mon["url2"]) == ("/lyrics/display", "/clock")
    op.disconnect()


def test_screens_load_shared_zoom_fit(client):
    for path in ("/monitor", "/lyrics/display/public", "/img"):
        assert "js/zoom_fit.js" in client.get(path).get_data(as_text=True), path


def test_agenda_edit_has_whatsapp_share_buttons(logged_in_client):
    html = logged_in_client.get("/agenda/edit").get_data(as_text=True)
    for marker in ('id="copyWhatsBtn"', 'id="shareMenu"', 'data-format="grid"', 'data-format="light"',
                   'data-format="dark"', 'id="saveImgBtn"', "js/pages/agenda_share.js"):
        assert marker in html, marker


def test_culto_keys_and_current_culto_of_the_day(app):
    from datetime import datetime

    import orders_store as s

    assert (s.key_date("2026-10-04-2"), s.key_seq("2026-10-04-2")) == ("2026-10-04", 2)
    assert (s.key_seq("2026-10-04"), s.make_key("2026-10-04", 1), s.make_key("2026-10-04", 3)) == (1, "2026-10-04", "2026-10-04-3")
    with app.app_context():
        assert s.next_free_key("2031-05-04") == "2031-05-04"
        s.save_order("2031-05-04", {"tipo": "Culto Dominical", "horario_culto": "18:40",
                                    "eventos": [{"titulo": "Ensaio", "hora": "16:00"}]})
        assert s.next_free_key("2031-05-04") == "2031-05-04-2"
        s.save_order("2031-05-04-2", {"tipo": "Escola Bíblica", "horario_culto": "09:00"})
        try:
            # Em ordem de horário, não de chave
            assert [k for k, _ in s.day_orders("2031-05-04")] == ["2031-05-04-2", "2031-05-04"]
            assert s.next_free_key("2031-05-04") == "2031-05-04-3"
            # De manhã é o da manhã; a partir de 1h antes do da noite, o da noite
            assert s.current_key("2031-05-04", datetime(2031, 5, 4, 10, 0)) == "2031-05-04-2"
            assert s.current_key("2031-05-04", datetime(2031, 5, 4, 17, 50)) == "2031-05-04"
            assert s.current_key("2031-05-04", datetime(2031, 5, 4, 7, 0)) == "2031-05-04-2"
            # Outro dia: o primeiro pelo horário
            assert s.current_key("2031-05-04", datetime(2031, 5, 1, 20, 0)) == "2031-05-04-2"
            assert s.get_next_order("2031-05-04", datetime(2031, 5, 1, 20, 0))[0] == "2031-05-04-2"
            assert s.current_key("2031-05-05") == "2031-05-05"
        finally:
            s.save_order("2031-05-04", {})
            s.save_order("2031-05-04-2", {})


def test_second_culto_has_own_pages_and_no_events(logged_in_client):
    c = logged_in_client
    c.post("/api/orders/2031-06-01", json={"tipo": "Culto Dominical", "horario_culto": "18:40",
                                           "eventos": [{"titulo": "Ensaio do louvor", "hora": "16:00"}]})
    try:
        # "Novo culto" abre o louvor da próxima chave livre
        r = c.get("/agenda/2031-06-01/novo-culto")
        assert r.status_code == 302 and r.headers["Location"].endswith("/agenda/2031-06-01-2/louvor")
        # Eventos são do dia: ignorados no 2º culto
        c.post("/api/orders/2031-06-01-2", json={"tipo": "Escola Bíblica", "horario_culto": "09:00",
                                                 "eventos": [{"titulo": "Não deveria ficar"}]})
        assert "eventos" not in c.get("/api/orders/2031-06-01-2").get_json()

        day = c.get("/agenda/2031-06-01/admin").get_data(as_text=True)
        assert day.index("Escola Bíblica") < day.index("Culto Dominical")
        assert "/agenda/2031-06-01-2/louvor" in day and "Ensaio do louvor" in day
        # Chave do 2º culto na URL da página do dia mostra o dia inteiro
        assert "Ensaio do louvor" in c.get("/agenda/2031-06-01-2").get_data(as_text=True)

        louvor = c.get("/agenda/2031-06-01-2/louvor").get_data(as_text=True)
        assert 'href="/agenda/2031-06-01/louvor"' in louvor and 'id="deleteCultoBtn"' in louvor
        assert c.get("/agenda/2031-06-01-2/eventos").headers["Location"].endswith("/agenda/2031-06-01/eventos")

        # Excluir o 1º culto mantém os eventos do dia
        assert c.delete("/api/cultos/2031-06-01").status_code == 200
        assert c.get("/api/orders/2031-06-01").get_json() == {
            "eventos": [{"titulo": "Ensaio do louvor", "hora": "16:00", "responsavel": "", "obs": ""}]}
        assert c.delete("/api/cultos/2031-06-01-2").status_code == 200
        assert c.get("/api/orders/2031-06-01-2").status_code == 404
    finally:
        c.delete("/api/orders/2031-06-01")
        c.delete("/api/orders/2031-06-01-2")


def test_agenda_calendars_load_shared_culto_helper(logged_in_client):
    for path in ("/agenda", "/agenda/edit"):
        assert "js/agenda_cultos.js" in logged_in_client.get(path).get_data(as_text=True), path


def test_tipo_culto_outro_keeps_custom_name(logged_in_client):
    import re

    c = logged_in_client
    c.post("/api/orders/2031-07-05", json={"tipo": "Culto de Missões", "horario_culto": "19:00"})
    try:
        for path in ("/order/2031-07-05", "/agenda/2031-07-05/louvor"):
            html = c.get(path).get_data(as_text=True)
            assert '<option value="Outro" selected>' in html, path
            campo = re.search(r'<input[^>]*id="(?:orderType|tipo)Outro"[^>]*>', html).group(0)
            assert 'value="Culto de Missões"' in campo and " hidden" not in campo, path
        # Tipo da lista: "Outro" fechado
        c.post("/api/orders/2031-07-05", json={"tipo": "Culto de Oração", "horario_culto": "19:30"})
        html = c.get("/order/2031-07-05").get_data(as_text=True)
        assert '<option value="Culto de Oração" selected>' in html and 'id="orderTypeOutro"' in html
    finally:
        c.delete("/api/orders/2031-07-05")


def test_view_order_marks_items_done(app, client, logged_in_client):
    import orders_store

    itens = [{"anyText": "Oração"}, {"title": "Hino | Autor", "url": "/lyrics/1"},
             {"isBible": True, "reference": "João 3:16", "title": "📖 João 3:16"}, {"anyText": "Oração"}]
    assert orders_store.item_ids(itens) == ["texto:Oração#1", "url:/lyrics/1#1", "biblia:João 3:16#1", "texto:Oração#2"]
    logged_in_client.post("/api/orders/2031-08-02", json={"tipo": "Culto Dominical", "itens": itens})
    try:
        # Visitante não marca; logado marca, todos veem
        assert client.post("/api/orders/2031-08-02/feitos", json={"item": "texto:Oração#2", "feito": True}).status_code in (302, 401)
        r = logged_in_client.post("/api/orders/2031-08-02/feitos", json={"item": "texto:Oração#2", "feito": True})
        assert r.get_json()["feitos"] == ["texto:Oração#2"]
        assert client.get("/api/orders/2031-08-02/feitos").get_json()["feitos"] == ["texto:Oração#2"]
        html = client.get("/view/order/2031-08-02").get_data(as_text=True)
        assert html.count(" feito\"") == 1 and 'data-item="texto:Oração#2"' in html
        assert 'button type="button" class="item-check"' not in html
        assert 'class="item-check" aria-pressed' in logged_in_client.get("/view/order/2031-08-02").get_data(as_text=True)
        # Editar a ordem não apaga a marcação
        logged_in_client.post("/api/orders/2031-08-02", json={"tipo": "Culto Dominical", "itens": itens[::-1]})
        assert client.get("/api/orders/2031-08-02/feitos").get_json()["feitos"] == ["texto:Oração#2"]
        logged_in_client.post("/api/orders/2031-08-02/feitos", json={"limpar": True})
        assert client.get("/api/orders/2031-08-02/feitos").get_json()["feitos"] == []
    finally:
        logged_in_client.delete("/api/orders/2031-08-02")


def test_items_going_on_screen_are_marked_done(app):
    from datetime import date

    import display_state
    import orders_store
    from blueprints import display

    today = date.today().isoformat()
    itens = [{"title": "Hino | A", "url": "/lyrics/7"},
             {"isBible": True, "reference": "Romanos 10:14-17", "title": "📖 Romanos 10:14-17"},
             {"anyText": "Oração"}, {"title": "Hino | A", "url": "/lyrics/7"}]
    with app.app_context():
        antes = orders_store.get_order(today)
        orders_store.save_order(today, {"tipo": "Culto Dominical", "itens": itens})
    display_state._live_follow_kind = None
    display._ultimo_feito_auto = None
    sock = _operator_socket(app)

    def no_ar(kind, payload):
        sock.emit("stage_content", {"kind": kind, "payload": payload, "label": "x"})
        sock.emit("release_staged_content", {"kind": kind})
        sock.get_received()
        with app.app_context():
            return orders_store.get_feitos(today)

    try:
        assert no_ar("lyrics", {"songId": 7, "sectionIndex": 0, "title": "V1"}) == ["url:/lyrics/7#1"]
        # Outra seção da mesma música não marca a 2ª vez que ela aparece na ordem
        assert no_ar("lyrics", {"songId": 7, "sectionIndex": 1, "title": "Refrão"}) == ["url:/lyrics/7#1"]
        # Versículo dentro da passagem da ordem marca a leitura
        assert no_ar("bible", {"reference": "Romanos 10:15", "text": "..."})[-1] == "biblia:Romanos 10:14-17#1"
        # A música volta depois de outra coisa: agora é a 2ª ocorrência
        assert no_ar("lyrics", {"songId": 7, "sectionIndex": 0, "title": "V1"})[-1] == "url:/lyrics/7#2"
        # Música fora da ordem não marca nada
        assert len(no_ar("lyrics", {"songId": 999, "sectionIndex": 0, "title": "X"})) == 3
    finally:
        sock.disconnect()
        display_state._live_follow_kind = None
        with app.app_context():
            orders_store.save_order(today, {})
            if antes:
                orders_store.save_order(today, antes)
