// Telas neutras: preta, branca e com o logo da igreja.
// Botões [data-tela-neutra="preta|branca|logo"] nas páginas de operador
// (control.html, presenter.html). Valem onde o "O que as ações mudam"
// deste computador manda — Os dois / Só público / Só monitor —, como letra
// e foto (o servidor aplica o modo: handle_blackout com usar_modo). Tocar
// liga aquela tela; tocar de novo ("Voltar") volta a imagem. O servidor
// guarda o de cada tela e avisa todo mundo pelo evento 'blackout'.
//
// Já houve um seletor só destas telas, guardado no navegador: com três
// seletores parecidos no Controle (este, a aba da prévia e o modo), a
// tela branca ia pro palco achando que ia pro público.
//
// Atributo próprio de propósito: o Controle tem outros botões com
// data-tela (telas do aviso, "Abrir no datashow") — na 1.0.9 este arquivo
// pegava todos, e escolher "Palco" no aviso ligava a tela preta.
(function () {
    const ROTULO = { preta: 'Preta', branca: 'Branca', logo: 'Logo' };
    const ICONE = { preta: 'fas fa-moon', branca: 'far fa-square', logo: 'fas fa-church' };
    const AVISO = {
        preta: 'Tela preta: o público vê tudo preto',
        branca: 'Tela branca: o público vê tudo branco',
        logo: 'Logo: o público vê o logo da igreja',
    };
    const AVISO_MONITOR = {
        preta: 'Tela preta: o palco vê tudo preto',
        branca: 'Tela branca: o palco vê tudo branco',
        logo: 'Logo: o palco vê o logo da igreja',
    };
    let estado = { public: null, monitor: null };   // tipo ligado em cada tela
    let previa = 'public';                           // qual tela a prévia do Controle mostra
    let modoServidor = 'all';                        // modo deste computador (sem seletor na página)
    let socket = null;

    const botoes = () => document.querySelectorAll('[data-tela-neutra]');

    // Modo deste computador: o seletor do Controle, se a página tem; senão
    // o que o servidor guarda (Apresentador)
    function modo() {
        const b = document.querySelector('[data-mode][aria-pressed="true"]');
        return b ? b.dataset.mode : modoServidor;
    }
    const telasDoModo = () => ({ public: ['public'], monitor: ['monitor'] }[modo()] || ['public', 'monitor']);
    // Esta tela neutra está no ar em todas as telas que o modo alcança?
    const noAr = tipo => telasDoModo().every(t => estado[t] === tipo);

    function render() {
        botoes().forEach(btn => {
            const tipo = btn.dataset.telaNeutra;
            const este = noAr(tipo);
            btn.classList.toggle('active', este);
            btn.setAttribute('aria-pressed', este ? 'true' : 'false');
            // No ar: o mesmo botão volta a imagem (como o antigo "Tela preta")
            const span = btn.querySelector('span');
            if (span) span.textContent = este ? _t('Voltar') : _t(ROTULO[tipo]);
            const icone = btn.querySelector('i');
            if (icone) icone.className = este ? 'fas fa-rotate-left' : ICONE[tipo];
            btn.title = este ? _t('Voltar a imagem') : (btn.dataset.tituloOriginal || '');
        });
        // Aviso em cima da prévia do Controle: o da tela que ela mostra
        const aviso = document.getElementById('preview-blackout');
        if (aviso) {
            const tipo = estado[previa === 'monitor' ? 'monitor' : 'public'];
            aviso.hidden = !tipo;
            if (tipo) {
                aviso.dataset.tipo = tipo;
                const txt = aviso.querySelector('span');
                if (txt) txt.textContent = _t((previa === 'monitor' ? AVISO_MONITOR : AVISO)[tipo]);
                const icone = aviso.querySelector('i');
                if (icone) icone.className = ICONE[tipo];
            }
        }
    }

    // Estado vindo do servidor: evento 'blackout', /api/telao-status ou
    // telao_status (este traz também o modo deste computador)
    function mostrar(dados) {
        if (!dados) return;
        if (dados.telas) estado = { public: dados.telas.public || null, monitor: dados.telas.monitor || null };
        else if (dados.telas_neutras) estado = { public: dados.telas_neutras.public || null, monitor: dados.telas_neutras.monitor || null };
        else if ('active' in dados) estado = { ...estado, public: dados.active ? (dados.tipo || 'preta') : null };
        const dev = document.cookie.match(/(?:^|;\s*)uc_device=([^;]*)/);
        const m = dados.mode || (dados.modes || {})[dev ? decodeURIComponent(dev[1]) : null];
        if (m || dados.modes) modoServidor = m || 'all';
        render();
    }

    function alternar(tipo) {
        const ligar = !noAr(tipo);
        socket.emit('blackout', { active: ligar, tipo, usar_modo: true });
        telasDoModo().forEach(t => { estado[t] = ligar ? tipo : null; });
        render();
    }

    function iniciar(sock) {
        socket = sock;
        botoes().forEach(btn => {
            btn.dataset.tituloOriginal = btn.title || '';
            btn.addEventListener('click', () => alternar(btn.dataset.telaNeutra));
        });
        // Trocou o modo no Controle: os botões passam a mostrar as telas dele
        document.querySelectorAll('[data-mode]').forEach(b => b.addEventListener('click', () => setTimeout(render, 0)));
        socket.on('blackout', mostrar);
        socket.on('telao_status', mostrar);
        fetch('/api/telao-status').then(r => r.json()).then(mostrar).catch(() => {});
        render();
    }

    // control.js avisa qual tela a prévia está mostrando (público/palco)
    function setPrevia(tela) { previa = tela; render(); }

    window.TelasNeutras = { iniciar, mostrar, setPrevia };
})();
