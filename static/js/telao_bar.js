// Barrinha "No ar / Preparado" logo abaixo do menu, em todas as páginas
// de operador (incluída por templates/_nav.html). Mostra o que está na
// tela pública, se o monitor de palco está em outra coisa, o que está
// preparado esperando Liberar (com Liberar/Descartar ali mesmo), o modo
// público/monitor, a tela preta e o "acompanhar ao vivo" — que antes era
// invisível — com um botão pra parar. Estado vem do servidor (telao.py):
// GET /api/telao-status ao conectar e o evento telao_status a cada mudança.
(function () {
    const bar = document.getElementById('telao-bar');
    if (!bar) return;

    const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => (
        { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    const STAGED_NAMES = { image: 'Foto', lyrics: 'Letra', bible: 'Bíblia' };
    const FOLLOW_TEXT = { image: 'Fotos entram direto', lyrics: 'Letra entra direto', bible: 'Bíblia entra direta' };
    let socket = null;

    function stagedLabel(item) {
        // Rótulos vêm do título da aba de origem ("Teu Povo · Letra ao
        // vivo — Refrão", "… - U-Control"): tira o nome da página
        const label = String(item.label || '')
            .replace(/\s+[·-]\s+(U-Control|Letra ao vivo)\b/g, '').trim();
        return `${STAGED_NAMES[item.kind] || 'Conteúdo'}: ${label}`;
    }

    function render(st) {
        if (!st || !st.live) return;
        lastStatus = st;
        if (offline) return;
        const parts = [];
        parts.push(
            `<a class="tb-live" href="/control" title="No ar na tela pública — abrir o Controle">` +
            `<span class="tb-dot"></span><b>No ar</b>` +
            `<span class="tb-label">${esc(st.live.label)}</span></a>`);
        if (st.blackout) {
            parts.push('<span class="tb-chip tb-black" title="O público vê a tela toda preta"><i class="fas fa-moon"></i> Tela preta</span>');
        }
        if (st.mode === 'public') {
            parts.push('<span class="tb-chip tb-mode" title="Ações mudam só a tela do público"><i class="fas fa-users"></i> Só público</span>');
        } else if (st.mode === 'monitor') {
            parts.push('<span class="tb-chip tb-mode" title="Ações mudam só o monitor de palco"><i class="fas fa-tv"></i> Só monitor</span>');
        }
        if (st.monitor) {
            parts.push(`<span class="tb-chip tb-monitor" title="O monitor de palco está mostrando outra coisa"><i class="fas fa-tv"></i> Monitor: <span class="tb-label">${esc(st.monitor.label)}</span></span>`);
        }
        (st.staged || []).forEach(item => {
            parts.push(
                `<span class="tb-chip tb-staged" title="Preparado — só vai ao telão quando liberar">` +
                `<b>Preparado</b><span class="tb-label">${esc(stagedLabel(item))}</span>` +
                `<button type="button" class="tb-btn tb-release" data-act="release" data-kind="${esc(item.kind)}">Liberar</button>` +
                `<button type="button" class="tb-btn tb-x" data-act="discard" data-kind="${esc(item.kind)}" title="Descartar" aria-label="Descartar">&times;</button>` +
                `</span>`);
        });
        if (st.follow) {
            parts.push(
                `<span class="tb-chip tb-follow" title="Depois de um Liberar, o que for preparado desse tipo vai direto ao telão">` +
                `<i class="fas fa-bolt"></i> ${esc(FOLLOW_TEXT[st.follow] || 'Entra direto')}` +
                `<button type="button" class="tb-btn" data-act="stop-follow">parar</button></span>`);
        }
        bar.innerHTML = parts.join('');
        bar.classList.toggle('is-black', !!st.blackout);
    }

    function refresh() {
        fetch('/api/telao-status', { credentials: 'same-origin' })
            .then(r => (r.ok ? r.json() : null))
            .then(render)
            .catch(() => {});
    }

    // ── Conexão com o servidor ───────────────────────────────────────
    // Wi-Fi da igreja cai → antes nada avisava (a barra só ficava meio
    // apagada) e o navegador podia levar ~45s pra notar. Agora: pergunta
    // ao servidor a cada 5s (sem resposta em 4s = sem conexão), escuta o
    // aviso de rede do próprio aparelho, deixa a barra vermelha e apaga a
    // área de comandos ([data-telao-commands]) até voltar.
    let offline = false;
    let lastStatus = null;
    let pingTimer = null;

    function setOffline(value) {
        if (value === offline) return;
        offline = value;
        window.__ucOffline = value;
        document.body.classList.toggle('uc-offline', value);
        if (value) {
            bar.classList.add('is-offline');
            bar.innerHTML =
                '<span class="tb-offline"><i class="fas fa-triangle-exclamation"></i> ' +
                '<b>Sem conexão com o servidor</b> — reconectando… Os comandos estão pausados.</span>';
        } else {
            bar.classList.remove('is-offline');
            if (lastStatus) render(lastStatus);
            refresh();
            if (window.ucToast) window.ucToast('Conexão com o servidor restabelecida.');
        }
    }

    function ping() {
        if (!socket || !socket.connected) return;
        socket.timeout(4000).emit('telao_ping', {}, (err) => setOffline(!!err));
    }

    // Comando tentado sem conexão é DESCARTADO, com aviso: o Socket.IO
    // guardaria e mandaria tudo de uma vez quando a rede voltasse (três
    // fontes clicadas durante a queda entrariam no telão em sequência)
    function guardEmits() {
        const proto = window.io && window.io.Socket && window.io.Socket.prototype;
        if (!proto || proto.__ucGuarded) return;
        const original = proto.emit;
        proto.emit = function (event, ...args) {
            // Só com a queda detectada: na abertura da página o socket ainda
            // está conectando e o buffer normal do Socket.IO é o certo
            if (window.__ucOffline && event !== 'telao_ping') {
                if (window.ucToast) window.ucToast('Sem conexão com o servidor — o comando não foi enviado.', 'error');
                return this;
            }
            return original.call(this, event, ...args);
        };
        proto.__ucGuarded = true;
    }

    function start() {
        guardEmits();
        socket = window.io();
        socket.on('connect', () => { setOffline(false); refresh(); });
        socket.on('telao_status', render);
        socket.on('disconnect', () => setOffline(true));
        window.addEventListener('offline', () => setOffline(true));
        window.addEventListener('online', ping);
        pingTimer = setInterval(ping, 5000);
    }

    bar.addEventListener('click', (e) => {
        const btn = e.target.closest('[data-act]');
        if (!btn || !socket || offline) return;
        e.preventDefault();
        const kind = btn.dataset.kind;
        if (btn.dataset.act === 'release') socket.emit('release_staged_content', { kind });
        else if (btn.dataset.act === 'discard') socket.emit('discard_staged_content', { kind });
        else if (btn.dataset.act === 'stop-follow') socket.emit('stop_live_follow', {});
    });

    if (window.io) {
        start();
    } else {
        const s = document.createElement('script');
        s.src = '/static/vendor/socketio/socket.io.min.js';
        s.onload = start;
        document.head.appendChild(s);
    }
})();
