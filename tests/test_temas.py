"""Temas do telão (temas_store.py)."""


def test_fundo_animado_valida_estilo_cores_e_velocidade():
    """Fundo animado (static/js/fundo_animado.js): o que não vale volta pro padrão."""
    import temas_store
    ok = {'type': 'animado', 'estilo': 'aurora', 'cores': ['#111111', '#222222', '#333333'], 'base': '#000000', 'velocidade': 'lenta'}
    assert temas_store.normalizar_fundo(ok) == ok
    ruim = temas_store.normalizar_fundo({'type': 'animado', 'estilo': 'fogos', 'cores': ['red', '#222222'], 'base': 'url(x)', 'velocidade': 'turbo'})
    assert ruim == {'type': 'animado', 'estilo': 'luzes', 'cores': ['#222222', '#0e7490', '#1e3a8a'],
                    'base': '#05050c', 'velocidade': 'normal'}
    # O JS e o Python conhecem os mesmos estilos e velocidades
    js = open('static/js/fundo_animado.js', encoding='utf-8').read()
    for nome in temas_store.ESTILOS_ANIMADOS + temas_store.VELOCIDADES:
        assert f"'{nome}'" in js or f"{nome}:" in js, nome
