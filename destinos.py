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

A PASSAGEM (música, slides, Bíblia) é de todos: qualquer pessoa logada
escolhe e avança, sem assumir tela — vale o último toque. Cada tela tem
"Seguir a passagem" (_seguindo), que só o responsável dela liga/desliga:
seguindo, a passagem aparece nela (no palco a letra vira cifra; a Bíblia
não vai pro palco); sem seguir, ela fica com o que o dono pôs. O dono pôr
outra coisa (relógio, URL, Tela do PC, cronômetro, tela preta, vídeo só
no palco) desliga o seguir da tela dele. Vídeo é passagem, como a letra.

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
    'start_countdown', 'pause_countdown', 'resume_countdown', 'reset_countdown',
    'set_ticker', 'stop_ticker', 'apresentacao_cmd',
    'screen_share_start', 'screen_share_stop', 'stop_slideshow',
}

# Tela -> usuário responsável (None = livre)
_donos = {'public': None, 'monitor': None}
# Tela segue a passagem? (começa seguindo, como antes todo mundo era "Os dois")
_seguindo = {'public': True, 'monitor': True}
# Último conteúdo da passagem que foi ao ar: {'kind', 'payload'}
_passagem = None
# Palco com a Bíblia posta pelo dono: acompanha só os versículos (a música
# não tira a Bíblia de lá; a cifra volta quando o dono põe a letra)
_palco_na_biblia = False
# Último item clicado de cada tipo, mesmo que tenha ficado só preparado:
# é o que a tela mostra quando o dono põe aquele tipo nela
_ultimo_clicado = {}

# Eventos da passagem: qualquer pessoa logada manda (ver _telas_da_passagem)
EVENTOS_DA_PASSAGEM = {'stage_content', 'release_staged_content', 'update_lyrics',
                       'update_bible', 'show_image', 'show_image_zoom', 'apresentacao_cmd',
                       'show_video', 'toggle_video_pause', 'restart_video', 'seek_video'}
KINDS_DA_PASSAGEM = {'lyrics', 'bible', 'image', 'video'}
# O dono pôr isto na tela dele desliga o "seguir" dela
EVENTOS_QUE_DESLIGAM_SEGUIR = {'show_monitor_video', 'send_url', 'show_two_urls',
                               'show_monitor_two_urls', 'start_countdown', 'screen_share_start'}
# Telas de conteúdo da passagem (não desligam o seguir ao serem abertas)
_ROTAS_DA_PASSAGEM = ('/lyrics/display', '/bible/display', '/img')


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


def _e_foto(url):
    import telao
    return telao.kind_of_url(url) == 'photo'


def _kind_da_passagem(evento, dados):
    """'lyrics' | 'bible' | 'image' | 'slide' se o evento é da passagem."""
    if evento in ('stage_content', 'release_staged_content'):
        kind = dados.get('kind')
        return kind if kind in KINDS_DA_PASSAGEM else None
    if evento == 'update_lyrics':
        return 'lyrics'
    if evento == 'update_bible':
        return 'bible'
    if evento == 'show_image':
        return 'image' if _e_foto(dados.get('image_url', '')) else None
    if evento == 'show_video':
        return 'video'
    if evento in ('toggle_video_pause', 'restart_video', 'seek_video'):
        return 'video'
    if evento in ('show_image_zoom', 'apresentacao_cmd'):
        return 'slide'
    return None


def _modo_das_telas(telas):
    return 'all' if telas == {'public', 'monitor'} else next(iter(telas)) if telas else 'none'


def _telas_da_passagem(kind, usuario):
    """Onde um passo da passagem aparece: nas telas deste aparelho que são
    dele (ou livres) e nas que estão seguindo. Bíblia não vai pro palco
    por seguir (os músicos ficam na cifra)."""
    minhas = {t for t in telas_do_modo(display_state.device_mode()) if dono(t) in (None, usuario)}
    seguem = {t for t in TELAS if _seguindo.get(t)}
    if (kind == 'bible') != _palco_na_biblia:
        seguem.discard('monitor')   # palco na cifra não vira versículo, e vice-versa
    return minhas, minhas | seguem


def lembrar_passagem(kind, payload):
    """Conteúdo da passagem que foi ao ar (blueprints/display.py): é o que
    uma tela mostra ao voltar a seguir."""
    global _passagem
    if kind in KINDS_DA_PASSAGEM and payload:
        _passagem = {'kind': kind, 'payload': payload}


def seguir(tela, ligado):
    """Liga/desliga o "Seguir a passagem" de `tela`. Só o responsável dela
    (ou qualquer um, se a tela está livre). Devolve o responsável que
    impediu, ou None."""
    d = dono(tela)
    if d and d != _usuario():
        return d
    _seguindo[tela] = bool(ligado)
    return None


def _desligar_seguir_das(telas):
    for t in telas:
        _seguindo[t] = False


# Tela que a tela preta tirou da passagem: volta a seguir quando ela sai
_seguia_antes_do_preto = {'public': False, 'monitor': False}


def _rota_kinds(url):
    """Que conteúdos da passagem esta tela mostra (letra, Bíblia, foto/vídeo)."""
    u = (url or '').split('?')[0]
    if u.startswith('/lyrics/display'):
        return {'lyrics'}
    if u.startswith('/bible/display'):
        return {'bible'}
    if u.startswith('/img'):
        return {'image', 'video'}
    return set()


