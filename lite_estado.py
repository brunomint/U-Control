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
import time

# Tela da versão simples -> tela de verdade que ela acompanha. 'vocal' é o
# palco só com a letra (sem acordes); 'cronometro' é o tempo do pregador.
TELAS = {'publico': 'public', 'monitor': 'monitor', 'vocal': 'monitor', 'cronometro': 'monitor'}


def _linhas_da_letra(texto, publico=True):
    """Letra para o público: sem cifra, sem notas de palco (//), sem os
    "___" de alinhamento, sem os sinais de repetição (/: :/) e sem linhas
    vazias — como display_public.js."""
    from chord_lines import is_chord_line
    from letra_formato import limpar, sem_divisao, sem_repeticao
    linhas = []
    texto = sem_divisao(limpar(texto or '')) or ''
    if publico:   # no palco (vocais) o "/:" fica: é para quem canta
        texto = sem_repeticao(texto) or ''
    for linha in texto.split('\n'):
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


def _letra(payload, como_cifra, publico=True):
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
        e['linhas'] = _linhas_da_letra(payload.get('text'), publico)
        if publico and not e['linhas']:
            # Parte sem letra (introdução, solo): capa com título e autor, como o telão
            e['modo'] = 'capa'
            e['autor'] = payload.get('autor') or ''
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


def _cronometro():
    """Cronômetro (blueprints/countdown.py) ou None se não está rodando.
    `fim` e `restante` em ms; o aparelho conta sozinho com a hora do servidor."""
    from blueprints.countdown import _countdown_state as c
    if not c.get('active'):
        return None
    e = {'modo': 'cronometro', 'titulo': c.get('label') or '', 'pausado': bool(c.get('paused'))}
    if c.get('paused'):
        e['restante'] = int(c.get('paused_remaining') or 0)
    else:
        e['fim'] = int(c.get('end_timestamp') or 0)
    return e


def _conteudo(tela, so_letra=False):
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
        # Palco: a letra vai como cifra, a não ser que tenham pedido a letra sem
        # cifra ou que seja a tela dos vocais (só letra)
        como_cifra = (tela == 'monitor' and not so_letra
                      and not (destinos._palco_sem_cifra and tipo == 'lyrics'))
        return _letra(payload, como_cifra, publico=tela == 'public')
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
    if tipo == 'countdown':
        return _cronometro() or {'modo': 'vazio'}
    if tipo == 'blank':
        return {'modo': 'vazio'}
    rotulo = telao.describe({'kind': tipo, 'url': url}).get('label', '')
    return {'modo': 'outro', 'texto': rotulo.split(' · ')[0] if tipo == 'page' else rotulo}


def estado(tela):
    """tela: uma das TELAS. Devolve o dict com `rev` (muda só quando o
    conteúdo muda) e `agora` (hora do servidor, em ms: o aparelho antigo
    pode estar com o relógio errado)."""
    import display_state
    from blueprints import ticker
    chave = TELAS.get(tela, 'public')
    if tela == 'cronometro':
        e = _cronometro() or {'modo': 'relogio'}
    else:
        neutra = display_state._telas_neutras.get(chave)
        if neutra:
            e = {'modo': 'neutra', 'tipo': neutra}
            if neutra == 'logo':
                e['url'] = '/logo-igreja.png'
        else:
            e = _conteudo(chave, so_letra=tela == 'vocal')
        # Letreiro (aviso/recado) da tela: o recado para a banda vai ao palco
        if ticker._por_tela.get(chave):
            e['letreiro'] = ticker._por_tela[chave]
    e['tela'] = tela
    texto = json.dumps(e, sort_keys=True, ensure_ascii=False)
    e['rev'] = hashlib.sha1(texto.encode('utf-8')).hexdigest()[:12]
    e['agora'] = agora()
    return e


def agora():
    return int(time.time() * 1000)
