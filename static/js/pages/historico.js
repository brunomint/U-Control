const ICONS = { song: 'fa-music', image: 'fa-image', bible: 'fa-book-bible', ticker: 'fa-bullhorn' };
const LABELS = { song: _t('Música'), image: _t('Telão'), bible: _t('Bíblia'), ticker: _t('Aviso') };

const months = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho',
                'Julho','Agosto','Setembro','Outubro','Novembro','Dezembro'];
const weekdays = ['Domingo','Segunda','Terça','Quarta','Quinta','Sexta','Sábado'];

function formatDate(dateStr) {
    const [y, m, d] = dateStr.split('-');
    const dt = new Date(y, m - 1, d);
    if (!ucLocale().startsWith('pt')) {
        return dt.toLocaleDateString(ucLocale(), { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
    }
    return `${weekdays[dt.getDay()]}, ${parseInt(d)} de ${months[dt.getMonth()]} de ${y}`;
}

function formatTime(ts) {
    return ts.substring(11, 16);
}

function renderTitle(entry) {
    if (entry.type === 'song' && entry.url) {
        return `<a href="${entry.url}" target="_blank">${escHtml(entry.title)}</a>`;
    }
    if (entry.type === 'image' && entry.title && entry.title.startsWith('/static/')) {
        const name = entry.title.split('/').pop();
        return `<a href="${entry.title}" target="_blank">${escHtml(name)}</a>`;
    }
    if (entry.type === 'image' && entry.title) {
        // Troca de tela do telão: display.py loga as rotas cruas (ex. "/lyrics/display + /clock").
        return escHtml(entry.title.split(' + ').map(p => ROUTE_NAMES[p.trim()] || p.trim()).join(' + '));
    }
    return escHtml(entry.title || '—');
}

const ROUTE_NAMES = {
    '/lyrics/display': _t('Cifra'),
    '/lyrics/display/public': _t('Letra'),
    '/clock': _t('Relógio'),
    '/img': _t('Imagem'),
    '/bible/display': _t('Bíblia'),
    '/countdown': _t('Cronômetro'),
};

function escHtml(str) {
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function load() {
    fetch('/api/historico')
        .then(r => r.json())
        .then(log => {
            if (!log.length) {
                document.getElementById('content').innerHTML =
                    '<div class="empty-state">' + _t('Nenhum evento registrado ainda.') + '</div>';
                return;
            }

            // Agrupar por data
            const groups = {};
            log.forEach(entry => {
                const date = entry.ts.substring(0, 10);
                if (!groups[date]) groups[date] = [];
                groups[date].push(entry);
            });

            let html = '';
            Object.keys(groups).forEach(date => {
                html += `<div class="day-group">
                    <div class="day-header">${formatDate(date)}</div>`;
                groups[date].forEach(entry => {
                    html += `<div class="entry">
                        <div class="entry-icon ${entry.type}"><i class="fas ${ICONS[entry.type] || 'fa-display'}"></i></div>
                        <div class="entry-body">
                            <div class="entry-title">${renderTitle(entry)}</div>
                            <div class="entry-time">${LABELS[entry.type] || entry.type} · ${formatTime(entry.ts)}</div>
                        </div>
                    </div>`;
                });
                html += '</div>';
            });

            document.getElementById('content').innerHTML = html;
        })
        .catch(() => {
            document.getElementById('content').innerHTML =
                '<div class="empty-state">' + _t('Erro ao carregar histórico.') + '</div>';
        });
}

function clearHistory() {
    if (!confirm(_t('Limpar todo o histórico?'))) return;
    fetch('/api/historico', { method: 'DELETE' })
        .then(() => { showToast(_t('Histórico limpo.')); load(); renderRanking(); });
}

function showToast(msg) {
    window.ucToast(msg);
}

// ── TABS ──────────────────────────────────────────────────────
let _activeTab = 'historico';
function switchTab(tab) {
    _activeTab = tab;
    document.getElementById('tab-historico').style.display = tab === 'historico' ? '' : 'none';
    document.getElementById('tab-relatorio').style.display = tab === 'relatorio' ? '' : 'none';
    document.querySelectorAll('.tab-btn').forEach((b, i) => {
        b.classList.toggle('active', (i === 0 && tab === 'historico') || (i === 1 && tab === 'relatorio'));
    });
    if (tab === 'relatorio') renderRanking();
}

// ── RANKING ───────────────────────────────────────────────────
let _rankDays = 7;
let _rankLog  = [];

function setPeriod(days, btn) {
    _rankDays = days;
    document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    renderRanking();
}

function renderRanking() {
    fetch('/api/historico')
        .then(r => r.json())
        .then(log => {
            _rankLog = log;
            const cutoff = _rankDays
                ? new Date(Date.now() - _rankDays * 864e5).toISOString().substring(0, 10)
                : '0000-00-00';

            const songs = log.filter(e => e.type === 'song' && e.ts >= cutoff);

            if (!songs.length) {
                document.getElementById('ranking').innerHTML =
                    '<div class="empty-state">' + _t('Nenhuma música no período.') + '</div>';
                return;
            }

            // Conta por título
            const counts = {};
            const urls   = {};
            songs.forEach(e => {
                counts[e.title] = (counts[e.title] || 0) + 1;
                if (e.url) urls[e.title] = e.url;
            });

            const ranked = Object.entries(counts)
                .sort((a, b) => b[1] - a[1]);

            const posClass = ['gold', 'silver', 'bronze'];
            let html = '';
            ranked.forEach(([title, count], i) => {
                const pos = i + 1;
                const cls = posClass[i] || '';
                const label = urls[title]
                    ? `<a href="${urls[title]}" target="_blank">${escHtml(title)}</a>`
                    : escHtml(title);
                html += `<div class="rank-item">
                    <div class="rank-pos ${cls}">${_t('{n}º', { n: pos })}</div>
                    <div class="rank-title">${label}</div>
                    <div class="rank-count">${count}×</div>
                </div>`;
            });
            document.getElementById('ranking').innerHTML = html;
        });
}

load();
