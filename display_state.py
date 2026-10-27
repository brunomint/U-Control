"""Estado em memória do display ao vivo — compartilhado pelos handlers de
imagem/vídeo/monitor (blueprints/display.py) e pelo handler update_lyrics
(blueprints/lyrics.py). Núcleo mais entrelaçado do projeto: essas
variáveis são lidas e escritas por handlers de áreas diferentes ao mesmo
tempo, por isso vivem num módulo à parte em vez de dentro de qualquer
blueprint específico — mesmo padrão do connections.py."""
import time

# Cache simples em memória para reduzir queries no banco
_display_state_cache = {'data': None, 'timestamp': 0}
_cache_ttl = 5  # Cache válido por 5 segundos

# URL da última imagem/vídeo estático clicado — separado do estado do display
_last_static_media_url = None

# Último payload de update_lyrics recebido (para display_public carregar ao abrir)
_last_lyrics_payload = None
# Último versículo enviado ao telão (update_bible) — /bible/display busca
# ao abrir (/api/bible/current); sem isto, a prévia do /control, o monitor
# ou uma tela recarregada ficavam em "Aguardando versículos..." com o
# versículo no ar
_last_bible_payload = None
# Zoom da foto que está na tela ({image_url, zoom, origin, pan}) — as
# telas (/img, /monitor, tela pública) pedem ao abrir/recarregar ou ao
# receber a mesma foto de novo (antes o zoom se perdia). Some quando
# outra foto vai pra tela.
_image_zoom = None
# Versículo liberado só pro monitor ("Só monitor"): a /bible/display de
# dentro do monitor abre nele (/api/bible/current?host=monitor) sem mudar o
# que o público mostra ao recarregar
_last_bible_payload_monitor = None

# Modo atual do display: 'lyrics' | 'image' | 'video' | 'blank'
_current_display_mode = 'blank'
# Tela preta ligada no telão público (blackout do /control ou /presenter) —
# guardado pra tela que recarregar/conectar no meio continuar preta.
_blackout_active = False
# Qual tela neutra: 'preta', 'branca' ou 'logo' (logo da igreja)
BLACKOUT_TIPOS = ('preta', 'branca', 'logo')
_blackout_tipo = 'preta'
_last_image_url = None

# "Live-follow" do preparar/liberar (ver blueprints/display.py,
# handle_stage_content/_release_kind): qual StagedContent.kind foi
# CONFIRMADO ao vivo por último através do próprio sistema de
# preparar/liberar — 'lyrics' | 'bible' | 'image' | None. Enquanto um
# stage_content chegar com esse MESMO kind, vai direto ao ar sem pedir
# Liberar de novo (navegar dentro do que já está confirmado não deveria
# exigir confirmação a cada clique). Um kind DIFERENTE ainda exige
# Liberar explícito, o que reseta este valor pro novo kind.
#
# Só é atualizado por liberações que passam pelo preparar/liberar —
# ações nativas do /control (relógio, galeria do próprio /control, URL)
# NÃO tocam nisto de propósito: relógio também é kind='image' por baixo
# (show_image), e se contasse como confirmação, o incidente que motivou
# essa funcionalidade (slideshow esquecido sobrescrevendo o relógio)
# voltaria a ser possível — uma aba de foto esquecida rodando depois do
# relógio ainda precisa de confirmação, porque o relógio não "confirma"
# o tipo imagem.
#
# Mas ações nativas do /control ENCERRAM o live-follow quando trocam o
# telão pra outro tipo (ver _end_live_follow_unless em
# blueprints/display.py): antes, depois de liberar uma foto do
# /presenter, colocar o relógio ou a letra no telão não bastava — a
# próxima foto clicada no presenter entrava por cima na hora.
_live_follow_kind = None