def _voltar_a_seguir(telas, kinds=None):
    """O dono pôs de volta na tela dele algo da passagem: ela acompanha de
    novo quem conduz e já pega o passo atual (se é do mesmo tipo — letra
    no palco não vira vídeo). O guarda (extensions.py) chama
    retomar_passagem depois da ação."""
    global _passagem
    from flask import g
    for t in telas:
        _seguindo[t] = True
    if not (_passagem and (kinds is None or _passagem['kind'] in kinds)):
        # O passo atual é de outro tipo: mostra o último clicado deste tipo
        clicado = next((_ultimo_clicado[k] for k in sorted(kinds or ()) if k in _ultimo_clicado), None)
        if not clicado:
            return
        _passagem = clicado
    g.uc_retomar = set(g.get('uc_retomar') or ()) | set(telas)


def retomar_passagem():
    """Depois da ação do dono: as telas que voltaram a seguir mostram o
    passo atual da passagem (blueprints/display.py)."""
    from flask import g
    telas = g.pop('uc_retomar', None)
    if not telas:
        return
    from blueprints.display import _mostrar_passagem_em
    for t in sorted(telas):
        _mostrar_passagem_em(t)


def de_fora_na_passagem(handler):
    """`handler` é a própria ação da passagem que chegou do navegador
    (não uma chamada por dentro, que já vem com as telas certas)? Aí ele
    manda só pras telas que a passagem alcança (g.uc_modo_passagem)."""
    from flask import g
    return (bool(g.get('uc_modo_passagem'))
            and g.get('uc_evento_de_fora') is getattr(handler, '__wrapped__', handler))


def _modo_passagem(modo):
    """Modo efetivo deste pedido (display_state.device_mode lê daqui)."""
    from flask import g
    g.uc_modo_passagem = modo


def autorizar(evento, args):
    """Pode este aparelho mandar `evento`? Devolve None se pode, ou o
    motivo (texto) se não pode."""
    from i18n import gettext as _
    dados = args[0] if args and isinstance(args[0], dict) else {}
    kind = _kind_da_passagem(evento, dados)
    if kind:
        if kind == 'slide':
            return None   # zoom e apresentação: só seguem o que já está nas telas
        if evento == 'stage_content' and dados.get('payload'):
            _ultimo_clicado[kind] = {'kind': kind, 'payload': dados['payload']}
        usuario = _usuario()
        minhas, telas = _telas_da_passagem(kind, usuario)
        if not telas:
            return _('Nenhuma tela está mostrando a letra agora: quem cuida das telas pôs outra coisa nelas.')
        for t in minhas:
            if not _donos.get(t):
                _donos[t] = usuario
        _modo_passagem(_modo_das_telas(telas))
        # Estes já vão direto ao ar (stage/release se lembram em display.py)
        if evento == 'update_lyrics':
            lembrar_passagem('lyrics', dados)
        elif evento == 'update_bible':
            lembrar_passagem('bible', dados)
        elif evento == 'show_image':
            lembrar_passagem('image', {'image_url': dados.get('image_url', '')})
        elif evento == 'show_video':
            lembrar_passagem('video', {'video_url': dados.get('video_url', '')})
        return None
    if evento in EVENTOS_DO_PALCO:
        telas = {'monitor'}
    elif evento in EVENTOS_PELO_MODO:
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
    # Outra coisa na tela (vídeo, relógio, URL…): ela deixa de seguir a passagem
    url = dados.get('url') or dados.get('image_url') or ''
    da_passagem = lambda u: bool(u) and u.split('?')[0].startswith(_ROTAS_DA_PASSAGEM)
    # Tela dividida com letra/foto/Bíblia num lado: a passagem segue nesse lado
    dividida_com_passagem = (evento in ('show_two_urls', 'show_monitor_two_urls')
                             and (da_passagem(dados.get('url1')) or da_passagem(dados.get('url2'))))
    global _palco_na_biblia
    if evento == 'show_image' and dados.get('exclude_monitor'):
        telas = telas - {'monitor'}   # "Só público": o palco não muda
    if 'monitor' in telas and (evento in EVENTOS_QUE_DESLIGAM_SEGUIR
                               or evento in ('show_monitor_content', 'show_image')):
        # Bíblia no palco: ele passa a acompanhar só os versículos
        _palco_na_biblia = (evento in ('show_monitor_content', 'show_image')
                            and url.split('?')[0].startswith('/bible/display'))
    if evento == 'blackout':
        if dados.get('active', True):
            for t in telas:
                if _seguindo.get(t):
                    _seguia_antes_do_preto[t] = True
            _desligar_seguir_das(telas)
        else:
            # Saiu a tela preta: a tela volta a seguir se seguia antes dela
            voltam = {t for t in telas if _seguia_antes_do_preto.get(t)}
            for t in telas:
                _seguia_antes_do_preto[t] = False
            if voltam:
                _voltar_a_seguir(voltam)
    elif ((evento in EVENTOS_QUE_DESLIGAM_SEGUIR and not dividida_com_passagem)
            or (evento in ('show_monitor_content', 'show_image') and url and not da_passagem(url))):
        _desligar_seguir_das(telas)
    elif evento in ('show_monitor_content', 'show_image') and da_passagem(url):
        # O dono pôs letra/Bíblia/foto na tela dele: ela acompanha quem conduz
        _voltar_a_seguir(telas, _rota_kinds(url))
    return None
