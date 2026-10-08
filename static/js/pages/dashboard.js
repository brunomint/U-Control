// Início: saudação/data, card "Próximo culto" (/api/culto/proximo) e
// faixa do sistema + pills do topo (/api/system/status, a cada 5 s).

const DIAS = ['Domingo', 'Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sábado'];
const MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
               'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'];

function escapeHtml(unsafe) {
    return String(unsafe)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function updateGreeting() {
    const now = new Date();
    const h = now.getHours();
    const greeting = h < 12 ? 'Bom dia' : (h < 18 ? 'Boa tarde' : 'Boa noite');
    const g = document.getElementById('greeting');
    if (g) g.textContent = greeting;
    const d = document.getElementById('current-date');
    if (d) d.textContent = `${DIAS[now.getDay()]}, ${now.getDate()} de ${MESES[now.getMonth()]} de ${now.getFullYear()}`;
}

function isLoginRedirect(response) {
    return response.redirected || response.url.includes('/login');
}

// ── Próximo culto ──────────────────────────────────────────────────────
const KIND_LABEL = { song: 'música', bible: 'leitura', text: 'texto' };

function whenLabel(days) {
    if (days === 0) return 'Hoje';
    if (days === 1) return 'Amanhã';
    return `Próximo culto · em ${days} dias`;
}

function formatServiceDate(iso) {
    // iso = YYYY-MM-DD; monta a data local sem passar por UTC.
    const [y, m, d] = iso.split('-').map(Number);
    const dt = new Date(y, m - 1, d);
    return `${DIAS[dt.getDay()]}, ${d} de ${MESES[m - 1]}`;
}

function renderNextService(data) {
    const card = document.getElementById('next-service');
    if (!card) return;

    if (data.status !== 'ok') {
        card.innerHTML = `
            <div class="uc-empty">
                <i class="fas fa-calendar-plus"></i>
                Nenhum culto marcado daqui pra frente.
                <div class="uc-btn-row" style="justify-content:center;margin-top:14px">
                    <a class="uc-btn uc-btn-primary" href="${window.UC_URLS.orderNew}"><i class="fas fa-plus"></i> Nova ordem de culto</a>
                </div>
            </div>`;
        return;
    }

    const title = formatServiceDate(data.date) + (data.horario ? ` · ${data.horario}` : '');
    const meta = [data.tipo, data.dirigente && `dirigente: ${data.dirigente}`, data.pregador && `pregação: ${data.pregador}`]
        .filter(Boolean).map(escapeHtml).join(' · ');

    const itens = data.itens.length
        ? `<ol class="next-order">${data.itens.map((item, i) => `
            <li>
                <span class="n">${String(i + 1).padStart(2, '0')}</span>
                <span class="t">${escapeHtml(item.title)}${item.artist ? `<span class="artist">${escapeHtml(item.artist)}</span>` : ''}</span>
                <span class="kind">${KIND_LABEL[item.kind] || ''}</span>
            </li>`).join('')}</ol>`
        : `<div class="uc-empty"><i class="fas fa-list-ol"></i>A ordem ainda não tem itens.</div>`;

    const equipe = data.equipe.length
        ? `<div class="team">${data.equipe.map(e => `<span><b>${escapeHtml(e.funcao)}</b>${escapeHtml(e.pessoa)}</span>`).join('')}</div>`
        : '';

    card.innerHTML = `
        <div class="next-head">
            <div>
                <div class="next-eyebrow${data.days_until === 0 ? ' today' : ''}">${whenLabel(data.days_until)}</div>
                <h2>${escapeHtml(title)}</h2>
                ${meta ? `<div class="next-meta">${meta}</div>` : ''}
            </div>
        </div>
        ${itens}
        <div class="next-foot">
            <a class="uc-btn uc-btn-live uc-btn-lg" href="${window.UC_URLS.control}"><i class="fas fa-play"></i> Abrir Controle</a>
            <a class="uc-btn uc-btn-secondary uc-btn-lg" href="/order/${encodeURIComponent(data.date)}">Editar ordem</a>
            ${equipe}
        </div>`;
}

async function loadNextService() {
    const card = document.getElementById('next-service');
    try {
        const response = await fetch('/api/culto/proximo');
        if (isLoginRedirect(response)) {
            card.innerHTML = `<div class="uc-empty"><i class="fas fa-lock"></i>Sua sessão expirou. Entre de novo e recarregue a página.</div>`;
            return;
        }
        renderNextService(await response.json());
    } catch (e) {
        console.error(e);
        card.innerHTML = `<div class="uc-empty"><i class="fas fa-triangle-exclamation"></i>Não deu pra carregar o próximo culto. Recarregue a página.</div>`;
    }
}

// ── Sistema ───────────────────────────────────────────────────────────
const SCREEN_ROLES = { monitor: 'Monitor', lyrics_display: 'Letras', presenter: 'Presenter' };

function has(v) { return v === 0 || !!v; }

function meter(label, pct, text) {
    if (!has(pct)) return `<div class="stat"><span>${label}</span><span class="uc-mono">--</span></div>`;
    const p = Math.max(0, Math.min(100, Number(pct)));
    return `
        <div class="stat">
            <span>${label}</span>
            <span class="uc-mono">${escapeHtml(text)}</span>
            <span class="meter"><i class="${p >= 85 ? 'high' : ''}" style="width:${p}%"></i></span>
        </div>`;
}

function setServerPill(state) {
    const pill = document.getElementById('server-pill');
    if (!pill) return;
    const map = {
        online: ['uc-pill-ok', 'Servidor online'],
        offline: ['uc-pill-danger', 'Servidor offline'],
        session: ['uc-pill-warn', 'Sessão expirada'],
    };
    const [cls, text] = map[state];
    pill.className = `uc-pill ${cls}`;
    pill.innerHTML = `<span class="dot"></span>${text}`;
}

function setScreensPill(byRole) {
    const pill = document.getElementById('screens-pill');
    if (!pill) return;
    const parts = Object.keys(SCREEN_ROLES)
        .filter(role => byRole[role])
        .map(role => `${SCREEN_ROLES[role]}: ${byRole[role]}`);
    const total = Object.keys(SCREEN_ROLES).reduce((n, role) => n + (Number(byRole[role]) || 0), 0);
    pill.className = `uc-pill ${total ? 'uc-pill-ok' : 'uc-pill-muted'}`;
    pill.innerHTML = `<i class="fas fa-display"></i> ${total} ${total === 1 ? 'tela conectada' : 'telas conectadas'}`;
    pill.title = parts.length ? parts.join(' · ') : 'Nenhum monitor, letreiro ou presenter aberto agora';
}

async function loadSystemStatus() {
    const strip = document.getElementById('system-strip');
    if (!strip) return;
    try {
        const response = await fetch('/api/system/status');
        if (isLoginRedirect(response)) { setServerPill('session'); return; }
        const data = await response.json();

        setServerPill(data.online ? 'online' : 'offline');
        setScreensPill(data.socketio_by_role && typeof data.socketio_by_role === 'object' ? data.socketio_by_role : {});

        const diskText = has(data.disk_free_gb) ? `${Number(data.disk_free_gb).toFixed(1).replace('.', ',')} GB livres` : '--';
        strip.innerHTML = `
            ${meter('CPU', data.cpu_percent, has(data.cpu_percent) ? `${Number(data.cpu_percent).toFixed(0)}%` : '')}
            ${meter('RAM', data.ram_percent, has(data.ram_percent) ? `${Number(data.ram_percent).toFixed(0)}%` : '')}
            ${meter('Disco', data.disk_used_percent, diskText)}
            <div class="addr">
                <span>Público <span class="uc-mono">${escapeHtml(data.public_url || '--')}</span></span>
                <span>Rede local <span class="uc-mono">${escapeHtml(data.local_url || '--')}</span></span>
            </div>`;
    } catch (e) {
        console.error(e);
        setServerPill('offline');
        strip.innerHTML = `<span class="uc-muted">Sem resposta do servidor. Tentando de novo…</span>`;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    updateGreeting();
    setInterval(updateGreeting, 60000);
    loadNextService();
    loadSystemStatus();
    setInterval(loadSystemStatus, 5000);
});
