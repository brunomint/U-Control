"""Bíblia: navegação, busca, exibição e integração com a ordem do culto.
Praticamente autocontido — só generate_bible_url() é usada fora daqui
(pelas rotas /view/* em main.py, que importam direto deste módulo).

A integração com a ordem do culto (add/remove/listar passagem) mira
sempre a ordem de HOJE (tabela Order, por data) — Fase 5.6, unificação
do antigo order_of_service.json (sem data, bucket solto). Os botões daqui
não têm nenhum seletor de data, por isso a resposta sempre indica a data
que recebeu o item, pra quem estiver preparando um culto futuro perceber
na hora que caiu no lugar errado."""
import json
import logging
import os
import re
from datetime import date

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required
from flask_socketio import emit

from display_log import append_display_log
from extensions import socketio
from models import LyricsState
from orders_store import get_order, save_order
from settings_store import load_settings, save_settings

logger = logging.getLogger('ucontrol')

bible_bp = Blueprint('bible', __name__)

# Cache para Bíblias carregadas
_bible_cache = {}
_bible_metadata = None


def get_preferred_translation():
    """Retorna a tradução preferida da Bíblia."""
    settings = load_settings()
    return settings.get('bible_translation', 'acf')


def set_preferred_translation(translation):
    """Salva a tradução preferida da Bíblia."""
    settings = load_settings()
    settings['bible_translation'] = translation
    save_settings(settings)


def load_bible_metadata():
    """Carrega os metadados dos livros da Bíblia."""
    global _bible_metadata
    if _bible_metadata is None:
        metadata_path = os.path.join(os.getcwd(), 'bibles', 'books_metadata.json')
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r', encoding='utf-8') as f:
                _bible_metadata = json.load(f)
        else:
            _bible_metadata = {"translations": {}, "books": []}
    return _bible_metadata


def load_bible(translation='acf'):
    """Carrega uma tradução da Bíblia do arquivo JSON."""
    global _bible_cache
    if translation not in _bible_cache:
        bible_path = os.path.join(os.getcwd(), 'bibles', f'{translation}.json')
        if os.path.exists(bible_path):
            with open(bible_path, 'r', encoding='utf-8-sig') as f:
                _bible_cache[translation] = json.load(f)
        else:
            _bible_cache[translation] = []
    return _bible_cache[translation]


def get_book_name(abbrev):
    """Retorna o nome completo do livro pela abreviação."""
    metadata = load_bible_metadata()
    for book in metadata.get('books', []):
        if book['abbrev'] == abbrev:
            return book['name']
    return abbrev.upper()


def get_translation_abbrev(translation):
    """Sigla de exibição da tradução (ex: 'nvi' -> 'NVI')."""
    metadata = load_bible_metadata()
    info = metadata.get('translations', {}).get(translation)
    return info['abbrev'] if info else translation.upper()


def get_translation_name(translation):
    """Nome completo da tradução (ex: 'nvi' -> 'Nova Versão Internacional'),
    pro rodapé do telão — mesmo padrão do Holyrics de mostrar a versão
    usada por extenso, não só a sigla."""
    metadata = load_bible_metadata()
    info = metadata.get('translations', {}).get(translation)
    return info['name'] if info else translation.upper()


