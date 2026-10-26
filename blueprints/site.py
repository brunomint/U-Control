"""Site no telão pelo Controle (painel "Site", templates/_site_telao.html).
Quem abre e comanda o navegador é o navegador_telao.py; aqui ficam as
rotas e a lista de sites salvos (<instance>/sites_salvos.json, a mesma
pra todos os Controles). Cada mudança vai pros Controles abertos
('site_estado'), pra o painel de todos mostrar o mesmo."""
import json
import os

from flask import Blueprint, current_app, jsonify, request
from flask_login import login_required

import navegador_telao
from extensions import socketio
from i18n import gettext as _

site_bp = Blueprint('site', __name__)

MAX_SALVOS = 30


@site_bp.app_context_processor
def _no_controle():
    # control.html só mostra a ferramenta onde ela funciona
    return {'site_no_telao_disponivel': navegador_telao.disponivel}


def _avisar(estado):
    socketio.emit('site_estado', estado)
    return jsonify({'ok': True, **estado})


def _erro(e):
    # Mensagens fixas do navegador_telao.SiteErro têm tradução no
    # dicionário (a própria frase é a chave); as com valores ficam em português
    return jsonify({'ok': False, 'erro': _(str(e))}), 409


@site_bp.route('/api/site/estado')
@login_required
def api_estado():
    return jsonify(navegador_telao.estado())


@site_bp.route('/api/site/abrir', methods=['POST'])
@login_required
def api_abrir():
    try:
        return _avisar(navegador_telao.abrir((request.get_json(silent=True) or {}).get('url')))
    except navegador_telao.SiteErro as e:
        return _erro(e)


@site_bp.route('/api/site/comando', methods=['POST'])
@login_required
def api_comando():
    try:
        return _avisar(navegador_telao.comando((request.get_json(silent=True) or {}).get('acao')))
    except navegador_telao.SiteErro as e:
        return _erro(e)
    except Exception as e:  # janela fechada no meio, navegador travado
        current_app.logger.exception('site no telão: comando falhou')
        return _erro(_('O navegador do site não respondeu ({erro}).', erro=e.__class__.__name__))


@site_bp.route('/api/site/fechar', methods=['POST'])
@login_required
def api_fechar():
    navegador_telao.fechar()
    return _avisar(navegador_telao.estado())


# --- sites salvos ----------------------------------------------------------

def _arquivo():
    return os.path.join(current_app.instance_path, 'sites_salvos.json')


def _salvos():
    try:
        with open(_arquivo(), encoding='utf-8') as f:
            dados = json.load(f)
        return [s for s in dados if isinstance(s, dict) and s.get('url')][:MAX_SALVOS]
    except (OSError, ValueError):
        return []


@site_bp.route('/api/site/salvos')
@login_required
def api_salvos():
    return jsonify(_salvos())


@site_bp.route('/api/site/salvos', methods=['POST'])
@login_required
def api_salvar():
    dados = request.get_json(silent=True) or {}
    try:
        url = navegador_telao.normalizar(dados.get('url'))
    except navegador_telao.SiteErro as e:
        return jsonify({'ok': False, 'erro': _(str(e))}), 400
    nome = (dados.get('nome') or '').strip()[:60] or url.split('://', 1)[1].split('/')[0]
    salvos = [s for s in _salvos() if s['url'] != url]
    salvos.insert(0, {'nome': nome, 'url': url})
    os.makedirs(os.path.dirname(_arquivo()), exist_ok=True)
    with open(_arquivo(), 'w', encoding='utf-8') as f:
        json.dump(salvos[:MAX_SALVOS], f, ensure_ascii=False)
    return jsonify({'ok': True, 'salvos': salvos[:MAX_SALVOS]})


@site_bp.route('/api/site/salvos/remover', methods=['POST'])
@login_required
def api_remover():
    url = (request.get_json(silent=True) or {}).get('url')
    salvos = [s for s in _salvos() if s['url'] != url]
    with open(_arquivo(), 'w', encoding='utf-8') as f:
        json.dump(salvos, f, ensure_ascii=False)
    return jsonify({'ok': True, 'salvos': salvos})
