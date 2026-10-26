// Em português, os nomes de sempre; nos outros idiomas, os do navegador
const ucPt = ucLocale().startsWith('pt');
const weekdayShort = ucPt ? ['DOM','SEG','TER','QUA','QUI','SEX','SÁB']
    : Array.from({ length: 7 }, (x, i) => new Date(2000, 0, 2 + i).toLocaleDateString(ucLocale(), { weekday: 'short' }).toUpperCase());
const monthLong = ucPt ? ['janeiro','fevereiro','março','abril','maio','junho','julho','agosto','setembro','outubro','novembro','dezembro']
    : Array.from({ length: 12 }, (x, i) => new Date(2000, i, 1).toLocaleDateString(ucLocale(), { month: 'long' }));
let ordersData = {};
let currentMonth = new Date();

function buildHead() {
    const head = document.getElementById('calendarHead');
    head.innerHTML = weekdayShort.map(w => `<div>${w}</div>`).join('');
}

function formatDateISO(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth()+1).padStart(2,'0');
    const day = String(d.getDate()).padStart(2,'0');
    return `${y}-${m}-${day}`;
}

function renderCalendar() {
    const calendar = document.getElementById('calendar');
    const empty = document.getElementById('emptyState');
    const year = currentMonth.getFullYear();
    const month = currentMonth.getMonth();
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month+1, 0);
    const startWeekday = firstDay.getDay(); // 0 domingo
    const totalDays = lastDay.getDate();

    document.getElementById('monthLabel').textContent = _t('{mes} de {ano}', { mes: monthLong[month], ano: year });

    const days = AgendaCultos.groupByDay(ordersData);
    const cells = [];
    // espaços em branco antes do 1
    for (let i=0; i<startWeekday; i++) cells.push({ blank:true });
    for (let d=1; d<=totalDays; d++) cells.push({ dateStr: formatDateISO(new Date(year, month, d)), day: d });

    calendar.innerHTML = cells.map(cell => {
        if (cell.blank) return `<div class="day" style="background:transparent; border:none;"></div>`;

        const day = days[cell.dateStr];
        const todayCls = cell.dateStr === formatDateISO(new Date()) ? ' today' : '';
        const inner = AgendaCultos.dayCellInner(String(cell.day).padStart(2,'0'), day);
        if (!AgendaCultos.dayItems(day).length) return `<div class="day${todayCls}">${inner}</div>`;
        return `<div class="day has-data${todayCls}" onclick="window.location='/agenda/${cell.dateStr}'">${inner}</div>`;
    }).join('');
}

async function loadOrders() {
    try {
        const resp = await fetch('/api/orders');
        ordersData = await resp.json();
        renderCalendar();
    } catch (e) {
        const calendar = document.getElementById('calendar');
        const empty = document.getElementById('emptyState');
        calendar.style.display = 'none';
        empty.style.display = 'block';
        empty.textContent = _t('Erro ao carregar agenda');
    }
}

document.getElementById('prevBtn').addEventListener('click', () => {
    currentMonth = new Date(currentMonth.getFullYear(), currentMonth.getMonth()-1, 1);
    renderCalendar();
});
document.getElementById('nextBtn').addEventListener('click', () => {
    currentMonth = new Date(currentMonth.getFullYear(), currentMonth.getMonth()+1, 1);
    renderCalendar();
});

buildHead();
loadOrders();
