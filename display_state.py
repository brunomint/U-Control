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

# Modo atual do display: 'lyrics' | 'image' | 'video' | 'blank'
_current_display_mode = 'blank'
# Tela preta ligada no telão público (blackout do /control ou /presenter) —
# guardado pra tela que recarregar/conectar no meio continuar preta.
_blackout_active = False
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

# Modo Público/Monitor atual (control.js: publicOnlyMode/monitorOnlyMode)
# — fonte única de verdade no SERVIDOR, não só no JS do /control.
# _release_kind (blueprints/display.py) lê daqui pra QUALQUER liberação,
# não importa de onde ela vem: pelo card do /control ou pelo banner
# embutido nas próprias páginas (release_banner.js) — esse banner é uma
# aba/página diferente do /control, sem acesso às variáveis JS de lá, e
# achado ao vivo: sem isto, liberar pelo banner sempre ignorava o modo
# ativo (agia como se nenhum modo estivesse ligado), inconsistente com
# liberar pelo card. Atualizado via evento set_display_mode, emitido
# sempre que toggleMonitorMode()/togglePublicMode() mudam de estado.
_active_mode = {'exclude_monitor': False, 'monitor_only': False}

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
