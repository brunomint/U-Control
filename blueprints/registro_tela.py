"""Página "Registro da tela": mostra as trocas de um dia junto com o áudio do
culto, escolhido no próprio computador (não é enviado ao servidor), pra medir
o atraso entre tela e áudio. A lógica do registro fica em registro_tela.py."""
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required

from i18n import gettext as tr
from registro_tela import eventos_entre

registro_tela_bp = Blueprint('registro_tela', __name__)


@registro_tela_bp.route('/registro-tela')
@login_required
def pagina():
    return render_template('registro_tela.html')


@registro_tela_bp.route('/api/registro-tela')
@login_required
def api_eventos():
    try:
        dia = datetime.strptime(request.args.get('dia', ''), '%Y-%m-%d')
    except ValueError:
        return jsonify({'erro': tr('Data inválida.')}), 400
    inicio = int(dia.timestamp() * 1000)
    fim = int((dia + timedelta(days=1)).timestamp() * 1000)
    return jsonify({'eventos': eventos_entre(inicio, fim)})
