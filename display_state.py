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
# Avisos em slides no ar (blueprints/avisos.py): a lista que o telão roda; _current_display_mode = 'avisos'
_avisos_payload = None
# Telas neutras (preta, branca ou logo da igreja — blackout do /control ou
# /presenter), uma por tela: o operador escolhe se valem no público, no
# monitor de palco ou nos dois. Guardado pra tela que recarregar/conectar
# no meio continuar coberta. None = mostrando o conteúdo normal.
BLACKOUT_TIPOS = ('preta', 'branca', 'logo')
BLACKOUT_TELAS = ('public', 'monitor')
_telas_neutras = {'public': None, 'monitor': None}
# Atalhos pro telão público (o que existia antes de ter uma por tela) —
# handle_blackout mantém em dia; o Stream Deck lê estes
_blackout_active = False
_blackout_tipo = 'preta'


def blackout_payload():
    """O que vai no evento 'blackout': `telas` tem o de cada tela;
    active/tipo são os do público (telas antigas, OBS, /img)."""
    return {'active': _blackout_active, 'tipo': _blackout_tipo, 'telas': dict(_telas_neutras)}
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
#
# Por aparelho (_follows, ver _device_modes abaixo): o Liberar de um não
# deixa o outro acompanhando ao vivo, e "parar" ou trocar de modo só vale
# pra quem fez. Uma ação de outro aparelho só encerra o seu quando muda a
# tela pública, porque aí ela deixa de mostrar o que você acompanhava.

# Letra e Bíblia andam juntas: alternar entre música e leitura no mesmo
# culto (ex.: leitura clicada na ordem do culto em /lyrics, e de volta pra
# música) pedia Liberar a cada troca — e quem não via o "Liberar" achava
# que a página tinha travado. Depois que as duas foram confirmadas, as
# duas vão direto. Imagem nunca entra aqui (proteção do relógio acima).
# Só vale enquanto 'kind' não for None (os resets acima zeram só ele — o
# conjunto fica velho, mas é ignorado e refeito no próximo follow_confirma).
TEXTO = {'lyrics', 'bible'}

# device -> {'kind', 'texto', 'parado'}. 'parado' é o botão "parar" da
# barrinha do telão: até a próxima liberação confirmada, tudo pede Liberar —
# inclusive a troca de seção da letra que já está na tela (ver
# _secao_onde_a_letra_esta em blueprints/display.py).
_follows = {}


def _follow(device=None):
    device = current_device() if device is None else device
    return _follows.setdefault(device, {'kind': None, 'texto': set(), 'parado': False})


def follow_kind(device=None):
    return _follow(device)['kind']


def follow_parado():
    return _follow()['parado']


def follow_label(device=None):
    f = _follow(device)
    return 'Letra e Bíblia' if f['kind'] and f['texto'] == TEXTO else None


def follow_confirma(kind):
    """Liberação confirmada (_release_kind): este aparelho passa a acompanhar
    `kind`. Mudou a tela pública? Quem acompanhava outra coisa nela para."""
    f = _follow()
    f['parado'] = False
    if kind in TEXTO and f['kind'] in TEXTO:
        f['texto'] = f['texto'] | {kind, f['kind']}
    else:
        f['texto'] = {kind} & TEXTO
    f['kind'] = kind
    if device_mode() != 'monitor':
        follow_encerra_quem_ve_o_publico(lambda outro: not follow_inclui(kind, outro))


def follow_inclui(kind, device=None):
    """Esse kind vai direto ao ar (sem pedir Liberar)?"""
    f = _follow(device)
    return f['kind'] is not None and (kind == f['kind'] or kind in f['texto'])


def follow_encerra(device=None):
    _follow(device)['kind'] = None


def follow_para():
    """Botão "parar" da barrinha do telão."""
    f = _follow()
    f['kind'] = None
    f['parado'] = True


def follow_encerra_quem_ve_o_publico(deve_encerrar):
    """Os OUTROS aparelhos acompanhando a tela pública (Só monitor cuida do
    palco e fica de fora) para os quais `deve_encerrar(device)` vale."""
    eu = current_device()
    for device, f in _follows.items():
        if device != eu and f['kind'] and device_mode(device) != 'monitor' and deve_encerrar(device):
            f['kind'] = None


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


def dono_do_palco(eu=None):
    """Outro aparelho conectado agora em "Só monitor" (o id dele) — duas
    pessoas, uma no telão e outra no palco. Só conta quem está conectado:
    um PC que ficou em "Só monitor" e foi embora não prende ninguém."""
    from connections import socketio_clients_by_sid
    eu = current_device() if eu is None else eu
    conectados = {info.get('device') for info in list(socketio_clients_by_sid.values())}
    return next((d for d in conectados if d and d != eu and _device_modes.get(d) == 'monitor'), None)


def palco_de_outro_pc():
    """O palco é de outro aparelho: o "Só público" deste não o arrasta junto."""
    return dono_do_palco() is not None


def assumir_palco():
    """Este aparelho fica com o palco. Quem estava nele vai pra Só público
    (não "Os dois": seguiria mexendo no palco sem querer) e para de
    acompanhar ao vivo. Devolve os aparelhos que perderam o palco."""
    eu = current_device()
    tirados = [d for d, modo in _device_modes.items() if modo == 'monitor' and d != eu]
    for device in tirados:
        set_device_mode('public', device)
        follow_encerra(device)
    set_device_mode('monitor', eu)
    follow_encerra(eu)
    return tirados


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
