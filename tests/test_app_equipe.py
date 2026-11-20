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