def generate_bible_url(reference):
    """Gera URL de controle a partir de uma referência bíblica."""
    # Mapeamento de nomes para abreviações
    book_map = {
        'gênesis': 'gn', 'genesis': 'gn', 'gn': 'gn',
        'êxodo': 'ex', 'exodo': 'ex', 'ex': 'ex',
        'levítico': 'lv', 'levitico': 'lv', 'lv': 'lv',
        'números': 'nm', 'numeros': 'nm', 'nm': 'nm',
        'deuteronômio': 'dt', 'deuteronomio': 'dt', 'dt': 'dt',
        'josué': 'js', 'josue': 'js', 'js': 'js',
        'juízes': 'jz', 'juizes': 'jz', 'jz': 'jz',
        'rute': 'rt', 'rt': 'rt',
        '1 samuel': '1sm', '1samuel': '1sm', '1sm': '1sm', '1 sm': '1sm',
        '2 samuel': '2sm', '2samuel': '2sm', '2sm': '2sm', '2 sm': '2sm',
        '1 reis': '1rs', '1reis': '1rs', '1rs': '1rs', '1 rs': '1rs',
        '2 reis': '2rs', '2reis': '2rs', '2rs': '2rs', '2 rs': '2rs',
        '1 crônicas': '1cr', '1 cronicas': '1cr', '1cr': '1cr', '1 cr': '1cr',
        '2 crônicas': '2cr', '2 cronicas': '2cr', '2cr': '2cr', '2 cr': '2cr',
        'esdras': 'ed', 'ed': 'ed',
        'neemias': 'ne', 'ne': 'ne',
        'ester': 'et', 'et': 'et',
        'jó': 'job', 'job': 'job',
        'salmos': 'sl', 'salmo': 'sl', 'sl': 'sl',
        'provérbios': 'pv', 'proverbios': 'pv', 'pv': 'pv',
        'eclesiastes': 'ec', 'ec': 'ec',
        'cantares': 'ct', 'cânticos': 'ct', 'canticos': 'ct', 'ct': 'ct',
        'isaías': 'is', 'isaias': 'is', 'is': 'is',
        'jeremias': 'jr', 'jr': 'jr',
        'lamentações': 'lm', 'lamentacoes': 'lm', 'lm': 'lm',
        'ezequiel': 'ez', 'ez': 'ez',
        'daniel': 'dn', 'dn': 'dn',
        'oséias': 'os', 'oseias': 'os', 'os': 'os',
        'joel': 'jl', 'jl': 'jl',
        'amós': 'am', 'amos': 'am', 'am': 'am',
        'obadias': 'ob', 'ob': 'ob',
        'jonas': 'jn', 'jn': 'jn',
        'miquéias': 'mq', 'miqueias': 'mq', 'mq': 'mq',
        'naum': 'na', 'na': 'na',
        'habacuque': 'hc', 'hc': 'hc',
        'sofonias': 'sf', 'sf': 'sf',
        'ageu': 'ag', 'ag': 'ag',
        'zacarias': 'zc', 'zc': 'zc',
        'malaquias': 'ml', 'ml': 'ml',
        'mateus': 'mt', 'mt': 'mt',
        'marcos': 'mc', 'mc': 'mc',
        'lucas': 'lc', 'lc': 'lc',
        'joão': 'jo', 'joao': 'jo',
        'atos': 'at', 'at': 'at',
        'romanos': 'rm', 'rm': 'rm',
        '1 coríntios': '1co', '1 corintios': '1co', '1co': '1co', '1 co': '1co',
        '2 coríntios': '2co', '2 corintios': '2co', '2co': '2co', '2 co': '2co',
        'gálatas': 'gl', 'galatas': 'gl', 'gl': 'gl',
        'efésios': 'ef', 'efesios': 'ef', 'ef': 'ef',
        'filipenses': 'fp', 'fp': 'fp',
        'colossenses': 'cl', 'cl': 'cl',
        '1 tessalonicenses': '1ts', '1ts': '1ts', '1 ts': '1ts',
        '2 tessalonicenses': '2ts', '2ts': '2ts', '2 ts': '2ts',
        '1 timóteo': '1tm', '1 timoteo': '1tm', '1tm': '1tm', '1 tm': '1tm',
        '2 timóteo': '2tm', '2 timoteo': '2tm', '2tm': '2tm', '2 tm': '2tm',
        'tito': 'tt', 'tt': 'tt',
        'filemom': 'fm', 'fm': 'fm',
        'hebreus': 'hb', 'hb': 'hb',
        'tiago': 'tg', 'tg': 'tg',
        '1 pedro': '1pe', '1pe': '1pe', '1 pe': '1pe',
        '2 pedro': '2pe', '2pe': '2pe', '2 pe': '2pe',
        '1 joão': '1jo', '1 joao': '1jo', '1jo': '1jo', '1 jo': '1jo',
        '2 joão': '2jo', '2 joao': '2jo', '2jo': '2jo', '2 jo': '2jo',
        '3 joão': '3jo', '3 joao': '3jo', '3jo': '3jo', '3 jo': '3jo',
        'judas': 'jd', 'jd': 'jd',
        'apocalipse': 'ap', 'ap': 'ap'
    }

    # Regex para capturar: livro capítulo:versículo(s)
    regex = r'^(.+?)\s*(\d+)(?:\s*:\s*(\d+)(?:\s*-\s*(\d+))?)?$'
    match = re.match(regex, reference, re.IGNORECASE)

    if not match:
        return f'/bible?search={reference}'

    book_name = match.group(1).strip().lower()
    chapter = match.group(2)
    verse_start = match.group(3)
    verse_end = match.group(4)

    book_abbrev = book_map.get(book_name)
    if not book_abbrev:
        return f'/bible?search={reference}'

    url = f'/bible/control/{book_abbrev}/{chapter}'
    if verse_start:
        if verse_end and verse_end != verse_start:
            url += f'/{verse_start}-{verse_end}'
        else:
            url += f'/{verse_start}'

    return url


