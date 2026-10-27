// Barrinha "No ar / Preparado" logo abaixo do menu, em todas as páginas
// de operador (incluída por templates/_nav.html). Mostra o que está na
// tela pública, se o monitor de palco está em outra coisa, o que está
// preparado esperando Liberar (com Liberar/Descartar ali mesmo), o modo
// público/monitor, a tela preta e o "acompanhar ao vivo" — que antes era
// invisível — com um botão pra parar. Estado vem do servidor (telao.py):
// GET /api/telao-status ao conectar e o evento telao_status a cada mudança.
(function () {
    // Algumas telas avulsas podem carregar este arquivo sem o _i18n.html
    const _t = typeof window._t === 'function' ? window._t
        : (s, v) => (v ? s.replace(/\{(\w+)\}/g, (m, k) => (k in v ? v[k] : m)) : s);

    // Rótulos do que está no ar vêm prontos do servidor (telao.py
    // describe: "Letra · Música — Seção", "Tela dividida · Cifra + Relógio")
    // e vão iguais pra todas as telas: traduz só o tipo, aqui no navegador.
    // Também usado pelo control.js (prévia e card do preparado).
    const TIPOS = {
        'Nada no ar': _t('Nada no ar'), 'Tela dividida': _t('Tela dividida'),
        'Letra': _t('Letra'), 'Cifra': _t('Cifra'), 'Bíblia': _t('Bíblia'),
        'Foto': _t('Foto'), 'Imagem': _t('Imagem'), 'Vídeo': _t('Vídeo'),
        'Relógio': _t('Relógio'), 'Cronômetro': _t('Cronômetro'),
        'Apresentação': _t('Apresentação'), 'Página': _t('Página'),
    };
    const tipo = n => (Object.prototype.hasOwnProperty.call(TIPOS, n) ? TIPOS[n] : n);
    window.ucTelaoLabel = function (label) {
        const s = String(label == null ? '' : label);
        const i = s.indexOf(' · ');
        const head = i < 0 ? s : s.slice(0, i);
        if (!Object.prototype.hasOwnProperty.call(TIPOS, head)) return s;
        let rest = i < 0 ? '' : s.slice(i + 3);
        if (head === 'Tela dividida') rest = rest.split(' + ').map(tipo).join(' + ');
        return TIPOS[head] + (i < 0 ? '' : ' · ' + rest);
    };

    const bar = document.getElementById('telao-bar');
    if (!bar) return;

    // Dentro do painel do Controle: a barra e a vigia de conexão são as do
    // Controle. Aqui só não deixa comando sair enquanto ele estiver sem
    // conexão (o Controle marca window.__ucOffline e a classe uc-offline
    // no <body> deste iframe).
    if (document.documentElement.classList.contains('uc-embed')) {
        const guard = () => {
            const proto = window.io && window.io.Socket && window.io.Socket.prototype;
            if (!proto || proto.__ucGuarded) return;
            const original = proto.emit;
            proto.emit = function (event, ...args) {
                let off = false;
                try { off = !!window.top.__ucOffline; } catch (e) { /* sem acesso */ }
                if (off) {
                    try { (window.top.ucToast || window.ucToast)(_t('Sem conexão com o servidor — o comando não foi enviado.'), 'error'); } catch (e) { /* sem aviso */ }
                    return this;
                }
                return original.call(this, event, ...args);
            };
            proto.__ucGuarded = true;
        };
        guard();
        return;
    }

    const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => (
        { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    const STAGED_NAMES = { image: _t('Foto'), lyrics: _t('Letra'), bible: _t('Bíblia') };
    const FOLLOW_TEXT = { image: _t('Fotos entram direto'), lyrics: _t('Letra entra direto'), bible: _t('Bíblia entra direta') };
    let socket = null;

    function stagedLabel(item) {
        // Rótulos vêm do título da aba de origem ("Teu Povo · Letra ao
        // vivo — Refrão", "… - U-Control"): tira o nome da página
        const label = String(item.label || '')
            .replace(/\s+[·-]\s+(U-Control|Letra ao vivo)\b/g, '').trim();
        return `${STAGED_NAMES[item.kind] || _t('Conteúdo')}: ${window.ucTelaoLabel(label)}`;
    }

    function render(st) {
        if (!st || !st.live) return;
        lastStatus = st;
        if (offline) return;
        const parts = [];
        parts.push(
            `<a class="tb-live" href="/control" title="${esc(_t('No ar na tela pública — abrir o Controle'))}">` +
            `<span class="tb-dot"></span><b>${esc(_t('No ar'))}</b>` +
            `<span class="tb-label">${esc(window.ucTelaoLabel(st.live.label))}</span></a>`);
        if (st.blackout) {
            // Tela neutra no ar: preta, branca ou logo (static/js/telas_neutras.js)
            const neutra = {
                preta: ['fa-moon', 'Tela preta', 'O público vê a tela toda preta'],
                branca: ['fa-square', 'Tela branca', 'O público vê a tela toda branca'],
                logo: ['fa-church', 'Logo', 'O público vê o logo da igreja'],
            }[st.blackout_tipo] || ['fa-moon', 'Tela preta', 'O público vê a tela toda preta'];
            parts.push(`<span class="tb-chip tb-black" title="${esc(_t(neutra[2]))}"><i class="fas ${neutra[0]}"></i> ${esc(_t(neutra[1]))}</span>`);
        }
        // Modo desta máquina (o servidor guarda um por PC — ver
        // display_state._device_modes); o GET já vem com st.mode
        const dev = document.cookie.match(/(?:^|;\s*)uc_device=([^;]*)/);
        const mode = st.mode || (st.modes || {})[dev ? decodeURIComponent(dev[1]) : null] || 'all';
        if (mode === 'public') {
            parts.push(`<span class="tb-chip tb-mode" title="${esc(_t('Ações mudam só a tela do público'))}"><i class="fas fa-users"></i> ${esc(_t('Só público'))}</span>`);
        } else if (mode === 'monitor') {
            parts.push(`<span class="tb-chip tb-mode" title="${esc(_t('Ações mudam só o monitor de palco'))}"><i class="fas fa-tv"></i> ${esc(_t('Só monitor'))}</span>`);
        }
        if (st.monitor) {
            parts.push(`<span class="tb-chip tb-monitor" title="${esc(_t('O monitor de palco está mostrando outra coisa'))}"><i class="fas fa-tv"></i> ${esc(_t('Monitor:'))} <span class="tb-label">${esc(window.ucTelaoLabel(st.monitor.label))}</span></span>`);
        }
        (st.staged || []).forEach(item => {
            parts.push(
                `<span class="tb-chip tb-staged" title="${esc(_t('Preparado — só vai ao telão quando liberar'))}">` +
                `<b>${esc(_t('Preparado'))}</b><span class="tb-label">${esc(stagedLabel(item))}</span>` +
                `<button type="button" class="tb-btn tb-release" data-act="release" data-kind="${esc(item.kind)}">${esc(_t('Liberar'))}</button>` +
                `<button type="button" class="tb-btn tb-x" data-act="discard" data-kind="${esc(item.kind)}" title="${esc(_t('Descartar'))}" aria-label="${esc(_t('Descartar'))}">&times;</button>` +
                `</span>`);
        });
        if (st.slideshow) {
            parts.push(
                `<span class="tb-chip tb-running" title="${esc(_t('Fotos trocando sozinhas no telão'))}">` +
                `<i class="fas fa-images"></i> ${esc(_t('Slideshow · a cada {n}s', { n: st.slideshow.interval }))}` +
                `<button type="button" class="tb-btn" data-act="stop-slideshow">${esc(_t('parar'))}</button></span>`);
        }
        if (st.ticker) {
            const nomes = { public: _t('público'), monitor: _t('palco'), obs: _t('transmissão') };
            const where = st.ticker.targets.length === 3 ? '' : ' (' + st.ticker.targets.map(t => nomes[t] || t).join(', ') + ')';
            parts.push(
                `<span class="tb-chip tb-running" title="${esc(_t('Aviso rolando na base da tela'))}${esc(where)}">` +
                `<i class="fas fa-bullhorn"></i> ${esc(_t('Aviso'))}${esc(where)}: <span class="tb-label">${esc(st.ticker.text)}</span>` +
                `<button type="button" class="tb-btn" data-act="stop-ticker">${esc(_t('parar'))}</button></span>`);
        }
        if (st.countdown) {
            parts.push(
                `<span class="tb-chip tb-running" title="${esc(_t('Cronômetro'))} ${esc(st.countdown.label)}">` +
                `<i class="fas fa-stopwatch"></i> ${esc(_t('Cronômetro'))} <b class="tb-clock" data-countdown></b>` +
                `<button type="button" class="tb-btn" data-act="stop-countdown">${esc(_t('parar'))}</button></span>`);
        }
        if (st.follow) {
            parts.push(
                `<span class="tb-chip tb-follow" title="${esc(_t('Depois de um Liberar, o que for preparado desse tipo vai direto ao telão'))}">` +
                `<i class="fas fa-bolt"></i> ${esc(st.follow_label === 'Letra e Bíblia' ? _t('Letra e Bíblia entram direto') : (FOLLOW_TEXT[st.follow] || _t('Entra direto')))}` +
                `<button type="button" class="tb-btn" data-act="stop-follow">${esc(_t('parar'))}</button></span>`);
        }
        bar.innerHTML = parts.join('');
        bar.classList.toggle('is-black', !!st.blackout);
        // Relógio do servidor como referência (o PC do operador pode estar
        // com a hora diferente da do Pi)
        clockSkew = st.server_now_ms ? st.server_now_ms - Date.now() : 0;
        tickCountdown();
    }

    let clockSkew = 0;
    function fmt(ms) {
        const s = Math.max(0, Math.round(ms / 1000));
        const m = Math.floor(s / 60);
        return `${String(m).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
    }
    function tickCountdown() {
        const el = bar.querySelector('[data-countdown]');
        const cd = lastStatus && lastStatus.countdown;
        if (!el || !cd) return;
        if (cd.paused) { el.textContent = _t('{tempo} · pausado', { tempo: fmt(cd.remaining_ms || 0) }); return; }
        const left = (cd.end_ms || 0) - (Date.now() + clockSkew);
        el.textContent = left > 0 ? fmt(left) : _t('00:00 · terminou');
    }
    setInterval(tickCountdown, 1000);

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
        // Páginas abertas no painel do Controle também ficam travadas
        document.querySelectorAll('iframe').forEach((f) => {
            try { f.contentDocument.body.classList.toggle('uc-offline', value); } catch (e) { /* outra origem */ }
        });
        if (value) {
            bar.classList.add('is-offline');
            bar.innerHTML =
                '<span class="tb-offline"><i class="fas fa-triangle-exclamation"></i> ' +
                '<b>' + _t('Sem conexão com o servidor') + '</b> — ' + _t('reconectando… Os comandos estão pausados.') + '</span>';
        } else {
            bar.classList.remove('is-offline');
            if (lastStatus) render(lastStatus);
            refresh();
            if (window.ucToast) window.ucToast(_t('Conexão com o servidor restabelecida.'));
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
                if (window.ucToast) window.ucToast(_t('Sem conexão com o servidor — o comando não foi enviado.'), 'error');
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
        else if (btn.dataset.act === 'stop-slideshow') socket.emit('stop_slideshow', {});
        else if (btn.dataset.act === 'stop-ticker') socket.emit('stop_ticker', { target: 'all' });
        else if (btn.dataset.act === 'stop-countdown') socket.emit('reset_countdown', {});
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
