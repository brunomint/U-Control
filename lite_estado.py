"""O que cada tela (público ou monitor de palco) mostra agora, num JSON
pequeno para a versão simples (blueprints/lite.py, docs/PLANO-LITE.md).

Não guarda nada próprio: lê o mesmo estado que as telas normais usam
(telao._public/_monitor, display_state, destinos) e aplica as mesmas
regras — o monitor segue o público quando não tem conteúdo próprio e
mostra a letra como cifra; tela preta/branca/logo vale por tela.

`rev` muda só quando o conteúdo muda: o aparelho pergunta a cada pouco e
só redesenha quando ela é outra."""
import hashlib
import json
import re

TELAS = {'publico': 'public', 'monitor': 'monitor'}


def _linhas_da_letra(texto):
    """Letra para o público: sem cifra, sem notas de palco (//), sem os
    "___" de alinhamento e sem linhas vazias — como display_public.js."""
    from chord_lines import is_chord_line
    from letra_formato import limpar, sem_divisao
    linhas = []
    for linha in (sem_divisao(limpar(texto or '')) or '').split('\n'):
        if is_chord_line(linha) or linha.strip().startswith('//'):
            continue
        linha = re.sub(r'_+', '', linha)
        if linha.strip():
            linhas.append(linha.strip())
    return linhas


def _cifra_html(texto):
    from chord_lines import render_cifra_html
    from letra_formato import limpar, sem_divisao
    return render_cifra_html(sem_divisao(limpar(texto or '')) or '')


def _titulo_da_musica(payload):
    try:
        from songs_store import get_song
        song = get_song(int(payload.get('songId')))
        return song['title'] if song else ''
    except (TypeError, ValueError):
        return ''


def _letra(payload, como_cifra):
    tipo = payload.get('type') or 'text'
    e = {
        'modo': 'cifra' if como_cifra else 'letra',
        'musica': _titulo_da_musica(payload),
        'secao': payload.get('title') or '',
    }
    if tipo == 'sheet':
        e['aviso'] = 'Partitura: só aparece na tela normal.'
        return e
    if como_cifra:
        e['html'] = _cifra_html(payload.get('text'))
        if payload.get('nextTitle'):
            e['a_seguir'] = payload['nextTitle']
    else:
        e['linhas'] = _linhas_da_letra(payload.get('text'))
    if tipo == 'mixed':
        e['aviso'] = 'Esta parte tem partitura: só aparece na tela normal.'
    return e


def _biblia(payload):
    if not payload:
        return {'modo': 'vazio'}
    versos = payload.get('verses')
    if isinstance(versos, list) and versos:
        texto = ' '.join(f"{v.get('num', '')} {v.get('text', '')}".strip() for v in versos if isinstance(v, dict))
    else:
        texto = str(payload.get('text') or '')
    return {'modo': 'biblia', 'referencia': payload.get('reference') or '',
            'versao': payload.get('version') or '', 'texto': texto}


def _letra_visivel():
    try:
        from models import LyricsState
        state = LyricsState.query.first()
        return not (state and state.visible is False)
    except Exception:
        return True


def _conteudo(tela):
    import destinos
    import display_state
    import telao
    from blueprints import screen_share

    if screen_share.mostra_em(tela):
        return {'modo': 'outro', 'texto': 'Tela do computador'}

    if tela == 'monitor':
        entrada = telao._monitor or telao._public_entry()
        proprio = telao._monitor is not None
    else:
        if display_state._current_display_mode == 'avisos' and display_state._avisos_payload:
            slides = [str(s) for s in (display_state._avisos_payload.get('slides') or []) if str(s).strip()]
            return {'modo': 'avisos', 'avisos': slides,
                    'segundos': display_state._avisos_payload.get('segundos') or 8}
        entrada = telao._public_entry()
        proprio = False
    if not entrada:
        return {'modo': 'vazio'}

    tipo = entrada.get('kind')
    url = entrada.get('url', '')
    if tipo == 'split':
        # Tela dividida (só no monitor): a versão simples mostra um lado só,
        # de preferência a cifra
        lados = [entrada.get('url1', ''), entrada.get('url2', '')]
        url = next((u for u in lados if telao.kind_of_url(u) in ('cifra', 'lyrics')), lados[0] or lados[1])
        tipo = telao.kind_of_url(url)

    if tipo in ('lyrics', 'cifra'):
        payload = display_state._last_lyrics_payload
        if tela == 'monitor' and proprio and getattr(display_state, '_last_lyrics_payload_monitor', None):
            payload = display_state._last_lyrics_payload_monitor
        if not payload:
            return {'modo': 'vazio'}
        if tela == 'public' and not _letra_visivel():
            return {'modo': 'vazio'}
        # Palco: a letra vai como cifra, a não ser que tenham pedido a letra sem cifra
        como_cifra = tela == 'monitor' and not (destinos._palco_sem_cifra and tipo == 'lyrics')
        return _letra(payload, como_cifra)
    if tipo == 'bible':
        payload = display_state._last_bible_payload
        if tela == 'monitor' and display_state._last_bible_payload_monitor:
            payload = display_state._last_bible_payload_monitor
        return _biblia(payload)
    if tipo == 'photo':
        return {'modo': 'imagem', 'url': url}
    if tipo == 'gallery':
        foto = display_state._last_static_media_url
        if foto and telao.kind_of_url(foto) == 'photo':
            return {'modo': 'imagem', 'url': foto}
        return {'modo': 'outro', 'texto': 'Vídeo no telão' if foto else ''}
    if tipo == 'clock':
        return {'modo': 'relogio'}
    if tipo == 'blank':
        return {'modo': 'vazio'}
    rotulo = telao.describe({'kind': tipo, 'url': url}).get('label', '')
    return {'modo': 'outro', 'texto': rotulo.split(' · ')[0] if tipo == 'page' else rotulo}


def estado(tela):
    """tela: 'publico' ou 'monitor'. Devolve o dict com `rev`."""
    import display_state
    chave = TELAS.get(tela, 'public')
    neutra = display_state._telas_neutras.get(chave)
    if neutra:
        e = {'modo': 'neutra', 'tipo': neutra}
        if neutra == 'logo':
            e['url'] = '/logo-igreja.png'
    else:
        e = _conteudo(chave)
    e['tela'] = tela
    texto = json.dumps(e, sort_keys=True, ensure_ascii=False)
    e['rev'] = hashlib.sha1(texto.encode('utf-8')).hexdigest()[:12]
    return e