# Mapeamento de abreviações equivalentes entre diferentes traduções
ABBREV_ALIASES = {
    'sl': ['ps', 'salmos', 'salmo'],      # Salmos
    'ps': ['sl', 'salmos', 'salmo'],
    'jz': ['jud', 'juizes'],               # Juízes
    'jud': ['jz', 'juizes'],
    'ct': ['ss', 'canticos', 'cantares'],  # Cantares
    'ss': ['ct', 'canticos', 'cantares'],
    'lm': ['la', 'lamentacoes'],           # Lamentações
    'la': ['lm', 'lamentacoes'],
    'am': ['amos'],                         # Amós
    'ob': ['obadias', 'abd'],               # Obadias
    'mq': ['mi', 'miqueias'],               # Miquéias
    'mi': ['mq', 'miqueias'],
    'na': ['naum'],                         # Naum
    'hc': ['hab', 'habacuque'],             # Habacuque
    'hab': ['hc', 'habacuque'],
    'sf': ['zep', 'sofonias'],              # Sofonias
    'zep': ['sf', 'sofonias'],
    'ag': ['hag', 'ageu'],                  # Ageu
    'hag': ['ag', 'ageu'],
    'zc': ['zec', 'zacarias'],              # Zacarias
    'zec': ['zc', 'zacarias'],
    'ml': ['mal', 'malaquias'],             # Malaquias
    'mal': ['ml', 'malaquias'],
    'mt': ['mat', 'mateus'],                # Mateus
    'mat': ['mt', 'mateus'],
    'mc': ['mr', 'marcos'],                 # Marcos
    'mr': ['mc', 'marcos'],
    'lc': ['lk', 'lucas'],                  # Lucas
    'lk': ['lc', 'lucas'],
    'jo': ['jn', 'joao'],                   # João
    'jn': ['jo', 'joao'],
    'at': ['acts', 'atos'],                 # Atos
    'acts': ['at', 'atos'],
    'rm': ['rom', 'romanos'],               # Romanos
    'rom': ['rm', 'romanos'],
    '1co': ['1cor', '1corintios'],          # 1 Coríntios
    '1cor': ['1co', '1corintios'],
    '2co': ['2cor', '2corintios'],          # 2 Coríntios
    '2cor': ['2co', '2corintios'],
    'gl': ['gal', 'galatas'],               # Gálatas
    'gal': ['gl', 'galatas'],
    'ef': ['eph', 'efesios'],               # Efésios
    'eph': ['ef', 'efesios'],
    'fp': ['php', 'filipenses'],            # Filipenses
    'php': ['fp', 'filipenses'],
    'cl': ['col', 'colossenses'],           # Colossenses
    'col': ['cl', 'colossenses'],
    '1ts': ['1th', '1tessalonicenses'],     # 1 Tessalonicenses
    '1th': ['1ts', '1tessalonicenses'],
    '2ts': ['2th', '2tessalonicenses'],     # 2 Tessalonicenses
    '2th': ['2ts', '2tessalonicenses'],
    '1tm': ['1ti', '1timoteo'],             # 1 Timóteo
    '1ti': ['1tm', '1timoteo'],
    '2tm': ['2ti', '2timoteo'],             # 2 Timóteo
    '2ti': ['2tm', '2timoteo'],
    'tt': ['tit', 'tito'],                  # Tito
    'tit': ['tt', 'tito'],
    'fm': ['phm', 'filemom'],               # Filemom
    'phm': ['fm', 'filemom'],
    'hb': ['heb', 'hebreus'],               # Hebreus
    'heb': ['hb', 'hebreus'],
    'tg': ['jas', 'tiago'],                 # Tiago
    'jas': ['tg', 'tiago'],
    '1pe': ['1pt', '1pedro'],               # 1 Pedro
    '1pt': ['1pe', '1pedro'],
    '2pe': ['2pt', '2pedro'],               # 2 Pedro
    '2pt': ['2pe', '2pedro'],
    '1jo': ['1jn', '1joao'],                # 1 João
    '1jn': ['1jo', '1joao'],
    '2jo': ['2jn', '2joao'],                # 2 João
    '2jn': ['2jo', '2joao'],
    '3jo': ['3jn', '3joao'],                # 3 João
    '3jn': ['3jo', '3joao'],
    'jd': ['jude', 'judas'],                # Judas
    'jude': ['jd', 'judas'],
    'ap': ['rev', 'apocalipse'],            # Apocalipse
    'rev': ['ap', 'apocalipse'],
}


