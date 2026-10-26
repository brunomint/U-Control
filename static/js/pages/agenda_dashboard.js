async function loadOrders() {
    try {
        const resp = await fetch('/api/orders');
        const data = await resp.json();
        const now = new Date();
        const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
        // Uma linha por culto (chave YYYY-MM-DD ou YYYY-MM-DD-N, ver agenda_cultos.js)
        const dates = Object.keys(data).filter(d => d >= today).sort().slice(0, 6);
        const container = document.getElementById('recentDates');
        if (!dates.length) {
            container.innerHTML = `<li class="uc-muted">${_t('Nenhuma data marcada daqui pra frente')}</li>`;
            return;
        }
        container.innerHTML = dates.map(d => {
            const o = data[d] || {};
            const tipo = o.tipo ? _t(o.tipo) : _t('Sem tipo');
            const horario = o.horario_culto || o.horario;
            const hora = horario ? ` • ${horario}` : '';
            const formatted = new Date(d.slice(0, 10) + 'T12:00:00').toLocaleDateString(ucLocale(), { timeZone: 'UTC' });
            return `<li><div class="grow"><strong>${formatted}</strong><div class="sub">${tipo}${hora}</div></div><a class="uc-btn uc-btn-ghost uc-btn-sm" href="/agenda/${d}/admin">${_t('Ver')}</a><a class="uc-btn uc-btn-secondary uc-btn-sm" href="/agenda/${d}/edit"><i class="fas fa-pen"></i> ${_t('Editar')}</a></li>`;
        }).join('');
    } catch (e) {
        document.getElementById('recentDates').innerHTML = `<li class="uc-muted">${_t('Erro ao carregar as datas')}</li>`;
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

// Nome da igreja no calendário público (blueprints/agenda.py)
document.getElementById('salvarNomeIgreja').addEventListener('click', async () => {
    const msg = document.getElementById('nomeIgrejaMsg');
    try {
        const r = await fetch('/api/agenda/nome-igreja', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nome: document.getElementById('nomeIgreja').value }),
        });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        msg.textContent = _t('Salvo.');
    } catch (e) {
        msg.textContent = _t('Não deu pra salvar: {erro}', { erro: e.message });
    }
});
