// ---- Filtros e paginação ----
let allOrders = {};
let filteredDates = [];
const pageSize = 12;
let currentPage = 1;

function populateTypeOptions() {
    const select = document.getElementById('filterType');
    const baseOptions = [
        '',
        'Culto Dominical','Culto de Oração','Culto de Jovens','Culto de Ensino','Culto Santa Ceia','Culto Especial','Outro'
    ];
    const dynamic = new Set();
    Object.values(allOrders || {}).forEach(o => {
        if (o && o.tipo) dynamic.add(o.tipo);
    });
    const merged = Array.from(new Set([...baseOptions, ...dynamic]));
    select.innerHTML = merged.map(v => `<option value="${v}">${v || _t('Todos')}</option>`).join('');
}

function applyFilters() {
    const dates = Object.keys(allOrders);
    const from = document.getElementById('filterDateFrom').value;
    const to = document.getElementById('filterDateTo').value;
    const tipo = document.getElementById('filterType').value;
    const status = document.getElementById('filterStatus').value;
    const text = document.getElementById('filterText').value.trim().toLowerCase();

    const now = new Date();
    const todayStr = now.getFullYear() + '-' + String(now.getMonth()+1).padStart(2,'0') + '-' + String(now.getDate()).padStart(2,'0');

    filteredDates = dates.filter(d => {
        const order = allOrders[d] || {};
        // Por padrão, só mostra hoje e futuros (a menos que filtro de status diga o contrário)
        if (!status && !from && d < todayStr) return false;

        if (from && d < from) return false;
        if (to && d > to) return false;
        if (tipo && (order.tipo || '') !== tipo) return false;

        if (status) {
            const isPastFlag = isPast(d);
            const isTodayFlag = isToday(d);
            if (status === 'passado' && !(isPastFlag && !isTodayFlag)) return false;
            if (status === 'hoje' && !isTodayFlag) return false;
            if (status === 'futuro' && (isPastFlag || isTodayFlag)) return false;
        }

        if (text) {
            const dir = (order.dirigente || '').toLowerCase();
            const pre = (order.pregador || '').toLowerCase();
            if (!dir.includes(text) && !pre.includes(text)) return false;
        }
        return true;
    }).sort((a, b) => a.localeCompare(b));

    currentPage = 1;
    renderGrid();
}

function renderGrid() {
    const grid = document.getElementById('ordersGrid');
    const emptyState = document.getElementById('emptyState');
    const pagination = document.getElementById('pagination');
    const resultsInfo = document.getElementById('resultsInfo');
    const pageInfo = document.getElementById('pageInfo');

    if (filteredDates.length === 0) {
        grid.innerHTML = '';
        emptyState.style.display = 'block';
        pagination.style.display = 'none';
        resultsInfo.textContent = _t('Nenhum resultado para os filtros.');
        return;
    }

    const total = filteredDates.length;
    const totalPages = Math.max(1, Math.ceil(total / pageSize));
    if (currentPage > totalPages) currentPage = totalPages;
    const start = (currentPage - 1) * pageSize;
    const end = start + pageSize;
    const pageDates = filteredDates.slice(start, end);

    grid.innerHTML = pageDates.map(date => createOrderCard(date, allOrders[date])).join('');
    emptyState.style.display = 'none';

    pagination.style.display = totalPages > 1 ? 'flex' : 'none';
    document.getElementById('prevPage').disabled = currentPage === 1;
    document.getElementById('nextPage').disabled = currentPage === totalPages;
    pageInfo.textContent = _t('Página {atual} de {total}', { atual: currentPage, total: totalPages });
    resultsInfo.textContent = _t('Exibindo {n} de {total} ordens', { n: Math.min(end, total), total });
}

function clearFilters() {
    document.getElementById('filterDateFrom').value = '';
    document.getElementById('filterDateTo').value = '';
    document.getElementById('filterType').value = '';
    document.getElementById('filterStatus').value = '';
    document.getElementById('filterText').value = '';
    applyFilters();
}

const weekdays = [_t('Domingo'), _t('Segunda-feira'), _t('Terça-feira'), _t('Quarta-feira'), _t('Quinta-feira'), _t('Sexta-feira'), _t('Sábado')];
const months = [_t('Jan'), _t('Fev'), _t('Mar'), _t('Abr'), _t('Mai'), _t('Jun'), _t('Jul'), _t('Ago'), _t('Set'), _t('Out'), _t('Nov'), _t('Dez')];

function formatDate(dateStr) {
    const [year, month, day] = dateStr.split('-');
    const date = new Date(year, month - 1, day);
    return {
        day: day,
        month: months[date.getMonth()],
        year: year,
        weekday: weekdays[date.getDay()],
        full: `${day}/${month}/${year}`
    };
}

function isToday(dateStr) {
    const today = new Date();
    const [year, month, day] = dateStr.split('-');
    return today.getFullYear() === parseInt(year) &&
           today.getMonth() === parseInt(month) - 1 &&
           today.getDate() === parseInt(day);
}

function isPast(dateStr) {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const [year, month, day] = dateStr.split('-');
    const date = new Date(year, month - 1, day);
    return date < today;
}

