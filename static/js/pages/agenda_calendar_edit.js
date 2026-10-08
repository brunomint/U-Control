const weekdayShort = ['DOM','SEG','TER','QUA','QUI','SEX','SÁB'];
const monthLong = ['janeiro','fevereiro','março','abril','maio','junho','julho','agosto','setembro','outubro','novembro','dezembro'];
let ordersData = {};
let currentMonth = new Date();

function hasOrderData(o) {
    if (!o || typeof o !== 'object') return false;
    const hasMain = (val) => typeof val === 'string' && val.trim() !== '';
    const hasArray = (arr) => Array.isArray(arr) && arr.length > 0;

    const hasTipo = hasMain(o.tipo);
    const hasOther = hasMain(o.horario) || hasMain(o.dirigente) || hasMain(o.pregador) || hasMain(o.tema);

    if (hasOther) return true;
    if (hasArray(o.eventos)) return true;
    if (hasArray(o.itens)) return true;
    if (o.louvor && (hasArray(o.louvor.musicos) || hasArray(o.louvor.cantores))) return true;
    if (o.midia && (hasMain(o.midia.lider) || hasMain(o.midia.palco) || hasMain(o.midia.visual) || hasArray(o.midia.equipe) || hasArray(o.midia.extras) || hasMain(o.midia.obs))) return true;

    // Se só o tipo estiver preenchido e nada mais, considera como vazio
    if (hasTipo && !hasOther && !hasArray(o.eventos) && !hasArray(o.itens)) return false;

    return hasTipo;
}

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
    const startWeekday = firstDay.getDay();
    const totalDays = lastDay.getDate();
    const monthText = `${monthLong[month]} de ${year}`;

    document.getElementById('monthLabel').textContent = monthText;
    const inner = document.getElementById('monthLabelInner');
    if (inner) inner.textContent = monthText;

    const cells = [];
    // espaços em branco antes do 1
    for (let i=0; i<startWeekday; i++) cells.push({ blank:true });
    for (let d=1; d<=totalDays; d++) {
        const dateStr = formatDateISO(new Date(year, month, d));
        const order = ordersData[dateStr] || {};
        const hasData = hasOrderData(order);
        cells.push({ dateStr, hasData, order });
    }

    calendar.innerHTML = cells.map(cell => {
        if (cell.blank) return `<div class="day" style="background:transparent; border:none;"></div>`;

        const o = cell.order || {};
        const dayNumber = String(new Date(cell.dateStr + 'T00:00:00').getDate()).padStart(2,'0');
        const todayCls = cell.dateStr === formatDateISO(new Date()) ? ' today' : '';

        const items = [];

        // LOUVOR
        if (o.tipo?.trim() &&
            (o.horario_culto || o.dirigente || o.pregador)
        ) {
            items.push({
                tipoItem: 'louvor',
                titulo: o.tipo,
                hora: o.horario_culto || '',
                dirigente: o.dirigente || '',
                pregador: o.pregador || '',
                prioridade: 0
            });
        }

        // EVENTOS
        if (Array.isArray(o.eventos)) {
            o.eventos.forEach(ev => {
                if (ev?.titulo) {
                    items.push({
                        tipoItem: 'evento',
                        titulo: ev.titulo,
                        hora: ev.hora || '',
                        responsavel: ev.responsavel || '',
                        obs: ev.obs || '',
                        prioridade: 1
                    });
                }
            });
        }

        // ordenar: louvor primeiro, depois horário crescente
        items.sort((a,b)=>{
            if (a.prioridade !== b.prioridade) return a.prioridade - b.prioridade;
            return (a.hora || '').localeCompare(b.hora || '');
        });

        if (items.length === 0) {
            return `
                <div class="day clickable${todayCls}" data-date="${cell.dateStr}">
                    <div class="day-top">
                        <div class="day-date">${dayNumber}</div>
                    </div>
                    <div class="day-body">
                        <div class="info-line muted">Sem eventos</div>
                    </div>
                </div>
            `;
        }

        const total = items.length;

        let mode;
        let visible = [];
        let hidden = 0;

        /*
        MODOS:
        detailed  → 1 item (mostra detalhes + hora)
        compact   → até 2 (mostra hora)
        overflow  → 3+ (esconde hora)
        */

        if (total === 1) {
            mode = 'detailed';
            visible = items;
        }
        else if (total <= 2) {
            mode = 'compact';
            visible = items;
        }
        else {
            mode = 'overflow';
            visible = items.slice(0, 3);
            hidden = total - 3;
        }

        const isSingle = mode === 'detailed';
        const showTime = mode !== 'overflow';

        const lines = visible.map(it => {

            const tituloClass = it.tipoItem === 'louvor'
                ? 'tipo-pill'
                : 'eventos-pill';

            const timeClass = it.tipoItem === 'louvor'
                ? 'time-pill-tipo'
                : 'time-pill-eventos';

            let extraInfo = '';
            // 🔹 detalhes apenas quando item único
            if (isSingle) {

                if (it.tipoItem === 'louvor') {
                    extraInfo = `
                        ${it.dirigente ? `
                            <div class="meta-line">
                                <span class="meta-label">Dirigente:</span>
                                <span class="meta-value">${it.dirigente}</span>
                            </div>` : ''}
                        ${it.pregador ? `
                            <div class="meta-line">
                                <span class="meta-label">Pregador:</span>
                                <span class="meta-value">${it.pregador}</span>
                            </div>` : ''}
                    `;
                }
                if (it.tipoItem === 'evento') {
                    extraInfo = `
                        ${it.responsavel ? `
                            <div class="meta-line">
                                <span class="meta-label">Resp:</span>
                                <span class="meta-value">${it.responsavel}</span>
                            </div>` : ''}
                        ${it.obs ? `
                            <div class="meta-line">
                                <span class="meta-label">Obs:</span>
                                <span class="meta-value">${it.obs}</span>
                            </div>` : ''}
                    `;
                }
            }
            return `
                <div class="day-item">
                    <span class="pill ${tituloClass}">${it.titulo}</span>
                    ${(it.hora && showTime) ? `<span class="pill ${timeClass}">${it.hora}</span>` : ''}
                    ${extraInfo}
                </div>
            `;
        }).join('');

        let button = '';

        if (hidden > 0) {
            button = `<div class="day-footer"><span class="tag">+${hidden} ver detalhes</span></div>`;
        } else if (items.length >= 2) {
            button = `<div class="day-footer"><span class="tag">Mais detalhes</span></div>`;
        }

        return `
            <div class="day clickable${todayCls}" data-date="${cell.dateStr}">
                <div class="day-top">
                    <div class="day-date">${dayNumber}</div>
                </div>
                <div class="day-body">
                    ${lines}
                </div>
                ${button}
            </div>
        `;
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
        empty.textContent = 'Erro ao carregar agenda';
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

document.getElementById('saveImgBtn').addEventListener('click', async () => {
    const calendarShell = document.querySelector('.card.calendar-shell');
    if (!calendarShell) return;
    const label = document.getElementById('monthLabel')?.textContent || 'agenda';
    const safeLabel = label.toLowerCase().replace(/\s+/g, '-');
    try {
        calendarShell.classList.add('capturing');
        const canvas = await html2canvas(calendarShell, {
            backgroundColor: '#161a2b',
            scale: 2,
            useCORS: true,
        });
        const link = document.createElement('a');
        link.download = `${safeLabel}.png`;
        link.href = canvas.toDataURL('image/png');
        link.click();
        calendarShell.classList.remove('capturing');
    } catch (err) {
        calendarShell.classList.remove('capturing');
        console.error('Erro ao salvar imagem do calendário:', err);
        alert('Não foi possível salvar o calendário como imagem.');
    }
});
document.addEventListener('click', e => {
    const day = e.target.closest('.clickable');
    if (!day) return;

    const date = day.dataset.date;
    window.location = `/agenda/${date}/admin`;
});
buildHead();
loadOrders();
