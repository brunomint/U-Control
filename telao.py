"""Resumo do telão pra barrinha "No ar / Preparado" (static/js/telao_bar.js)
que aparece em todas as páginas de operador.

Junta num lugar só o que antes ficava espalhado e invisível: o que está
na tela pública, se o monitor de palco está mostrando outra coisa, o que
está preparado esperando Liberar, o modo (público/monitor), o
"acompanhar ao vivo" e a tela preta. Os handlers de display/letra/Bíblia
chamam set_public()/set_monitor() quando mudam o telão e
broadcast_status() depois de qualquer mudança; a barra também lê
GET /api/telao-status ao abrir a página.

Guarda só o tipo + a URL do que está no ar; o rótulo legível é montado
na hora (build_status), então "Letra" sempre mostra a seção atual mesmo
que ela tenha mudado depois."""
import re

import display_state
from extensions import socketio

# {'kind': ..., 'url': ...} — None = ainda nada registrado desde que o
# servidor ligou (build_status cai no último estado salvo no banco)
_public = None
# None = monitor mostrando o mesmo que o público
_monitor = None
_last_bible_ref = None
# Slideshow roda no navegador do /control (timer em control.js); a aba
# avisa o servidor (slideshow_state) e o servidor guarda quem está rodando
# pra mostrar na barra — e esquece se essa aba fechar/cair.
_slideshow = None  # {'sid', 'interval', 'count'}

_FOLLOW_LABELS = {'image': 'Fotos', 'lyrics': 'Letra', 'bible': 'Bíblia'}
_MEDIA_RE = re.compile(r'\.(jpe?g|png|gif|bmp|webp)(\?|$)', re.I)
_VIDEO_RE = re.compile(r'\.(mp4|webm|mov)(\?|$)', re.I)


def kind_of_url(url):
    path = (url or '').split('?')[0]
    if _VIDEO_RE.search(path):
        return 'video'
    if path.startswith('/static/') or _MEDIA_RE.search(path):
        return 'photo'
    if path == '/img':
        return 'gallery'
    if path.startswith('/lyrics/display/public'):
        return 'lyrics'
    if path.startswith('/lyrics/display'):
        return 'cifra'
    if path.startswith('/bible/display'):
        return 'bible'
    if path == '/clock':
        return 'clock'
    if path == '/countdown':
        return 'countdown'
    return 'page' if url else 'blank'


def set_public(kind, url=''):
    global _public
    _public = {'kind': kind, 'url': url or ''}


def set_public_url(url):
    set_public(kind_of_url(url), url)


def set_monitor(kind=None, url=''):
    """kind=None: monitor volta a acompanhar o público."""
    global _monitor
    _monitor = {'kind': kind, 'url': url or ''} if kind else None


def set_monitor_url(url):
    set_monitor(kind_of_url(url), url)


def set_bible_ref(ref):
    global _last_bible_ref
    _last_bible_ref = ref or _last_bible_ref


def _file_name(url):
    from urllib.parse import unquote
    name = unquote((url or '').split('?')[0].rsplit('/', 1)[-1])
    return name or url


def _song_label():
    payload = display_state._last_lyrics_payload or {}
    title = None
    song_id = payload.get('songId') or payload.get('id')
    if song_id is not None:
        try:
            from songs_store import get_song
            song = get_song(int(song_id))
            title = song['title'] if song else None
        except Exception:
            title = None
    section = (payload.get('title') or '').strip()
    parts = [p for p in (title, section) if p]
    return ' — '.join(parts)


def describe(entry):
    """Rótulo legível pra um {'kind','url'} (ou um 'split' com url1/url2)."""
    if not entry:
        return {'kind': 'blank', 'label': 'Nada no ar'}
    kind, url = entry.get('kind'), entry.get('url', '')
    if kind == 'split':
        names = [describe({'kind': kind_of_url(u), 'url': u})['label'].split(' · ')[0]
                 for u in (entry.get('url1'), entry.get('url2')) if u]
        return {'kind': 'split', 'label': 'Tela dividida · ' + ' + '.join(names)}
    if kind == 'lyrics':
        song = _song_label()
        return {'kind': kind, 'label': 'Letra' + (f' · {song}' if song else '')}
    if kind == 'cifra':
        song = _song_label()
        return {'kind': kind, 'label': 'Cifra' + (f' · {song}' if song else '')}
    if kind == 'bible':
        return {'kind': kind, 'label': 'Bíblia' + (f' · {_last_bible_ref}' if _last_bible_ref else '')}
    if kind == 'photo':
        return {'kind': kind, 'label': f'Foto · {_file_name(url)}'}
    if kind == 'gallery':
        last = display_state._last_static_media_url
        return {'kind': kind, 'label': 'Imagem' + (f' · {_file_name(last)}' if last else '')}
    if kind == 'video':
        return {'kind': kind, 'label': f'Vídeo · {_file_name(url)}'}
    if kind == 'clock':
        return {'kind': kind, 'label': 'Relógio'}
    if kind == 'countdown':
        return {'kind': kind, 'label': 'Cronômetro'}
    if kind == 'page':
        short = re.sub(r'^https?://(www\.)?', '', url).rstrip('/')
        return {'kind': kind, 'label': f'Página · {short}'}
    return {'kind': 'blank', 'label': 'Nada no ar'}