# Letra e Bíblia andam juntas: alternar entre música e leitura no mesmo
# culto (ex.: leitura clicada na ordem do culto em /lyrics, e de volta pra
# música) pedia Liberar a cada troca — e quem não via o "Liberar" achava
# que a página tinha travado. Depois que as duas foram confirmadas, as
# duas vão direto. Imagem nunca entra aqui (proteção do relógio acima).
# Só vale enquanto _live_follow_kind não for None (os resets acima zeram
# só ele — o conjunto fica velho, mas é ignorado e refeito no próximo
# follow_confirma).
TEXTO = {'lyrics', 'bible'}
_live_follow_texto = set()


# Botão "parar" da barrinha do telão: até a próxima liberação confirmada,
# tudo pede Liberar — inclusive a troca de seção da letra que já está na
# tela (ver _secao_onde_a_letra_esta em blueprints/display.py).
_follow_parado = False


def follow_confirma(kind):
    """Liberação confirmada (_release_kind): passa a acompanhar `kind`."""
    global _live_follow_kind, _live_follow_texto, _follow_parado
    _follow_parado = False
    if kind in TEXTO and _live_follow_kind in TEXTO:
        _live_follow_texto = _live_follow_texto | {kind, _live_follow_kind}
    else:
        _live_follow_texto = {kind} & TEXTO
    _live_follow_kind = kind


def follow_inclui(kind):
    """Esse kind vai direto ao ar (sem pedir Liberar)?"""
    return _live_follow_kind is not None and (kind == _live_follow_kind or kind in _live_follow_texto)

# Modo Público/Monitor de cada máquina (control.js: publicOnlyMode/
# monitorOnlyMode) — guardado no SERVIDOR, não só no JS do /control.
# _release_kind (blueprints/display.py) lê daqui pra QUALQUER liberação,
# não importa de onde ela vem: pelo card do /control ou pelo banner
# embutido nas próprias páginas (release_banner.js) — esse banner é uma
# aba/página diferente do /control, sem acesso às variáveis JS de lá.
#
# Por máquina, não um só: dois /control em PCs diferentes, um cuidando do
# público ("Só público") e outro do monitor de palco ("Só monitor").
# Com um modo único, trocar num PC trocava no outro, e a letra mandada
# pelo PC do público ia parar no monitor. A máquina é o cookie uc_device
# (ver main.py), que todas as abas do mesmo navegador mandam — inclusive
# no socket. Máquina sem modo guardado = 'all' (Os dois).
_device_modes = {}


def current_device():
    """Id da máquina de quem fez o pedido (cookie uc_device). Fora de
    um pedido ou sem cookie: '' — as máquinas sem cookie dividem o mesmo
    modo (string, não None, pra o dicionário virar JSON sem tropeçar)."""
    try:
        from flask import request
        return request.cookies.get('uc_device') or ''
    except RuntimeError:
        return ''


def device_mode(device=None):
    """'all' | 'public' | 'monitor' da máquina (padrão: quem pediu)."""
    return _device_modes.get(device if device is not None else current_device(), 'all')


def set_device_mode(mode, device=None):
    device = device if device is not None else current_device()
    if mode in ('public', 'monitor'):
        _device_modes[device] = mode
    else:
        _device_modes.pop(device, None)

# Estado de reprodução de vídeo para sincronização entre clientes /img.
# Quando uma nova janela /img conecta, ela consulta este estado para começar
# o vídeo na mesma posição em que ele está tocando nas outras janelas.
#   url:           URL do vídeo atualmente em reprodução (ou None)
#   started_at:    timestamp Unix de quando o vídeo começou OU foi retomado
#   position_offset: posição (segundos) no vídeo no momento de started_at
#                  (0 quando começa do zero; X quando retoma após pausa)
#   paused:        True se está pausado
_video_state = {
    'url': None,
    'started_at': 0.0,
    'position_offset': 0.0,
    'paused': False,
}


def _video_current_position():
    """Retorna a posição (em segundos) atual do vídeo, ou 0 se nada tocando."""
    if not _video_state['url']:
        return 0.0
    if _video_state['paused']:
        return _video_state['position_offset']
    return _video_state['position_offset'] + (time.time() - _video_state['started_at'])
