"""Controle simples (/lite/controle, Fase 3 de docs/PLANO-LITE.md): botões
do telão para aparelho antigo, por formulário (POST com CSRF), sem
Socket.IO.

Funciona como o Stream Deck (blueprints/atalhos.py): "próximo/anterior" e
"abrir música" vão para o Controle aberto num PC, que sabe qual é a próxima
estrofe; tela preta/branca/logo, esconder a letra e relógio o servidor faz
sozinho. As ações passam pelos mesmos handlers de socket do Controle, com a
mesma regra de quem cuida de cada tela (destinos.py): este aparelho escolhe
"Minhas telas" e, se a tela está com outra pessoa, "Assumir".

Este aparelho não tem conexão em tempo real, então não "segura" a tela
sozinho (destinos.dono larga a tela de quem não tem aparelho conectado):
ele mexe numa tela livre ou numa tela da mesma pessoa logada noutro aparelho."""
from flask import g

import display_state

MODOS = [('public', 'Público'), ('monitor', 'Palco'), ('all', 'Os dois'), ('none', 'Nenhuma')]
NEUTRAS = [('preta', 'Tela preta'), ('branca', 'Tela branca'), ('logo', 'Logo')]


def _rodar(handler, dados):
    """Chama um handler de socket do Controle (com login e regra das telas).
    Devolve (resultado, motivo da recusa ou None)."""
    from blueprints.atalhos import _como_socket
    g.pop('uc_recusa', None)
    with _como_socket():
        resultado = handler(dados)
    return resultado, g.pop('uc_recusa', None)


def _minhas_telas():
    import destinos
    return destinos.telas_do_modo(display_state.device_mode())


RECADO_PARA = [('monitor', 'Palco'), ('public', 'Público'), ('ambos', 'Os dois')]


def _destino_do_recado():
    from flask import request
    para = request.form.get('para', 'monitor')
    return ['public', 'monitor'] if para == 'ambos' else [para if para in ('public', 'monitor') else 'monitor']


def estado():
    """O que a página mostra no alto: o que está em cada tela e as minhas telas."""
    import destinos
    import telao
    from blueprints import atalhos
    from extensions import db
    from models import LyricsState, StagedContent
    publico = telao.describe(telao._public_entry())['label']
    palco = telao.describe(telao._monitor)['label'] if telao._monitor else 'O mesmo do público'
    preparado = db.session.query(StagedContent).order_by(StagedContent.updated_at.desc()).first()
    letra = LyricsState.query.first()
    minhas = _minhas_telas()
    return {
        'publico': publico,
        'palco': palco,
        'neutras': dict(display_state._telas_neutras),
        'neutra_minha': next((t for t, _ in NEUTRAS if minhas and all(
            display_state._telas_neutras.get(x) == t for x in minhas)), None),
        'texto_visivel': not (letra and letra.visible is False),
        'preparado': (preparado.label or preparado.kind) if preparado else None,
        'modo': display_state.device_mode(),
        'donos': destinos.donos(),
        'controle_aberto': atalhos.controle_aberto(),
        'recados': {t: x for t, x in _letreiros().items() if t in ('public', 'monitor')},
    }


def _letreiros():
    from blueprints import ticker
    return dict(ticker._por_tela)


def acao(nome, valor=''):
    """Faz a ação de um botão. Devolve (ok, mensagem, extra)."""
    from blueprints import atalhos
    from blueprints.display import handle_blackout, handle_set_display_mode, handle_show_image
    from blueprints.lyrics import handle_toggle_lyrics_visibility

    if nome in ('proximo', 'anterior'):
        r = atalhos._navegar(1 if nome == 'proximo' else -1)
        return r.get('ok'), None if r.get('ok') else r.get('erro'), None

    if nome == 'abrir':
        if not (valor.startswith('/lyrics/') or valor.startswith('/bible')):
            return False, 'Item inválido.', None
        r = atalhos.abrir_no_controle(valor)
        return r.get('ok'), ('Aberto no Controle. Use Próximo para ir à primeira parte.' if r.get('ok') else r.get('erro')), None

    if nome == 'liberar':
        with atalhos._como_socket():
            r = atalhos._liberar()
        return r.get('ok'), ('Liberado: ' + r['liberado']) if r.get('ok') else r.get('erro'), None

    if nome in dict(NEUTRAS):
        minhas = _minhas_telas()
        no_ar = bool(minhas) and all(display_state._telas_neutras.get(t) == nome for t in minhas)
        _, recusa = _rodar(handle_blackout, {'active': not no_ar, 'tipo': nome, 'usar_modo': True})
        return recusa is None, recusa, None

    if nome == 'texto':
        _, recusa = _rodar(handle_toggle_lyrics_visibility, {'visible': valor == 'mostrar'})
        return recusa is None, recusa, None

    if nome == 'relogio':
        _, recusa = _rodar(handle_show_image, {'image_url': '/clock'})
        return recusa is None, recusa, None

    if nome == 'recado':
        from blueprints.ticker import handle_set_ticker
        texto = (valor or '').strip()[:200]
        if not texto:
            return False, 'Escreva o recado.', None
        _, recusa = _rodar(handle_set_ticker, {'text': texto, 'targets': _destino_do_recado()})
        return recusa is None, recusa or 'Recado no ar: ' + texto, None

    if nome == 'recado-tirar':
        from blueprints.ticker import handle_stop_ticker
        _, recusa = _rodar(handle_stop_ticker, {'targets': ['public', 'monitor']})
        return recusa is None, recusa, None

    if nome in ('modo', 'assumir'):
        if valor not in dict(MODOS):
            return False, 'Escolha inválida.', None
        r, recusa = _rodar(handle_set_display_mode, {'mode': valor, 'assumir': nome == 'assumir'})
        if recusa:
            return False, recusa, None
        if r and not r.get('ok') and r.get('ocupadas'):
            quem = ', '.join(f"{'o público' if t == 'public' else 'o palco'} está com {d}"
                             for t, d in r['ocupadas'].items())
            return False, quem[0].upper() + quem[1:] + '.', {'assumir': valor}
        return True, None, None

    return False, 'Ação desconhecida.', None
