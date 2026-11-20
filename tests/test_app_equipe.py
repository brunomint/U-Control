"""App Android da equipe (blueprints/app_equipe.py, docs/APP_EQUIPE.md)."""
import updates


def test_identidade_e_publica_e_diz_que_e_o_ucontrol(client):
    """O app acha o servidor testando os endereços do Wi-Fi: precisa
    responder sem login e se identificar, senão qualquer coisa na porta
    8585 seria aceita como a igreja."""
    r = client.get('/api/identidade')
    assert r.status_code == 200
    dados = r.get_json()
    assert dados['app'] == 'U-Control'
    assert dados['versao'] == updates.current_version()
    assert dados['api'] >= 1
    assert isinstance(dados['igreja'], str)
    assert len(dados['id']) == 32
    assert client.get('/api/identidade').get_json()['id'] == dados['id']
    assert r.headers['Cache-Control'] == 'no-store'


def test_identidade_traz_o_nome_da_igreja(app, client, logged_in_client):
    logged_in_client.post('/api/agenda/nome-igreja', json={'nome': 'Igreja Teste'})
    try:
        assert client.get('/api/identidade').get_json()['igreja'] == 'Igreja Teste'
    finally:
        logged_in_client.post('/api/agenda/nome-igreja', json={'nome': ''})


def _musica_e_culto(app, titulo='Hino App', data=None):
    from datetime import date, timedelta
    import orders_store
    import songs_store
    data = data or (date.today() + timedelta(days=2)).isoformat()
    with app.app_context():
        sid = songs_store.next_song_id()
        songs_store.save_song({'id': sid, 'title': titulo, 'author': 'Autor',
                               'sections': [{'title': 'V', 'text': ['la la']}]})
        orders_store.save_order(data, {'tipo': 'Culto da noite', 'dirigente': 'Ana', 'itens': [
            {'title': titulo, 'url': f'/lyrics/{sid}'},
            {'isBible': True, 'reference': 'Sl 23'},
            {'anyText': 'Avisos'},
        ]})
    return sid, data


def test_salvar_lista_os_proximos_cultos_com_as_musicas(app, client):
    from datetime import date, timedelta
    import orders_store
    sid, data = _musica_e_culto(app)
    longe = (date.today() + timedelta(days=40)).isoformat()
    _musica_e_culto(app, 'Longe', longe)
    try:
        r = client.get('/api/app/salvar?dias=15')
        assert r.status_code == 200 and r.headers['Cache-Control'] == 'no-store'
        cultos = {c['chave']: c for c in r.get_json()['cultos']}
        assert longe not in cultos
        c = cultos[data]
        assert c['titulo'] == 'Culto da noite' and c['dirigente'] == 'Ana'
        assert [m['id'] for m in c['musicas']] == [sid]
        assert c['musicas'][0]['titulo'] == 'Hino App'
    finally:
        with app.app_context():
            orders_store.save_order(data, {})
            orders_store.save_order(longe, {})


def test_versao_da_musica_muda_com_a_cifra_e_nao_com_o_telao(app, client):
    import songs_store
    sid, data = _musica_e_culto(app)
    v1 = client.get(f'/api/app/musicas?ids={sid},999999').get_json()['musicas']
    assert [m['id'] for m in v1] == [sid]   # a que não existe fica de fora
    with app.app_context():
        songs_store.touch_last_played(sid)
    assert client.get(f'/api/app/musicas?ids={sid}').get_json()['musicas'][0]['versao'] == v1[0]['versao']
    with app.app_context():
        songs_store.save_song({'id': sid, 'title': 'Hino App', 'author': 'Autor',
                               'sections': [{'title': 'V', 'text': ['outra letra']}]})
    assert client.get(f'/api/app/musicas?ids={sid}').get_json()['musicas'][0]['versao'] != v1[0]['versao']
