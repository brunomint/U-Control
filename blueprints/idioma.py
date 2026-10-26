"""Sistema → Idioma: escolher o idioma da interface (ver i18n.py), e o
dicionário que o JS das páginas usa (static/js/i18n.js)."""
import json

from flask import Blueprint, Response, jsonify, render_template, request
from flask_login import login_required

import i18n
from extensions import db
from models import Setting

idioma_bp = Blueprint('idioma', __name__)


@idioma_bp.route('/idioma')
@login_required
def idioma_page():
    return render_template('idioma.html', idiomas=i18n.IDIOMAS, salvo=i18n.idioma_salvo())


@idioma_bp.route('/api/idioma', methods=['POST'])
@login_required
def api_idioma():
    # '' = seguir o navegador de cada um
    idioma = (request.get_json(silent=True) or {}).get('idioma') or None
    if idioma is not None and idioma not in i18n.IDIOMAS:
        return jsonify({'error': 'Idioma desconhecido.'}), 400
    row = Setting.query.first()
    if not row:
        row = Setting()
        db.session.add(row)
    row.language = idioma
    db.session.commit()
    return jsonify({'ok': True, 'idioma': idioma})


@idioma_bp.route('/i18n/<idioma>.js')
def dicionario_js(idioma):
    # Sem login: login, telas e /view também usam
    dados = json.dumps(i18n.dicionario(idioma), ensure_ascii=False)
    resp = Response(f'window.UC_I18N = {dados};\n', mimetype='application/javascript')
    resp.cache_control.max_age = 86400  # o ?v= muda quando o dicionário muda
    return resp
