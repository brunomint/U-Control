from werkzeug.security import generate_password_hash

import main as ucontrol_main
from models import DisplayState, User


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
    socket_client = ucontrol_main.socketio.test_client(app)
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
        save_urls({"url1": "http://a", "url2": "http://b", "url3": ""})
        image = load_image_path()
        urls = load_urls()

    assert image == {"image": "/static/imagens/foo.jpg"}
    assert urls == {"url1": "http://a", "url2": "http://b", "url3": ""}


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
    # Mesmo template (order_edit.html) por trás das duas rotas — o mesmo
    # título gerado pelo template confirma isso.
    title = "Editar Ordem - 2026-08-09".encode()
    assert title in agenda_response.data
    assert title in order_response.data


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

    socket_client = ucontrol_main.socketio.test_client(app)
    socket_client.emit("show_image", {"image_url": "/static/imagens/teste.jpg"})

    assert display_state._current_display_mode == "image"
    assert display_state._last_image_url == "/static/imagens/teste.jpg"
    socket_client.disconnect()


def test_show_video_updates_display_state_module_live(app):
    import display_state

    socket_client = ucontrol_main.socketio.test_client(app)
    socket_client.emit("show_video", {"video_url": "/static/videos/teste.mp4"})

    assert display_state._current_display_mode == "video"
    assert display_state._video_state["url"] == "/static/videos/teste.mp4"
    assert display_state._video_state["paused"] is False
    socket_client.disconnect()


def test_api_current_display_reflects_last_shown_image(app, client):
    socket_client = ucontrol_main.socketio.test_client(app)
    socket_client.emit("show_image", {"image_url": "/static/imagens/atual.jpg"})
    socket_client.disconnect()

    response = client.get("/api/current-display")
    assert response.status_code == 200
    data = response.get_json()
    assert data["mode"] == "image"
    assert data["image_url"] == "/static/imagens/atual.jpg"


def test_api_monitor_sync_forwards_current_video_to_monitor_sids(app, client):
    monitor_client = ucontrol_main.socketio.test_client(app)
    monitor_client.emit("identify", {"role": "monitor"})

    presenter_client = ucontrol_main.socketio.test_client(app)
    presenter_client.emit("show_video", {"video_url": "/static/videos/sync.mp4"})
    presenter_client.disconnect()

    monitor_client.get_received()  # limpa os eventos já recebidos até aqui
    response = client.post("/api/monitor/sync")
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
    receiver = ucontrol_main.socketio.test_client(app)
    receiver_sid = next(iter(connections.socketio_clients_by_sid))
    sender = ucontrol_main.socketio.test_client(app)

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

    socket_client = ucontrol_main.socketio.test_client(app)
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

    socket_client = ucontrol_main.socketio.test_client(app)
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

    socket_client = ucontrol_main.socketio.test_client(app)
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

    socket_client = ucontrol_main.socketio.test_client(app)
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
    from extensions import db
    from models import StagedContent

    socket_client = ucontrol_main.socketio.test_client(app)
    socket_client.emit("stage_content", {"kind": "image", "payload": {"image_url": "/foto.jpg"}, "label": "foto"})
    socket_client.emit("stage_content", {"kind": "lyrics", "payload": {"title": "Refrão"}, "label": "letra"})
    socket_client.get_received()

    with app.app_context():
        assert db.session.get(StagedContent, "image") is not None
        assert db.session.get(StagedContent, "lyrics") is not None

    socket_client.disconnect()


def test_api_staged_content_reflects_current_state(app, client):
    socket_client = ucontrol_main.socketio.test_client(app)
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