def _public_entry():
    if _public:
        return _public
    # Servidor recém-ligado: usa o último estado salvo (show_image/
    # show_video/tela dividida gravam o DisplayState no banco)
    try:
        from models import DisplayState
        state = DisplayState.query.first()
        if state and state.url1:
            return {'kind': kind_of_url(state.url1), 'url': state.url1}
    except Exception:
        pass
    if display_state._current_display_mode == 'lyrics':
        return {'kind': 'lyrics', 'url': '/lyrics/display/public'}
    return None


def public_url():
    """URL que mostra na tela o que o público vê agora — usada pela
    prévia "Telão agora" do /control e pelo Sincronizar monitor."""
    entry = _public_entry()
    if not entry:
        return ''
    kind, url = entry.get('kind'), entry.get('url', '')
    if kind == 'lyrics':
        return '/lyrics/display/public'
    if kind == 'bible':
        return '/bible/display'
    return url


def set_slideshow(sid, running, interval=None, count=None):
    global _slideshow
    if running:
        _slideshow = {'sid': sid, 'interval': interval, 'count': count}
    elif _slideshow and (sid is None or _slideshow['sid'] == sid):
        _slideshow = None


def forget_client(sid):
    """Aba desconectou: se era ela que rodava o slideshow, ele parou."""
    if _slideshow and _slideshow['sid'] == sid:
        set_slideshow(sid, False)
        broadcast_status()


def _extras():
    """Coisas que rodam sozinhas e o operador pode esquecer ligadas."""
    import time
    from blueprints import countdown, ticker
    targets = sorted(ticker._ticker_targets)
    cd = countdown._countdown_state
    return {
        'ticker': {'text': ticker._ticker_text, 'targets': targets} if targets and ticker._ticker_text else None,
        'countdown': {
            'label': cd.get('label') or '',
            'paused': bool(cd.get('paused')),
            'end_ms': cd.get('end_timestamp'),
            'remaining_ms': cd.get('paused_remaining'),
        } if cd.get('active') else None,
        'slideshow': {'interval': _slideshow['interval'], 'count': _slideshow['count']} if _slideshow else None,
        'server_now_ms': time.time() * 1000,
    }


def build_status():
    from models import StagedContent
    mode = display_state._active_mode
    follow = display_state._live_follow_kind
    try:
        staged = [{'kind': s.kind, 'label': s.label} for s in StagedContent.query.all()]
    except Exception:
        staged = []
    return {
        'live': {**describe(_public_entry()), 'url': public_url()},
        'monitor': describe(_monitor) if _monitor else None,
        'staged': staged,
        'mode': 'monitor' if mode.get('monitor_only') else 'public' if mode.get('exclude_monitor') else 'all',
        'follow': follow,
        'follow_label': _FOLLOW_LABELS.get(follow) if follow else None,
        'blackout': bool(display_state._blackout_active),
        **_extras(),
    }


def broadcast_status():
    """Manda o resumo pra todas as barras abertas. Funciona tanto dentro
    de um handler de socket quanto numa rota HTTP."""
    try:
        socketio.emit('telao_status', build_status())
    except Exception:
        import logging
        logging.getLogger('ucontrol').exception('Falha ao transmitir telao_status')


def set_monitor_split(url1, url2):
    global _monitor
    _monitor = {'kind': 'split', 'url1': url1 or '', 'url2': url2 or ''}


def diverge_monitor_from_public():
    """Ação "só público": o monitor fica congelado no que o público
    mostrava até agora (se já não estava mostrando outra coisa)."""
    if _monitor is None:
        prev = _public_entry()
        if prev:
            set_monitor(prev.get('kind'), prev.get('url', ''))
