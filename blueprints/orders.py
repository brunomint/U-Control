"""Ordem do culto: CRUD via API, templates de item, section-templates,
compatibilidade com o sistema antigo (/save, /load), páginas de edição, e
api_culto_status (passos da ordem de hoje — por dado, não por escala de
equipe, por isso fica aqui e não em agenda)."""
import json
import os
from datetime import date

from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required

from orders_store import (
    DATA_FILE,
    load_orders,
    save_orders,
    load_templates,
    save_templates_file,
    load_section_templates,
    save_section_templates,
)

orders_bp = Blueprint('orders', __name__)


@orders_bp.route('/api/culto/status', methods=['GET'])
@login_required
def api_culto_status():
    today = date.today().isoformat()
    orders = load_orders()
    order = orders.get(today)

    if not order:
        return jsonify({
            'status': 'no_service',
            'date': today,
            'message': 'Nenhum culto agendado para hoje',
            'steps': []
        })

    steps = []
    for item in order.get('itens', []):
        title = (item.get('title') or '').strip()
        title_upper = title.upper()
        step_type = 'item'
        if 'ABERTURA' in title_upper or 'INÍCIO' in title_upper or 'INICIO' in title_upper:
            step_type = 'abertura'
        elif 'LOUVOR' in title_upper or 'MÚSICA' in title_upper or 'MUSICA' in title_upper or 'HINO' in title_upper:
            step_type = 'louvor'
        elif 'MENSAGEM' in title_upper or 'PREGAÇÃO' in title_upper or 'PREGACAO' in title_upper or 'PALAVRA' in title_upper or 'PRELEÇÃO' in title_upper or 'PRELECAO' in title_upper:
            step_type = 'mensagem'
        elif 'OFERTA' in title_upper or 'OFERTAS' in title_upper or 'DÍZIMO' in title_upper or 'DIZIMO' in title_upper:
            step_type = 'oferta'
        elif 'ENCERRAMENTO' in title_upper or 'FINAL' in title_upper or 'BÊNÇÃO' in title_upper or 'BENCAO' in title_upper:
            step_type = 'encerramento'

        steps.append({
            'title': title or 'Item',
            'type': step_type
        })

    return jsonify({
        'status': 'ok',
        'date': today,
        'tipo': order.get('tipo', ''),
        'horario': order.get('horario_culto', ''),
        'dirigente': order.get('dirigente', ''),
        'pregador': order.get('pregador', ''),
        'steps': steps
    })


# API para listar todas as ordens
@orders_bp.route('/api/orders', methods=['GET'])
def api_get_orders():
    """Retorna todas as ordens de culto"""
    orders = load_orders()
    return jsonify(orders)

# API para obter uma ordem específica
@orders_bp.route('/api/orders/<date>', methods=['GET'])
def api_get_order(date):
    """Retorna uma ordem específica por data"""
    orders = load_orders()
    if date in orders:
        return jsonify(orders[date])
    return jsonify({"error": "Ordem não encontrada"}), 404