def get_book_by_abbrev(translation, abbrev):
    """Retorna um livro específico pela abreviação."""
    bible = load_bible(translation)
    abbrev_lower = abbrev.lower()

    # Primeiro, tenta encontrar pela abreviação exata
    for book in bible:
        if book.get('abbrev', '').lower() == abbrev_lower:
            return book

    # Se não encontrou, tenta pelas abreviações alternativas
    aliases = ABBREV_ALIASES.get(abbrev_lower, [])
    for alias in aliases:
        for book in bible:
            if book.get('abbrev', '').lower() == alias.lower():
                return book

    return None


def search_bible(translation, query, limit=50):
    """Busca versículos por texto."""
    bible = load_bible(translation)
    results = []
    query_lower = query.lower()

    for book in bible:
        book_abbrev = book.get('abbrev', '')
        book_name = get_book_name(book_abbrev)
        chapters = book.get('chapters', [])

        for chapter_idx, chapter in enumerate(chapters):
            for verse_idx, verse in enumerate(chapter):
                if query_lower in verse.lower():
                    results.append({
                        'book_abbrev': book_abbrev,
                        'book_name': book_name,
                        'chapter': chapter_idx + 1,
                        'verse': verse_idx + 1,
                        'text': verse,
                        'reference': f'{book_name} {chapter_idx + 1}:{verse_idx + 1}'
                    })
                    if len(results) >= limit:
                        return results
    return results


def parse_reference(reference):
    """Parseia uma referência bíblica como 'João 3:16' ou 'Jo 3:16-18'."""
    metadata = load_bible_metadata()

    # Padrões: "João 3:16", "Jo 3:16", "João 3:16-18", "João 3"
    pattern = r'^(.+?)\s*(\d+)(?::(\d+)(?:-(\d+))?)?$'
    match = re.match(pattern, reference.strip())

    if not match:
        return None

    book_input = match.group(1).strip().lower()
    chapter = int(match.group(2))
    verse_start = int(match.group(3)) if match.group(3) else None
    verse_end = int(match.group(4)) if match.group(4) else verse_start

    # Encontra o livro pela abreviação ou nome
    book_abbrev = None
    for book in metadata.get('books', []):
        if book['abbrev'].lower() == book_input or book['name'].lower() == book_input:
            book_abbrev = book['abbrev']
            break

    if not book_abbrev:
        # Tenta match parcial
        for book in metadata.get('books', []):
            if book_input in book['name'].lower() or book['name'].lower().startswith(book_input):
                book_abbrev = book['abbrev']
                break

    if not book_abbrev:
        return None

    return {
        'book_abbrev': book_abbrev,
        'chapter': chapter,
        'verse_start': verse_start,
        'verse_end': verse_end
    }


