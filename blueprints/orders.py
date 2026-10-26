"""Ordem do culto: CRUD via API, templates de item, section-templates,
compatibilidade com o sistema antigo (/save, /load — Fase 5.6: migradas
pra mirar a ordem de HOJE em vez do antigo order_of_service.json, um
bucket solto sem data), páginas de edição, e api_culto_status (passos da
ordem de hoje — por dado, não por escala de equipe, por isso fica aqui e
não em agenda)."""
from datetime import date

from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required

from i18n import gettext as tr
from orders_store import (
    CULTO_FIELDS,
    clear_feitos,
    current_key,
    get_feitos,
    get_next_order,
    get_order,
    load_orders,
    save_order,
    save_orders,
    load_templates,
    save_templates_file,
    load_section_templates,
    save_section_templates,
    key_date,
    key_seq,
    set_feito,
)

orders_bp = Blueprint('orders', __name__)


@orders_bp.route('/api/culto/status', methods=['GET'])
@login_required
def api_culto_status():
    today = date.today().isoformat()
    order = get_order(current_key(today))

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


@orders_bp.route('/api/painel/musica', methods=['GET'])
@login_required
def api_painel_musica():
    """Qual música abrir na aba Música do painel do Controle: a que está
    (ou esteve por último) no telão; senão a primeira do próximo culto."""
    import display_state
    from models import LyricsState
    today = date.today().isoformat()
    order_date, order = get_next_order(today)
    song_id = (display_state._last_lyrics_payload or {}).get('songId')
    if song_id is None:
        try:
            state = LyricsState.query.first()
            song_id = state.song_id if state else None
        except Exception:
            song_id = None
    if song_id is None and order:
        for item in order.get('itens', []):
            url = item.get('url') or ''
            if url.startswith('/lyrics/'):
                song_id = url.split('/lyrics/')[1].split('?')[0]
                break
    return jsonify({'song_id': song_id, 'order_date': order_date})


