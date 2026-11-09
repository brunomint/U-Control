"""Quem cuida de cada tela: o público (telão e site) e o palco (monitor).

Cada tela tem um responsável por vez, que é a PESSOA logada (não o
aparelho: o mesmo login em vários aparelhos é a mesma pessoa). O seletor
"O que as ações mudam" do /control diz quais telas este aparelho quer
mexer; escolher uma tela livre fica com ela, e uma tela de outra pessoa
só com "Assumir" (dois toques), que tira a tela dela.

Aparelho novo começa sem tela nenhuma ('none'): antes começava em "Os
dois" e passava por cima de quem estava cuidando de cada tela.

O servidor confere toda ação de operador (extensions.OperatorSocketIO
chama autorizar): ação numa tela de outra pessoa, ou sem tela escolhida,
é recusada e o aparelho recebe 'acao_recusada' com o motivo.

Responsável que fechou todas as abas (nenhum aparelho dele conectado com
aquela tela no modo) deixa a tela livre — ninguém fica preso por um PC
que foi embora. Tudo em memória, como os modos (display_state)."""
import display_state

TELAS = ('public', 'monitor')
NOMES = {'public': 'o público', 'monitor': 'o palco'}

# Eventos que só mexem no palco, não importa o modo
EVENTOS_DO_PALCO = {
    'show_monitor_content', 'show_monitor_pause', 'show_monitor_two_urls', 'show_monitor_video',
}
# Eventos que mexem nas telas do modo deste aparelho
EVENTOS_PELO_MODO = {
    'show_image', 'show_video', 'send_url', 'show_two_urls', 'show_image_zoom',
    'update_lyrics', 'update_bible', 'toggle_lyrics_visibility', 'set_display_bg',
    'blackout', 'stage_content', 'release_staged_content',
    'toggle_video_pause', 'restart_video', 'seek_video',
    'start_countdown', 'pause_countdown', 'resume_countdown', 'reset_countdown',
    'set_ticker', 'stop_ticker', 'apresentacao_cmd',
    'screen_share_start', 'screen_share_stop', 'stop_slideshow',
}

# Tela -> usuário responsável (None = livre)
_donos = {'public': None, 'monitor': None}


def telas_do_modo(modo):
    return {'all': {'public', 'monitor'}, 'public': {'public'},
            'monitor': {'monitor'}}.get(modo, set())


def _usuario():
    try:
        from flask_login import current_user
        return current_user.username if current_user.is_authenticated else ''
    except Exception:
        return ''


def _aparelhos_conectados():
    """{aparelho: usuário} de quem está conectado agora."""
    from connections import socketio_clients_by_sid
    return {i.get('device', ''): i.get('usuario', '')
            for i in list(socketio_clients_by_sid.values()) if i.get('device')}


def dono(tela):
    """Responsável pela tela, ou None se livre. Quem não tem mais nenhum
    aparelho conectado com essa tela no modo perde a tela."""
    usuario = _donos.get(tela)
    if not usuario:
        return None
    ainda = any(u == usuario and tela in telas_do_modo(display_state.device_mode(d))
                for d, u in _aparelhos_conectados().items())
    if not ainda:
        _donos[tela] = None
        return None
    return usuario


def donos():
    return {t: dono(t) for t in TELAS}


def ocupadas_por_outro(telas, usuario=None):
    """{tela: responsável} das telas que estão com outra pessoa."""
    usuario = usuario if usuario is not None else _usuario()
    return {t: d for t in telas for d in [dono(t)] if d and d != usuario}


def escolher_modo(modo, assumir=False):
    """Este aparelho passa a mexer nas telas de `modo` ('all', 'public',
    'monitor' ou 'none'). Tela com outra pessoa: sem `assumir`, nada muda
    e devolve {'ok': False, 'ocupadas': {...}}; com `assumir`, fica com
    ela e os aparelhos da outra pessoa deixam de mexer nela."""
    if modo not in ('all', 'public', 'monitor', 'none'):
        modo = 'none'
    usuario = _usuario()
    telas = telas_do_modo(modo)
    ocupadas = ocupadas_por_outro(telas, usuario)
    if ocupadas and not assumir:
        return {'ok': False, 'ocupadas': ocupadas}
    tirados = []
    if ocupadas:
        tirados = _tirar_de_quem_tinha(set(ocupadas), usuario)
    for t in telas:
        _donos[t] = usuario
    display_state.set_device_mode(modo)
    display_state.follow_encerra()
    # Tela que este usuário largou e nenhum outro aparelho dele usa: fica livre
    for t in TELAS:
        if t not in telas and _donos.get(t) == usuario:
            dono(t)
    return {'ok': True, 'tirados': tirados}


def _tirar_de_quem_tinha(telas, usuario):
    """Os aparelhos de outras pessoas deixam de mexer em `telas`:
    "Os dois" vira a outra tela, e quem só tinha essa fica sem nenhuma.
    Devolve os aparelhos que mudaram."""
    tirados = []
    for device, modo in list(display_state._device_modes.items()):
        if device == display_state.current_device():
            continue
        if _aparelhos_conectados().get(device) == usuario:
            continue
        resto = telas_do_modo(modo) - telas
        if resto == telas_do_modo(modo):
            continue
        novo = 'public' if resto == {'public'} else 'monitor' if resto == {'monitor'} else 'none'
        display_state.set_device_mode(novo, device)
        display_state.follow_encerra(device)
        tirados.append(device)
    return tirados


def ajustar_ao_conectar(device, usuario):
    """Aparelho que conecta com um modo guardado de tela que agora está
    com outra pessoa (ele caiu, a tela ficou livre e alguém pegou): perde
    essa tela, em vez de passar a mexer junto com o novo responsável."""
    if not device:
        return
    modo = display_state.device_mode(device)
    perdeu = {t for t in telas_do_modo(modo) if dono(t) and dono(t) != usuario}
    if not perdeu:
        return
    resto = telas_do_modo(modo) - perdeu
    novo = 'public' if resto == {'public'} else 'monitor' if resto == {'monitor'} else 'none'
    display_state.set_device_mode(novo, device)
    display_state.follow_encerra(device)


def autorizar(evento, args):
    """Pode este aparelho mandar `evento`? Devolve None se pode, ou o
    motivo (texto) se não pode."""
    from i18n import gettext as _
    if evento in EVENTOS_DO_PALCO:
        telas = {'monitor'}
    elif evento in EVENTOS_PELO_MODO:
        dados = args[0] if args and isinstance(args[0], dict) else {}
        if evento == 'blackout' and not dados.get('usar_modo'):
            # Botões com telas fixas (Stream Deck ?telas=); sem nenhuma, o público
            telas = set(dados.get('telas') or ['public']) & set(TELAS) or {'public'}
        else:
            telas = telas_do_modo(display_state.device_mode())
        if not telas:
            return _('Escolha antes qual tela você controla: público, palco ou os dois.')
    else:
        return None
    ocupadas = ocupadas_por_outro(telas)
    if ocupadas:
        t, d = next(iter(ocupadas.items()))
        return _('{tela} está com {nome}. Para mexer, toque em Assumir.',
                 tela=_(NOMES[t]).capitalize(), nome=d)
    # Tela livre que está no modo deste aparelho: quem mexe fica com ela
    meu_modo = telas_do_modo(display_state.device_mode())
    for t in telas & meu_modo:
        if not _donos.get(t):
            _donos[t] = _usuario()
    return None