# --- Rotas da Bíblia ---

@bible_bp.route('/bible')
@login_required
def bible_home():
    """Página principal da Bíblia."""
    metadata = load_bible_metadata()
    translation = request.args.get('translation') or get_preferred_translation()

    # Separa livros por testamento
    old_testament = [b for b in metadata.get('books', []) if b.get('testament') == 'old']
    new_testament = [b for b in metadata.get('books', []) if b.get('testament') == 'new']

    return render_template('bible.html',
                         old_testament=old_testament,
                         new_testament=new_testament,
                         translations=metadata.get('translations', {}),
                         current_translation=translation)

@bible_bp.route('/bible/<book_abbrev>')
@login_required
def bible_book(book_abbrev):
    """Exibe os capítulos de um livro."""
    translation = request.args.get('translation') or get_preferred_translation()
    book = get_book_by_abbrev(translation, book_abbrev)

    if not book:
        flash('Livro não encontrado!', 'error')
        return redirect(url_for('bible.bible_home'))

    metadata = load_bible_metadata()
    book_name = get_book_name(book_abbrev)
    num_chapters = len(book.get('chapters', []))

    return render_template('bible_book.html',
                         book_abbrev=book_abbrev,
                         book_name=book_name,
                         num_chapters=num_chapters,
                         translations=metadata.get('translations', {}),
                         current_translation=translation)

@bible_bp.route('/bible/<book_abbrev>/<int:chapter>')
@login_required
def bible_chapter(book_abbrev, chapter):
    """Exibe os versículos de um capítulo."""
    translation = request.args.get('translation') or get_preferred_translation()
    book = get_book_by_abbrev(translation, book_abbrev)

    if not book:
        flash('Livro não encontrado!', 'error')
        return redirect(url_for('bible.bible_home'))

    chapters = book.get('chapters', [])
    if chapter < 1 or chapter > len(chapters):
        flash('Capítulo não encontrado!', 'error')
        return redirect(url_for('bible.bible_book', book_abbrev=book_abbrev))

    metadata = load_bible_metadata()
    book_name = get_book_name(book_abbrev)
    verses = chapters[chapter - 1]

    # Navegação entre capítulos
    prev_chapter = chapter - 1 if chapter > 1 else None
    next_chapter = chapter + 1 if chapter < len(chapters) else None

    return render_template('bible_chapter.html',
                         book_abbrev=book_abbrev,
                         book_name=book_name,
                         chapter=chapter,
                         verses=verses,
                         num_chapters=len(chapters),
                         prev_chapter=prev_chapter,
                         next_chapter=next_chapter,
                         translations=metadata.get('translations', {}),
                         current_translation=translation,
                         translation_abbrev=get_translation_abbrev(translation),
                         translation_name=get_translation_name(translation))