function countItems(itens) {
    let musicas = 0;
    let biblia = 0;
    let outros = 0;

    itens.forEach(item => {
        if (item.isBible) {
            biblia++;
        } else if (item.url && item.url.includes('/lyrics/')) {
            musicas++;
        } else {
            outros++;
        }
    });

    return { musicas, biblia, outros, total: itens.length };
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}

function createOrderCard(dateStr, order) {
    const date = formatDate(dateStr);
    const stats = countItems(order.itens || []);
    const today = isToday(dateStr);
    const past = isPast(dateStr);

    let state = 'future';
    let badge = '<span class="uc-pill uc-pill-muted">' + _t('Agendado') + '</span>';
    if (today) {
        state = 'today';
        badge = '<span class="uc-pill uc-pill-live"><span class="dot"></span>' + _t('Hoje') + '</span>';
    } else if (past) {
        state = 'past';
        badge = '<span class="uc-pill uc-pill-muted">' + _t('Passado') + '</span>';
    }

    const people = [
        order.dirigente && `<span><b>${_t('Dirigente')}</b> ${escapeHtml(order.dirigente)}</span>`,
        order.pregador && `<span><b>${_t('Pregação')}</b> ${escapeHtml(order.pregador)}</span>`,
        order.tema && `<span><b>${_t('Tema')}</b> ${escapeHtml(order.tema)}</span>`,
    ].filter(Boolean).join('');

    const horario = order.horario_culto || order.horario || '';

    return `
        <article class="uc-card order-card ${state}" data-date="${dateStr}">
            <div class="order-top">
                <div class="order-date">
                    <span class="day">${date.day}</span>
                    <span class="month">${date.month}</span>
                </div>
                <div class="order-head">
                    <div class="order-tipo">${escapeHtml(order.tipo || _t('Culto'))}</div>
                    <div class="order-when">${date.weekday}${horario ? ` · ${escapeHtml(horario)}` : ''}</div>
                </div>
                ${badge}
            </div>
            ${people ? `<div class="order-people">${people}</div>` : ''}
            <div class="order-stats">
                <span><i class="fas fa-music"></i> ${stats.musicas === 1 ? _t('1 música') : _t('{n} músicas', { n: stats.musicas })}</span>
                <span><i class="fas fa-book-bible"></i> ${stats.biblia === 1 ? _t('1 leitura') : _t('{n} leituras', { n: stats.biblia })}</span>
                <span><i class="fas fa-list"></i> ${_t('{n} no total', { n: stats.total })}</span>
            </div>
            <div class="order-actions">
                <a href="/order/${dateStr}" class="uc-btn uc-btn-secondary uc-btn-sm"><i class="fas fa-pen"></i> ${_t('Editar')}</a>
                <a href="/view/order/${dateStr}" class="uc-btn uc-btn-ghost uc-btn-sm"><i class="fas fa-eye"></i> ${_t('Ver')}</a>
                <a href="/view?order=${dateStr}" class="uc-btn uc-btn-ghost uc-btn-sm" title="${_t('Abrir as cifras desta ordem')}"><i class="fas fa-guitar"></i> ${_t('Cifras')}</a>
                <button type="button" class="uc-btn uc-btn-ghost uc-btn-sm" onclick="copyLink('${dateStr}')" title="${_t('Copiar link público da ordem')}" aria-label="${_t('Copiar link')}"><i class="fas fa-link"></i></button>
            </div>
        </article>
    `;
}

function copyLink(dateStr) {
    const url = `${window.location.origin}/view/order/${dateStr}`;
    navigator.clipboard.writeText(url).then(() => {
        showToast(_t('Link copiado para a área de transferência!'));
    }).catch(() => {
        // Fallback para navegadores antigos
        const input = document.createElement('input');
        input.value = url;
        document.body.appendChild(input);
        input.select();
        document.execCommand('copy');
        document.body.removeChild(input);
        showToast(_t('Link copiado!'));
    });
}

function showToast(message, type) {
    window.ucToast(message, type);
}

async function loadOrders() {
    try {
        const response = await fetch('/api/orders');
        allOrders = await response.json();
        populateTypeOptions();
        applyFilters();
    } catch (error) {
        console.error('Erro ao carregar ordens:', error);
        showToast(_t('Erro ao carregar as ordens de culto'), 'error');
    }
}

document.getElementById('filterDateFrom').addEventListener('change', applyFilters);
document.getElementById('filterDateTo').addEventListener('change', applyFilters);
document.getElementById('filterType').addEventListener('change', applyFilters);
document.getElementById('filterStatus').addEventListener('change', applyFilters);
document.getElementById('filterText').addEventListener('input', () => {
    clearTimeout(window.__filterTextTimeout);
    window.__filterTextTimeout = setTimeout(applyFilters, 200);
});
document.getElementById('clearFilters').addEventListener('click', clearFilters);
document.getElementById('prevPage').addEventListener('click', () => { currentPage = Math.max(1, currentPage - 1); renderGrid(); });
document.getElementById('nextPage').addEventListener('click', () => { currentPage = currentPage + 1; renderGrid(); });

document.addEventListener('DOMContentLoaded', loadOrders);
