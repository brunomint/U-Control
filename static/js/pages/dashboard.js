// Atualiza hora atual
function updateTime() {
    const now = new Date();
    const timeStr = now.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
    const el = document.getElementById('current-time');
    if (el) el.textContent = timeStr;
}

// Atualiza data atual
function updateDate() {
    const now = new Date();
    const dateStr = now.toLocaleDateString('pt-BR', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
    const el = document.getElementById('current-date');
    if (el) el.textContent = dateStr.charAt(0).toUpperCase() + dateStr.slice(1);
}

function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

async function loadSystemStatus() {
    const container = document.getElementById('system-status-container');
    if (!container) return;

    try {
        const response = await fetch('/api/system/status');
        const contentType = response.headers.get('content-type') || '';

        if (response.redirected || response.url.includes('/login')) {
            container.innerHTML = `
                <div class="status-item">
                    <span>Servidor</span>
                    <span class="status-badge" style="background: var(--warning);">SESSÃO</span>
                </div>`;
            return;
        }

        if (!contentType.includes('application/json')) {
            throw new Error('Resposta não é JSON');
        }

        const data = await response.json();
        const online = !!data.online;
        const badgeText = online ? 'ONLINE' : 'OFFLINE';
        const badgeColor = online ? 'var(--success)' : 'var(--danger)';

        const publicUrl = data.public_url || '--';
        const localUrl = data.local_url || '--';
        const socketioClients = (data.socketio_clients === 0 || data.socketio_clients) ? data.socketio_clients : '--';
        const socketioByRole = (data.socketio_by_role && typeof data.socketio_by_role === 'object') ? data.socketio_by_role : {};
        const cpuPercent = (data.cpu_percent === 0 || data.cpu_percent) ? data.cpu_percent : null;
        const ramPercent = (data.ram_percent === 0 || data.ram_percent) ? data.ram_percent : null;

        const cpuText = (cpuPercent === null) ? '--' : `${Number(cpuPercent).toFixed(0)}%`;
        const ramText = (ramPercent === null) ? '--' : `${Number(ramPercent).toFixed(0)}%`;

        const diskTotalGb = (data.disk_total_gb === 0 || data.disk_total_gb) ? data.disk_total_gb : null;
        const diskFreeGb = (data.disk_free_gb === 0 || data.disk_free_gb) ? data.disk_free_gb : null;
        const diskUsedPercent = (data.disk_used_percent === 0 || data.disk_used_percent) ? data.disk_used_percent : null;

        const diskText = (diskTotalGb === null || diskFreeGb === null || diskUsedPercent === null)
            ? '--'
            : `${Number(diskFreeGb).toFixed(1)}GB livre / ${Number(diskTotalGb).toFixed(1)}GB (${Number(diskUsedPercent).toFixed(0)}% usado)`;

        const roleLabel = {
            'monitor': 'Monitor',
            'lyrics_display': 'Display Letras',
            'presenter': 'Presenter',
            'unknown': 'Outros'
        };

        const roleCountsHtml = Object.keys(socketioByRole)
            .sort()
            .map((role) => {
                const label = roleLabel[role] || role;
                const count = socketioByRole[role];
                return `
                    <div class="status-item">
                        <span>SocketIO - ${escapeHtml(String(label))}</span>
                        <span style="color: var(--text-secondary);">${escapeHtml(String(count))}</span>
                    </div>`;
            }).join('');

        container.innerHTML = `
            <div class="status-item">
                <span>Servidor</span>
                <span class="status-badge" style="background: ${badgeColor};">${badgeText}</span>
            </div>
            <div class="status-item">
                <span>CPU / RAM</span>
                <span style="color: var(--text-secondary);">${escapeHtml(cpuText)} / ${escapeHtml(ramText)}</span>
            </div>
            <div class="status-item">
                <span>Disco</span>
                <span style="color: var(--text-secondary);">${escapeHtml(diskText)}</span>
            </div>
            <div class="status-item">
                <span>Conexões SocketIO</span>
                <span style="color: var(--text-secondary);">${escapeHtml(String(socketioClients))}</span>
            </div>
            ${roleCountsHtml}
            <div class="status-item">
                <span>Acesso público</span>
                <span style="color: var(--text-secondary);">${escapeHtml(String(publicUrl))}</span>
            </div>
            <div class="status-item">
                <span>Acesso local</span>
                <span style="color: var(--text-secondary);">${escapeHtml(String(localUrl))}</span>
            </div>`;
    } catch (e) {
        console.error(e);
        container.innerHTML = `
            <div class="status-item">
                <span>Servidor</span>
                <span class="status-badge" style="background: var(--danger);">OFFLINE</span>
            </div>
            <div class="status-item">
                <span>CPU / RAM</span>
                <span style="color: var(--text-secondary);">-- / --</span>
            </div>
            <div class="status-item">
                <span>Disco</span>
                <span style="color: var(--text-secondary);">--</span>
            </div>
            <div class="status-item">
                <span>Conexões SocketIO</span>
                <span style="color: var(--text-secondary);">--</span>
            </div>
            <div class="status-item">
                <span>Acesso público</span>
                <span style="color: var(--text-secondary);">--</span>
            </div>
            <div class="status-item">
                <span>Acesso local</span>
                <span style="color: var(--text-secondary);">--</span>
            </div>`;
    }
}

async function loadCultoStatus() {
    const container = document.getElementById('culto-status-container');
    if (!container) return;
    container.innerHTML = `
        <div class="text-center py-4">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Carregando...</span>
            </div>
            <p class="mt-2">Carregando ordem do culto...</p>
        </div>`;

    try {
        const response = await fetch('/api/culto/status');
        const contentType = response.headers.get('content-type') || '';

        if (response.redirected || response.url.includes('/login')) {
            container.innerHTML = `
                <div class="alert alert-warning">
                    Sua sessão expirou. Faça login novamente e recarregue a página.
                </div>`;
            return;
        }

        if (!contentType.includes('application/json')) {
            throw new Error('Resposta não é JSON');
        }

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data?.error || 'Erro ao carregar status');
        }

        if (data.status === 'no_service') {
            container.innerHTML = `
                <div class="alert alert-info">
                    <i class="fas fa-info-circle"></i> ${escapeHtml(data.message || 'Nenhum culto agendado para hoje')}
                </div>`;
            return;
        }

        if (!data.steps || data.steps.length === 0) {
            const info = [];
            if (data.tipo) info.push(`<strong>${escapeHtml(data.tipo)}</strong>`);
            if (data.horario) info.push(`🕐 ${escapeHtml(data.horario)}`);
            if (data.dirigente) info.push(`Dirigente: ${escapeHtml(data.dirigente)}`);
            if (data.pregador) info.push(`Pregador: ${escapeHtml(data.pregador)}`);
            container.innerHTML = `
                <div style="line-height:1.8; color: var(--text-secondary); font-size:0.9em;">
                    ${info.length ? info.join('<br>') : '<i class="fas fa-exclamation-triangle"></i> Culto agendado sem itens na ordem.'}
                </div>`;
            return;
        }

        const typeIcon = {
            'abertura': 'fa-door-open',
            'louvor': 'fa-music',
            'mensagem': 'fa-book',
            'oferta': 'fa-hand-holding-usd',
            'encerramento': 'fa-sign-out-alt',
            'item': 'fa-circle'
        };

        container.innerHTML = data.steps.map((step) => {
            const icon = typeIcon[step.type] || typeIcon.item;
            return `
                <div class="step pending">
                    <i class="fas ${icon}"></i> ${escapeHtml(step.title || 'Item')}
                </div>`;
        }).join('');
    } catch (e) {
        console.error(e);
        container.innerHTML = `
            <div class="alert alert-warning">
                Não foi possível carregar a ordem do culto. Tente recarregar a página.
            </div>`;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    try { updateTime(); } catch (e) { console.error(e); }
    try { updateDate(); } catch (e) { console.error(e); }
    setInterval(() => {
        try { updateTime(); } catch (e) { console.error(e); }
    }, 1000);

    try { loadCultoStatus(); } catch (e) { console.error(e); }
    try { loadSystemStatus(); } catch (e) { console.error(e); }
    setInterval(() => {
        try { loadSystemStatus(); } catch (e) { console.error(e); }
    }, 5000);
});