# API para salvar/atualizar uma ordem
@orders_bp.route('/api/orders/<date>', methods=['POST'])
@login_required
def api_save_order(date):
    """Salva ou atualiza uma ordem específica"""
    try:
        data = request.get_json(force=True) or {}
        orders = load_orders()

        order = orders.get(date, {})

        # ---------- EVENTOS -----------
        eventos = data.get('eventos', [])
        lista_eventos = []

        if isinstance(eventos, list):
            lista_eventos = [
                {
                    'titulo': e.get('titulo', '').strip(),
                    'hora': e.get('hora', '').strip(),
                    'responsavel': e.get('responsavel', '').strip(),
                    'obs': e.get('obs', '').strip()
                }
                for e in eventos
                if (e.get('titulo') or '').strip()
            ]
        # só salva se tiver conteúdo
        if lista_eventos:
            order['eventos'] = lista_eventos
        else:
            order.pop('eventos', None)

        # ---------- LOUVOR ----------
        tipo = (data.get('tipo') or '').strip()
        horario = (data.get('horario_culto') or '').strip()
        dirigente = (data.get('dirigente') or '').strip()
        pregador = (data.get('pregador') or '').strip()

        louvor = data.get('louvor') or {}
        cantores = louvor.get('cantores') or []
        musicos = louvor.get('musicos') or []

        itens = data.get('itens') or []

        tem_louvor = (
            (tipo and tipo.lower() != 'nenhum') or
            horario or
            dirigente or
            pregador or
            len(cantores) > 0 or
            len(musicos) > 0 or
            len(itens) > 0
        )

        if tem_louvor:
            order['tipo'] = tipo
            order['horario_culto'] = horario
            order['dirigente'] = dirigente
            order['pregador'] = pregador
            order['louvor'] = {
                'cantores': cantores,
                'musicos': musicos
            }
            order['itens'] = itens
        else:
            order.pop('tipo', None)
            order.pop('horario_culto', None)
            order.pop('dirigente', None)
            order.pop('pregador', None)
            order.pop('louvor', None)
            order.pop('itens', None)

        # ---------- MÍDIA ----------
        midia = data.get('midia') or {}

        lider = (midia.get('lider') or '').strip()
        palco = (midia.get('palco') or '').strip()
        visual = (midia.get('visual') or '').strip()
        equipe = midia.get('equipe') or []
        obs = (midia.get('obs') or '').strip()

        tem_midia = (
            lider or palco or visual or obs or len(equipe) > 0
        )

        if tem_midia:
            order['midia'] = {
                'lider': lider,
                'palco': palco,
                'visual': visual,
                'equipe': equipe,
                'obs': obs
            }
        else:
            order.pop('midia', None)

        # ---------- LIMPEZA AUTOMÁTICA ----------
        def is_empty_order(o):
            return len(o) == 0

        if is_empty_order(order):
            # remove do banco se estiver vazio
            if date in orders:
                del orders[date]
        else:
            # salva normalmente
            orders[date] = order

        if save_orders(orders):
            return jsonify({"message": "Ordem salva com sucesso!"}), 200

        return jsonify({"error": "Erro ao salvar ordem"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# API para deletar uma ordem
@orders_bp.route('/api/orders/<date>', methods=['DELETE'])
@login_required
def api_delete_order(date):
    """Deleta uma ordem específica"""
    try:
        orders = load_orders()
        if date in orders:
            del orders[date]
            if save_orders(orders):
                return jsonify({"message": "Ordem deletada com sucesso!"}), 200
        return jsonify({"error": "Ordem não encontrada"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@orders_bp.route('/api/templates', methods=['GET'])
def api_get_templates():
    return jsonify(load_templates())

@orders_bp.route('/api/templates', methods=['POST'])
@login_required
def api_save_template():
    data = request.get_json(force=True) or {}
    name = data.get('name', '').strip()
    items = data.get('items', [])
    if not name:
        return jsonify({'error': 'Nome obrigatório'}), 400
    templates = load_templates()
    templates[name] = items
    save_templates_file(templates)
    return jsonify({'ok': True})

@orders_bp.route('/api/templates/<path:name>', methods=['DELETE'])
@login_required
def api_delete_template(name):
    templates = load_templates()
    templates.pop(name, None)
    save_templates_file(templates)
    return jsonify({'ok': True})


@orders_bp.route('/api/section-templates/<section>', methods=['GET'])
def api_get_section_templates(section):
    return jsonify(load_section_templates().get(section, {}))

@orders_bp.route('/api/section-templates/<section>', methods=['POST'])
@login_required
def api_save_section_template(section):
    data = request.get_json(force=True) or {}
    name = data.get('name', '').strip()
    fields = data.get('fields', {})
    if not name:
        return jsonify({'error': 'Nome obrigatório'}), 400
    all_tpls = load_section_templates()
    all_tpls.setdefault(section, {})[name] = fields
    save_section_templates(all_tpls)
    return jsonify({'ok': True})

@orders_bp.route('/api/section-templates/<section>/<path:name>', methods=['DELETE'])
@login_required
def api_delete_section_template(section, name):
    all_tpls = load_section_templates()
    all_tpls.get(section, {}).pop(name, None)
    save_section_templates(all_tpls)
    return jsonify({'ok': True})

@orders_bp.route('/api/section-templates/apply-month', methods=['POST'])
@login_required
def api_apply_section_template_month():
    data = request.get_json(force=True) or {}
    section = data.get('section', '').strip()
    fields = data.get('fields', {})
    dates = data.get('dates', [])
    if not section or not fields or not dates:
        return jsonify({'error': 'Parâmetros obrigatórios: section, fields, dates'}), 400
    orders = load_orders()
    for d in dates:
        order = orders.get(d, {})
        if section == 'louvor':
            # dirigente/pregador/tipo vivem na raiz do order, não dentro de order["louvor"]
            for key in ('dirigente', 'pregador', 'tipo', 'horario_culto'):
                if key in fields:
                    order[key] = fields[key]
            if 'louvor' in fields:
                order['louvor'] = fields['louvor']
        else:
            order[section] = fields
        orders[d] = order
    save_orders(orders)
    return jsonify({'ok': True, 'applied': len(dates)})

# Rota para salvar a lista (mantém compatibilidade com sistema antigo)
@orders_bp.route('/save', methods=['POST'])
def save_list():
    try:
        data = request.json
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return jsonify({"message": "Lista salva com sucesso!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Rota para carregar a lista (mantém compatibilidade com sistema antigo)
@orders_bp.route('/load', methods=['GET'])
def load_list():
    try:
        # Verifica se há parâmetro de data
        date = request.args.get('date')
        if date:
            orders = load_orders()
            if date in orders:
                return jsonify(orders[date].get('itens', [])), 200
            return jsonify([]), 200

        # Fallback para sistema antigo
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = []
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Rota principal - Lista de ordens
@orders_bp.route("/order")
@login_required
def order_list():
    """Lista todas as ordens de culto em cards"""
    return render_template("order_list.html")

# Rota para criar nova ordem
@orders_bp.route("/order/new")
@login_required
def order_new():
    """Página para criar nova ordem de culto"""
    # Gera data de hoje como padrão
    from datetime import date
    today = date.today().isoformat()
    return render_template("order_edit.html", date=today, order=None, is_new=True)

# Rota para editar ordem existente
@orders_bp.route("/order/<date>")
@login_required
def order_edit(date):
    """Página para editar ordem de culto existente"""
    orders = load_orders()
    order = orders.get(date)
    return render_template("order_edit.html", date=date, order=order, is_new=False)
