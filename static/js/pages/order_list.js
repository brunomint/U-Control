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
    select.innerHTML = merged.map(v => `<option value="${v}">${v || 'Todos'}</option>`).join('');
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
        resultsInfo.textContent = 'Nenhum resultado para os filtros.';
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
    pageInfo.textContent = `Página ${currentPage} de ${totalPages}`;
    resultsInfo.textContent = `Exibindo ${Math.min(end, total)} de ${total} ordens`;
}

function clearFilters() {
    document.getElementById('filterDateFrom').value = '';
    document.getElementById('filterDateTo').value = '';
    document.getElementById('filterType').value = '';
    document.getElementById('filterStatus').value = '';
    document.getElementById('filterText').value = '';
    applyFilters();
}

const weekdays = ['Domingo', 'Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sábado'];
const months = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

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

function createOrderCard(dateStr, order) {
    const date = formatDate(dateStr);
    const stats = countItems(order.itens || []);
    const today = isToday(dateStr);
    const past = isPast(dateStr);

    let headerClass = '';
    let badge = '';
    if (today) {
        headerClass = 'today';
        badge = '🔴 HOJE';
    } else if (past) {
        headerClass = 'past';
        badge = 'Passado';
    } else {
        badge = 'Agendado';
    }

    return `
        <div class="order-card" data-date="${dateStr}">
            <div class="card-header ${headerClass}">
                <div class="card-date">${date.day} ${date.month}</div>
                <div class="card-weekday">${date.weekday} • ${order.horario || '18:40'}</div>
                <div class="card-badge">${badge}</div>
            </div>
            <div class="card-body">
                <div class="card-tipo">${order.tipo || 'Culto'}</div>

                <div class="card-info">
                    ${order.dirigente ? `<div class="card-info-item">👤 <strong>Dirigente:</strong> ${order.dirigente}</div>` : ''}
                    ${order.pregador ? `<div class="card-info-item">🎤 <strong>Pregador:</strong> ${order.pregador}</div>` : ''}
                    ${order.tema ? `<div class="card-info-item">📝 <strong>Tema:</strong> ${order.tema}</div>` : ''}
                </div>

                <div class="card-stats">
                    <div class="stat-item">
                        <div class="stat-number">${stats.musicas}</div>
                        <div class="stat-label">Músicas</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-number">${stats.biblia}</div>
                        <div class="stat-label">Bíblia</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-number">${stats.total}</div>
                        <div class="stat-label">Total</div>
                    </div>
                </div>

                <div class="card-actions">
                    <a href="/order/${dateStr}" class="card-btn secondary">✏️ Editar</a>
                    <a href="/view/order/${dateStr}" class="card-btn primary">👁️ Visualizar</a>
                    <a href="/view?order=${dateStr}" class="card-btn primary" title="Abrir cifras">🎵 Cifras</a>
                    <button class="card-btn secondary" onclick="copyLink('${dateStr}')" title="Copiar link">🔗</button>
                </div>
            </div>
        </div>
    `;
}

function copyLink(dateStr) {
    const url = `${window.location.origin}/view/order/${dateStr}`;
    navigator.clipboard.writeText(url).then(() => {
        showToast('Link copiado para a área de transferência!');
    }).catch(() => {
        // Fallback para navegadores antigos
        const input = document.createElement('input');
        input.value = url;
        document.body.appendChild(input);
        input.select();
        document.execCommand('copy');
        document.body.removeChild(input);
        showToast('Link copiado!');
    });
}

function showToast(message) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.classList.add('show');
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

async function loadOrders() {
    try {
        const response = await fetch('/api/orders');
        allOrders = await response.json();
        populateTypeOptions();
        applyFilters();
    } catch (error) {
        console.error('Erro ao carregar ordens:', error);
        showToast('Erro ao carregar ordens de culto');
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
