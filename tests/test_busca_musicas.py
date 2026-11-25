"""Busca de músicas (busca_musicas.py): rápida, enxuta e sempre em dia."""
import pytest


@pytest.fixture
def musicas(app):
    import busca_musicas
    import songs_store
    ids = []
    with app.app_context():
        for titulo, autor, letra in (('Graça Sublime', 'John Newton', 'Oh! graça sublime do Senhor'),
                                     ('Grandioso És Tu', 'Carl Boberg', 'Senhor, meu Deus, quando eu maravilhado'),
                                     ('Ao Deus de Abraão', 'Tradicional', 'Ao Deus de Abraão louvai'),
                                     ('Santo', 'Asaph Borba', 'Santo, santo é o Senhor')):
            sid = songs_store.next_song_id()
            songs_store.save_song({'id': sid, 'title': titulo, 'author': autor,
                                   'sections': [{'title': 'V', 'text': [letra]}]})
            ids.append(sid)
    yield ids
    with app.app_context():
        for sid in ids:
            songs_store.delete_song(sid)
    busca_musicas.invalidar()


def _titulos(client, url):
    r = client.get(url)
    assert r.status_code == 200
    return r.get_json()


def test_search_devolve_so_id_titulo_autor_e_acha_sem_acento(client, musicas):
    res = _titulos(client, '/search?q=graca')
    assert res and set(res[0]) == {'id', 'title', 'author'}
    assert res[0]['title'] == 'Graça Sublime'
    # Título que começa com a busca vem antes da que só tem na letra
    assert [m['title'] for m in _titulos(client, '/search?q=santo')][:1] == ['Santo']
    assert 'Graça Sublime' in [m['title'] for m in _titulos(client, '/search?q=NEWTON')]
    assert 'Grandioso És Tu' in [m['title'] for m in _titulos(client, '/search?q=maravilhado')]
    assert _titulos(client, '/search?q=') == []


def test_indice_se_refaz_quando_uma_musica_muda(app, client, musicas):
    import songs_store
    assert not _titulos(client, '/search?q=xyzzy')
    with app.app_context():
        song = songs_store.get_song(musicas[0])
        song['sections'][0]['text'] = ['agora com xyzzy na letra']
        songs_store.save_song(song)
    assert [m['id'] for m in _titulos(client, '/search?q=xyzzy')] == [musicas[0]]
    with app.app_context():
        songs_store.delete_song(musicas[3])
    assert 'Santo' not in [m['title'] for m in _titulos(client, '/search?q=santo')]


def test_api_songs_search_usa_o_mesmo_indice(client, musicas):
    res = _titulos(client, '/api/songs/search?q=abraao')
    assert [m['title'] for m in res] == ['Ao Deus de Abraão']
