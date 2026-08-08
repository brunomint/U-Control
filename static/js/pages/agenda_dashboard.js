async function loadOrders() {
    try {
        const resp = await fetch('/api/orders');
        const data = await resp.json();
        const dates = Object.keys(data).sort().reverse().slice(0,5);
        const container = document.getElementById('recentDates');
        if (!dates.length) {
            container.innerHTML = '<div class="muted">Nenhuma data cadastrada</div>';
            return;
        }
        container.innerHTML = dates.map(d => {
            const o = data[d] || {};
            const tipo = o.tipo || 'Sem tipo';
            const hora = o.horario ? ` • ${o.horario}` : '';
            const formatted = new Date(d + 'T12:00:00').toLocaleDateString('pt-BR', { timeZone: 'UTC' });
            return `<div class="item"><div><strong>${formatted}</strong><div class="muted">${tipo}${hora}</div></div><div class="actions"><a class="btn" href="/agenda/${d}/admin">Ver</a><a class="btn" style="background:#10b981; box-shadow:0 8px 20px rgba(16,185,129,0.25);" href="/agenda/${d}/edit">Editar</a></div></div>`;
        }).join('');
    } catch (e) {
        document.getElementById('recentDates').innerHTML = '<div class="muted">Erro ao carregar</div>';
    }
}

function getDateValue() {
    return document.getElementById('dashDate').value;
}
function openAdmin() {
    const d = getDateValue();
    if (d) window.location = `/agenda/${d}/admin`;
}
function openEdit() {
    const d = getDateValue();
    if (d) window.location = `/agenda/${d}/edit`;
}
function handleDateRedirect(ev) {
    ev.preventDefault();
    openAdmin();
}

loadOrders();