@orders_bp.route('/api/culto/proximo', methods=['GET'])
@login_required
def api_culto_proximo():
    """Próximo culto (hoje ou depois) pro card do dashboard: dados do
    culto, itens da ordem e equipe. Itens de música vêm como
    "Título | Artista" — separa aqui pra a tela não precisar."""
    today = date.today()
    order_date, order = get_next_order(today.isoformat())
    if not order_date:
        return jsonify({'status': 'none'})

    itens = []
    for item in order.get('itens', []):
        if item.get('isBible'):
            ref = item.get('reference') or item.get('title') or 'Leitura'
            itens.append({'kind': 'bible', 'title': ref,
                          'url': item.get('bible_url') or item.get('url') or f'/bible?search={ref}'})
        elif 'anyText' in item:
            text = (item.get('anyText') or '').strip()
            if text:
                itens.append({'kind': 'text', 'title': text.splitlines()[0][:80]})
        else:
            title, _, artist = (item.get('title') or 'Item').partition(' | ')
            itens.append({'kind': 'song', 'title': title.strip(), 'artist': artist.strip(), 'url': item.get('url')})

    louvor = order.get('louvor') or {}
    midia = order.get('midia') or {}
    equipe = []
    for label, pessoa in (('Mídia', midia.get('lider')), ('Palco', midia.get('palco')), ('Visual', midia.get('visual'))):
        if pessoa:
            equipe.append({'funcao': label, 'pessoa': pessoa})
    for m in louvor.get('musicos') or []:
        if m.get('pessoa'):
            equipe.append({'funcao': m.get('instrumento') or 'Música', 'pessoa': m['pessoa']})
    cantores = [c for c in (louvor.get('cantores') or []) if c]
    if cantores:
        equipe.append({'funcao': 'Vozes', 'pessoa': ', '.join(cantores)})

    return jsonify({
        'status': 'ok',
        'date': order_date,
        'days_until': (date.fromisoformat(key_date(order_date)) - today).days,
        'tipo': order.get('tipo', ''),
        'horario': order.get('horario_culto') or order.get('horario') or '',
        'dirigente': order.get('dirigente', ''),
        'pregador': order.get('pregador', ''),
        'itens': itens,
        'equipe': equipe,
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
    return jsonify({"error": tr("Ordem não encontrada")}), 404

# API para salvar/atualizar uma ordem
@orders_bp.route('/api/orders/<date>', methods=['POST'])
@login_required
def api_save_order(date):
    """Salva ou atualiza uma ordem específica"""
    try:
        data = request.get_json(force=True) or {}
        # get_order()/save_order() em vez de load_orders()/save_orders() com
        # o dict inteiro: essa rota é o salvamento real de escala/ordem do
        # culto — carregar/resalvar as 176 ordens só pra mudar 1 data era
        # proporcional ao total de ordens, não à mudança real (mesma causa
        # raiz do achado em touch_last_played(), ver songs_store.py —
        # 2026-08-15).
        order = get_order(date)

        # ---------- EVENTOS -----------
        # Eventos são do dia: só a linha da data pura guarda (o 2º, 3º...
        # culto do dia não tem eventos próprios)
        eventos = data.get('eventos', []) if key_seq(date) == 1 else []
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

        # ---------- TEMA e HORÁRIO da ordem (/order/<data>) ----------
        # A página de editar a ordem manda 'tema' e 'horario' (o do campo
        # Horário dela — a agenda usa 'horario_culto'), e esta rota não
        # copiava nenhum dos dois: o get_order() acima mantinha o valor
        # antigo e o que a pessoa digitou se perdia. Só mexe quando o campo
        # vem no pedido, pra quem não manda (agenda) não apagar o que já tem.
        for campo in ('tema', 'horario'):
            if campo in data:
                valor = (data.get(campo) or '').strip()
                if valor:
                    order[campo] = valor
                else:
                    order.pop(campo, None)

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

        # save_order(date, {}) já remove a ordem do banco se estiver vazia
        # (mesma "limpeza automática" que o dict inteiro tinha antes).
        if save_order(date, order):
            return jsonify({"message": tr("Ordem salva com sucesso!")}), 200

        return jsonify({"error": tr("Erro ao salvar ordem")}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# API para deletar uma ordem
@orders_bp.route('/api/orders/<date>', methods=['DELETE'])
@login_required
def api_delete_order(date):
    """Deleta uma ordem específica"""
    try:
        if get_order(date):
            if save_order(date, {}):
                return jsonify({"message": tr("Ordem deletada com sucesso!")}), 200
        return jsonify({"error": tr("Ordem não encontrada")}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Itens da ordem já feitos no culto (view/order): todos veem (GET é
# público, a página atualiza sozinha); só quem está logado marca
@orders_bp.route('/api/orders/<date>/feitos', methods=['GET'])
def api_get_feitos(date):
    return jsonify({'feitos': get_feitos(date)})


@orders_bp.route('/api/orders/<date>/feitos', methods=['POST'])
@login_required
def api_set_feito(date):
    data = request.get_json(force=True) or {}
    if data.get('limpar'):
        clear_feitos(date)
        return jsonify({'feitos': []})
    item_id = (data.get('item') or '').strip()
    if not item_id:
        return jsonify({'error': tr('Item obrigatório')}), 400
    feitos = set_feito(date, item_id, bool(data.get('feito')))
    if feitos is None:
        return jsonify({'error': tr('Ordem não encontrada')}), 404
    return jsonify({'feitos': feitos})


# Exclui UM culto (de um dia com vários): apaga os dados do culto mas
# mantém os eventos do dia, que vivem na linha da data pura
@orders_bp.route('/api/cultos/<date>', methods=['DELETE'])
@login_required
def api_delete_culto(date):
    order = get_order(date)
    if not order:
        return jsonify({"error": tr("Culto não encontrado")}), 404
    for field in CULTO_FIELDS:
        order.pop(field, None)
    save_order(date, order if order.get('eventos') else {})
    return jsonify({"message": tr("Culto excluído"), "day": key_date(date)}), 200


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
        return jsonify({'error': tr('Nome obrigatório')}), 400
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
        return jsonify({'error': tr('Nome obrigatório')}), 400
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
        return jsonify({'error': tr('Parâmetros obrigatórios: section, fields, dates')}), 400
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

# Rota para salvar a lista (mantém compatibilidade com sistema antigo —
# sem data no contexto, mira sempre a ordem de HOJE)
@orders_bp.route('/save', methods=['POST'])
@login_required
def save_list():
    try:
        data = request.json
        today = current_key(date.today().isoformat())
        order = get_order(today)
        if data:
            order['itens'] = data
        else:
            order.pop('itens', None)
        save_order(today, order)
        return jsonify({"message": tr("Lista salva com sucesso!")}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Rota para carregar a lista (mantém compatibilidade com sistema antigo —
# sem data no contexto, mira sempre a ordem de HOJE)
@orders_bp.route('/load', methods=['GET'])
def load_list():
    try:
        # Verifica se há parâmetro de data explícito
        date_param = request.args.get('date')
        if date_param:
            return jsonify(get_order(date_param).get('itens', [])), 200

        # Sem data no parâmetro: usa a ordem de hoje (antes lia
        # order_of_service.json, um bucket solto sem data — Fase 5.6)
        today = current_key(date.today().isoformat())
        return jsonify(get_order(today).get('itens', [])), 200
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
    order = get_order(date)
    return render_template("order_edit.html", date=date, order=order, is_new=False)
