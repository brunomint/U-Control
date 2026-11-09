// Quem cuida de cada tela, no /control: "Público: com você · Palco: com
// vitor", com Assumir pra tela que está com outra pessoa (dois toques,
// porque tira a tela de quem está com ela) e se ela acompanha a passagem
// (música, slides, Bíblia e vídeo que qualquer pessoa conduz): acompanha
// enquanto o responsável deixa letra/Bíblia/foto nela. O servidor decide (destinos.py; telao_status:
// donos, seguindo, eu). Usa o `socket` de pages/control.js.
(function () {
    const CONFIRMAR_MS = 4000;
    const caixa = document.getElementById('destinos');
    if (!caixa) return;
    const NOMES = { public: _t('Público (telão e site)'), monitor: _t('Palco (monitor)') };
    const ICONES = { public: 'fa-users', monitor: 'fa-tv' };
    const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => (
        { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    let ultimo = null;
    let pedido = null;      // {mode, ocupadas}: troca recusada esperando Assumir
    let armado = null;      // botão no primeiro toque
    let espera = null;

    function desarmar() {
        clearTimeout(espera);
        espera = null;
        armado = null;
        render();
    }

    function linha(tela, st) {
        const dono = (st.donos || {})[tela];
        const meu = dono && dono === st.eu;
        const texto = !dono ? _t('livre') : meu ? _t('com você') : _t('com {nome}', { nome: dono });
        const botao = dono && !meu
            ? `<button type="button" class="uc-btn uc-btn-secondary" data-assumir="${tela}">${
                esc(armado === tela ? _t('Confirmar: assumir') : _t('Assumir'))}</button>` : '';
        // A tela acompanha quem conduz enquanto o dono deixa letra/Bíblia/foto
        // nela; com relógio, tela preta etc. ela fica parada (destinos.py)
        const segue = !!(st.seguindo || {})[tela];
        const naBiblia = tela === 'monitor' && st.palco_na_biblia;
        const seguir = `<span class="destino-segue">${esc(!segue ? _t('parada no que o responsável pôs')
            : naBiblia ? _t('acompanha a Bíblia') : _t('acompanha a letra'))}</span>`;
        return `<div class="destino${meu ? ' meu' : ''}"><span><i class="fas ${ICONES[tela]}" aria-hidden="true"></i> ` +
            `<b>${esc(NOMES[tela])}:</b> ${esc(texto)}</span><span class="destino-acoes">${seguir}${botao}</span></div>`;
    }

    function render(st) {
        st = st || ultimo;
        if (!st || !st.donos) return;
        ultimo = st;
        let html = linha('public', st) + linha('monitor', st);
        if (pedido) {
            const quem = Object.entries(pedido.ocupadas)
                .map(([t, n]) => _t('{tela} está com {nome}', { tela: NOMES[t], nome: n })).join(' · ');
            html += `<div class="destino-pedido"><span>${esc(quem)}.</span>` +
                `<button type="button" class="uc-btn uc-btn-primary" data-assumir-pedido>${
                    esc(armado === 'pedido' ? _t('Confirmar: assumir') : _t('Assumir'))}</button>` +
                `<button type="button" class="uc-btn uc-btn-secondary" data-cancelar>${esc(_t('Cancelar'))}</button></div>`;
        }
        caixa.innerHTML = html;
    }

    function confirmar(chave, acao) {
        if (armado !== chave) {
            armado = chave;
            clearTimeout(espera);
            espera = setTimeout(desarmar, CONFIRMAR_MS);
            render();
            return;
        }
        clearTimeout(espera);
        armado = null;
        acao();
    }

    caixa.addEventListener('click', (e) => {
        const b = e.target.closest('button');
        if (!b) return;
        if (b.dataset.assumir) {
            const tela = b.dataset.assumir;
            confirmar(tela, () => socket.emit('assumir_tela', { tela }, () => render()));
        } else if (b.hasAttribute('data-assumir-pedido')) {
            confirmar('pedido', () => {
                const mode = pedido.mode;
                pedido = null;
                socket.emit('set_display_mode', { mode, assumir: true }, () => render());
            });
        } else if (b.hasAttribute('data-cancelar')) {
            pedido = null;
            desarmar();
        }
    });

    // Troca de telas recusada (control.js setModeChoice): oferece Assumir
    window.ucDestinos = {
        pedirAssumir(ocupadas, mode) {
            pedido = { ocupadas, mode };
            armado = null;
            render();
        },
    };

    socket.on('telao_status', (st) => render(st));
    socket.on('tela_assumida', d => {
        if (window.ucToast) window.ucToast(_t('{nome} assumiu uma das suas telas.', { nome: d.por }), 'error');
    });
    fetch('/api/telao-status').then(r => (r.ok ? r.json() : null)).then(render).catch(() => {});
})();