@bible_bp.route('/api/bible/search')
@login_required
def api_bible_search():
    """API para busca de versículos."""
    query = request.args.get('q', '')
    # Sem translation na URL, usa a preferida salva (não trava em 'acf') —
    # é o mesmo default que /bible, /bible/<livro> e /bible/<livro>/<cap>
    # já usam; sem isso a busca do /lyrics ignorava a tradução escolhida
    # pelo operador em outra página.
    translation = request.args.get('translation') or get_preferred_translation()
    translation_abbrev = get_translation_abbrev(translation)
    translation_name = get_translation_name(translation)

    if len(query) < 3:
        return jsonify({'error': 'Busca deve ter pelo menos 3 caracteres', 'results': []})

    # Primeiro tenta como referência
    ref = parse_reference(query)
    if ref:
        book = get_book_by_abbrev(translation, ref['book_abbrev'])
        if book:
            chapters = book.get('chapters', [])
            chapter_idx = ref['chapter'] - 1
            if 0 <= chapter_idx < len(chapters):
                verses = chapters[chapter_idx]
                results = []
                book_name = get_book_name(ref['book_abbrev'])

                if ref['verse_start']:
                    # Versículos específicos
                    start = ref['verse_start'] - 1
                    end = ref['verse_end'] if ref['verse_end'] else ref['verse_start']
                    for i in range(start, min(end, len(verses))):
                        results.append({
                            'book_abbrev': ref['book_abbrev'],
                            'book_name': book_name,
                            'chapter': ref['chapter'],
                            'verse': i + 1,
                            'text': verses[i],
                            'reference': f'{book_name} {ref["chapter"]}:{i + 1}'
                        })
                else:
                    # Capítulo inteiro
                    for i, verse in enumerate(verses):
                        results.append({
                            'book_abbrev': ref['book_abbrev'],
                            'book_name': book_name,
                            'chapter': ref['chapter'],
                            'verse': i + 1,
                            'text': verse,
                            'reference': f'{book_name} {ref["chapter"]}:{i + 1}'
                        })

                return jsonify({'results': results, 'type': 'reference',
                                 'translation': translation, 'translation_abbrev': translation_abbrev,
                                 'translation_name': translation_name})

    # Busca por texto
    results = search_bible(translation, query)
    return jsonify({'results': results, 'type': 'text',
                     'translation': translation, 'translation_abbrev': translation_abbrev,
                     'translation_name': translation_name})

@bible_bp.route('/api/bible/verse')
@login_required
def api_bible_verse():
    """API para obter versículos específicos."""
    translation = request.args.get('translation') or get_preferred_translation()
    book_abbrev = request.args.get('book')
    chapter = request.args.get('chapter', type=int)
    verse_start = request.args.get('verse_start', type=int)
    verse_end = request.args.get('verse_end', type=int, default=None)

    if not all([book_abbrev, chapter, verse_start]):
        return jsonify({'error': 'Parâmetros inválidos'}), 400

    book = get_book_by_abbrev(translation, book_abbrev)
    if not book:
        return jsonify({'error': 'Livro não encontrado'}), 404

    chapters = book.get('chapters', [])
    if chapter < 1 or chapter > len(chapters):
        return jsonify({'error': 'Capítulo não encontrado'}), 404

    verses = chapters[chapter - 1]
    book_name = get_book_name(book_abbrev)

    if verse_end is None:
        verse_end = verse_start

    result_verses = []
    for i in range(verse_start - 1, min(verse_end, len(verses))):
        result_verses.append({
            'verse': i + 1,
            'text': verses[i]
        })

    reference = f'{book_name} {chapter}:{verse_start}'
    if verse_end and verse_end != verse_start:
        reference += f'-{verse_end}'

    return jsonify({
        'book_abbrev': book_abbrev,
        'book_name': book_name,
        'chapter': chapter,
        'verses': result_verses,
        'reference': reference,
        'translation': translation,
        'translation_abbrev': get_translation_abbrev(translation),
        'translation_name': get_translation_name(translation)
    })

# Evento WebSocket para transmitir versículos da Bíblia
@socketio.on('update_bible')
def handle_update_bible(data):
    logger.debug(f'📖 Recebido update_bible: {data.get("reference", "Sem referência")}')
    ref = data.get('reference') or str(data.get('text', ''))[:60]
    if ref:
        append_display_log({'type': 'bible', 'title': ref})
    emit('update_bible', data, broadcast=True)

@bible_bp.route('/bible/display')
def bible_display():
    """Página de exibição da Bíblia para projeção."""
    return render_template('bible_display.html')

@bible_bp.route('/api/bible/add_to_order', methods=['POST'])
@login_required
def api_bible_add_to_order():
    """Adiciona uma passagem bíblica à ordem do culto de hoje."""
    data = request.get_json()
    reference = data.get('reference', '').strip()

    if not reference:
        return jsonify({'success': False, 'error': 'Referência vazia'})

    today = date.today().isoformat()
    order = get_order(today)
    itens = list(order.get('itens') or [])

    itens.append({
        'isBible': True,
        'reference': reference,
        'title': f'📖 {reference}'
    })
    order['itens'] = itens
    save_order(today, order)

    return jsonify({
        'success': True,
        'url': generate_bible_url(reference),
        'date': today,
        'message': f"Adicionado à ordem de hoje ({date.today().strftime('%d/%m')})",
    })

