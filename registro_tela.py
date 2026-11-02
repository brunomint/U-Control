"""Registro do que apareceu na tela do público, troca por troca, com hora exata.

Serve pra juntar a tela com o áudio gravado do culto depois (o site da igreja
guarda o áudio). Por isso cada linha guarda o texto exibido, não só a música:
se a letra for editada depois, o culto antigo continua como foi.

Não confundir com display_log.py (histórico por música, sem texto, 2000
linhas) nem com registro_acoes.py (quem fez o quê). telao.set_public() é o
ponto único por onde passa tudo que vai ao público; tela preta e "Esconder"
não passam por ali e chamam tela_neutra()/texto_visivel().

O tema vai copiado em cada linha pelo mesmo motivo: mudar um tema depois não
altera os cultos antigos. Fundo em imagem ou vídeo fica só pelo nome do arquivo.

Só observa: se falhar, o telão segue normalmente. A gravação usa uma conexão
própria pra não mexer na sessão do handler que chamou."""
import json
import logging
import time

import display_state
import letra_formato
import temas_store
from chord_lines import is_chord_line
from extensions import db
from models import TelaEvento

logger = logging.getLogger('ucontrol')

DIAS_GUARDADOS = 180
SEGUNDOS_ENTRE_LIMPEZAS = 3600
MAX_TITULO = 300
MAX_TEXTO = 8000

_TIPOS = {'lyrics': 'letra', 'bible': 'biblia', 'video': 'video', 'photo': 'foto',
          'gallery': 'foto', 'avisos': 'avisos', 'blank': 'vazio'}
_COM_TEXTO = ('letra', 'biblia')

_conteudo = None      # o que está no ar, sem contar tela preta e "Esconder"
_oculto = False       # botão "Esconder" (só vale pra letra e Bíblia)
_ultimo_gravado = None
_proxima_limpeza = 0


def _texto_da_letra(dados):
    texto = letra_formato.sem_divisao(dados.get('textoPublico') or dados.get('text') or '')
    linhas = [linha for linha in texto.split('\n') if not is_chord_line(linha)]
    return letra_formato.limpar('\n'.join(linhas)).strip()


def _texto_da_biblia(dados):
    versos = dados.get('verses')
    if not isinstance(versos, list):
        return (dados.get('text') or '').strip()
    linhas = [f"{v.get('num')} {v.get('text')}" for v in versos if isinstance(v, dict)]
    return '\n'.join(linhas)


def _texto_dos_avisos(dados):
    slides = dados.get('slides') or []
    return '\n\n'.join(s.get('texto') or s.get('text') or '' if isinstance(s, dict) else str(s)
                       for s in slides)


def _tema_em_texto(tema):
    return json.dumps(tema, ensure_ascii=False, sort_keys=True) if tema else ''


def _descrever(kind, url):
    import telao
    tipo = _TIPOS.get(kind, 'outro')
    if tipo == 'letra':
        dados = display_state._last_lyrics_payload or {}
        return tipo, telao._song_label(), _texto_da_letra(dados), _tema_em_texto(dados.get('tema'))
    if tipo == 'biblia':
        dados = display_state._last_bible_payload or {}
        return tipo, dados.get('reference') or '', _texto_da_biblia(dados), _tema_em_texto(temas_store.tema_da_biblia())
    if tipo == 'avisos':
        dados = display_state._avisos_payload or {}
        return tipo, '', _texto_dos_avisos(dados), _tema_em_texto(dados.get('tema'))
    if tipo == 'vazio':
        return tipo, '', '', ''
    return tipo, telao._file_name(url) or '', '', ''


def _no_ar():
    """O que o público vê agora, já com tela preta e "Esconder" aplicados."""
    neutra = display_state._telas_neutras.get('public')
    if neutra:
        return 'neutra', neutra, '', ''
    if _conteudo and _oculto and _conteudo[0] in _COM_TEXTO:
        return 'oculto', _conteudo[1], '', _conteudo[3]
    return _conteudo


def _limpar_antigos(conexao, agora_ms):
    global _proxima_limpeza
    if agora_ms < _proxima_limpeza:
        return
    _proxima_limpeza = agora_ms + SEGUNDOS_ENTRE_LIMPEZAS * 1000
    limite = agora_ms - DIAS_GUARDADOS * 86400 * 1000
    conexao.execute(TelaEvento.__table__.delete().where(TelaEvento.ts_ms < limite))


def _gravar():
    global _ultimo_gravado
    evento = _no_ar()
    if evento is None or evento == _ultimo_gravado:
        return   # reenvio do mesmo conteúdo não é troca de tela
    tipo, titulo, texto, tema = evento
    agora_ms = int(time.time() * 1000)   # antes do banco: a hora é a da troca
    with db.engine.begin() as conexao:
        conexao.execute(TelaEvento.__table__.insert().values(
            ts_ms=agora_ms, tipo=tipo, titulo=(titulo or '')[:MAX_TITULO],
            texto=(texto or '')[:MAX_TEXTO], tema=tema))
        _limpar_antigos(conexao, agora_ms)
    _ultimo_gravado = evento


def _sem_atrapalhar(funcao):
    try:
        funcao()
    except Exception:
        logger.exception('Falha ao registrar a troca de tela')


def tela_mudou(kind, url=''):
    """Chamado por telao.set_public() a cada conteúdo novo no público."""
    def registrar():
        global _conteudo, _oculto
        _conteudo = _descrever(kind, url)
        if _conteudo[0] in _COM_TEXTO:
            _oculto = False   # mostrar_se_escondido(): conteúdo novo reaparece
        _gravar()
    _sem_atrapalhar(registrar)


def tela_neutra():
    """Tela preta/logo ligada ou desligada (estado em display_state)."""
    _sem_atrapalhar(_gravar)


def texto_visivel(visivel):
    def registrar():
        global _oculto
        _oculto = not visivel
        _gravar()
    _sem_atrapalhar(registrar)


def eventos_entre(inicio_ms, fim_ms):
    linhas = (TelaEvento.query
              .filter(TelaEvento.ts_ms >= inicio_ms, TelaEvento.ts_ms < fim_ms)
              .order_by(TelaEvento.ts_ms, TelaEvento.id).all())
    return [{'ts': e.ts_ms, 'tipo': e.tipo, 'titulo': e.titulo, 'texto': e.texto,
             'tema': json.loads(e.tema) if e.tema else None} for e in linhas]