@bible_bp.route('/api/bible/remove_from_order', methods=['POST'])
@login_required
def api_bible_remove_from_order():
    """Remove uma passagem bíblica da ordem do culto de hoje."""
    data = request.get_json()
    reference = data.get('reference', '').strip()

    if not reference:
        return jsonify({'success': False, 'error': 'Referência vazia'})

    today = date.today().isoformat()
    order = get_order(today)
    itens = list(order.get('itens') or [])

    original_len = len(itens)
    itens = [item for item in itens if not (item.get('isBible') and item.get('reference') == reference)]

    if len(itens) == original_len:
        return jsonify({'success': False, 'error': 'Passagem não encontrada na ordem de hoje'})

    if itens:
        order['itens'] = itens
    else:
        order.pop('itens', None)
    save_order(today, order)

    return jsonify({'success': True})

@bible_bp.route('/bible/control/')
@login_required
def bible_control_list():
    """Lista de passagens bíblicas da ordem do culto de hoje."""
    today = date.today().isoformat()
    order = get_order(today)
    bible_items = [item for item in (order.get('itens') or []) if item.get('isBible')]

    return render_template('bible_control_list.html', bible_items=bible_items)

@bible_bp.route('/api/bible/set_translation', methods=['POST'])
@login_required
def api_set_bible_translation():
    """Salva a tradução preferida da Bíblia."""
    data = request.get_json()
    translation = data.get('translation', 'acf')
    set_preferred_translation(translation)
    return jsonify({'success': True, 'translation': translation})

@bible_bp.route('/bible/control/<book_abbrev>/<int:chapter>')
@bible_bp.route('/bible/control/<book_abbrev>/<int:chapter>/<int:verse_start>')
@bible_bp.route('/bible/control/<book_abbrev>/<int:chapter>/<int:verse_start>-<int:verse_end>')
@login_required
def bible_control(book_abbrev, chapter, verse_start=None, verse_end=None):
    """Página de controle de passagem bíblica (similar ao /lyrics/)."""
    translation = request.args.get('translation') or get_preferred_translation()

    book = get_book_by_abbrev(translation, book_abbrev)
    if not book:
        return "Livro não encontrado", 404

    chapters = book.get('chapters', [])
    if chapter < 1 or chapter > len(chapters):
        return "Capítulo não encontrado", 404

    verses = chapters[chapter - 1]
    book_name = get_book_name(book_abbrev)
    metadata = load_bible_metadata()

    # Navegação entre capítulos
    prev_chapter = chapter - 1 if chapter > 1 else None
    next_chapter = chapter + 1 if chapter < len(chapters) else None

    # Carrega passagens bíblicas da ordem do culto de hoje
    today = date.today().isoformat()
    order = get_order(today)
    bible_items = []
    for item in (order.get('itens') or []):
        if item.get('isBible'):
            # Gera URL a partir da referência se não existir
            if not item.get('url'):
                item['url'] = generate_bible_url(item.get('reference', ''))
            bible_items.append(item)

    # Estado real de visibilidade — mesma fonte única de verdade que
    # /lyrics/<id> usa (LyricsState.visible), não assume True. As duas
    # páginas mandam pro mesmo lugar (tela pública), então precisam
    # concordar sobre o estado, não cada uma assumir o seu.
    lyrics_state = LyricsState.query.first()
    lyrics_visible = lyrics_state.visible if lyrics_state else True

    return render_template('bible_control.html',
        book_abbrev=book_abbrev,
        book_name=book_name,
        chapter=chapter,
        verses=verses,
        num_chapters=len(chapters),
        prev_chapter=prev_chapter,
        next_chapter=next_chapter,
        translations=metadata.get('translations', {}),
        current_translation=translation,
        translation_abbrev=get_translation_abbrev(translation),
        translation_name=get_translation_name(translation),
        initial_verse=verse_start,
        verse_end=verse_end,
        bible_items=bible_items,
        lyrics_visible=lyrics_visible
    )
