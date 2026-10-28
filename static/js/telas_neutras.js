// Telas neutras: preta, branca e com o logo da igreja.
// Botões [data-tela-neutra="preta|branca|logo"] em qualquer página de
// operador (control.html, presenter.html) e o seletor de onde valem,
// [data-neutra-alvo="public|monitor|ambos"] (padrão: só o público; fica
// guardado neste computador). Tocar liga aquela tela nas escolhidas;
// tocar de novo ("Voltar") volta a imagem nelas. O servidor guarda o de
// cada tela (handle_blackout) e avisa todo mundo pelo evento 'blackout'.
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
    const CHAVE_ALVO = 'ucNeutraAlvo';
    let estado = { public: null, monitor: null };   // tipo ligado em cada tela
    let previa = 'public';                           // qual tela a prévia do Controle mostra
    let alvo = 'public';
    try { alvo = localStorage.getItem(CHAVE_ALVO) || 'public'; } catch (e) { /* sem storage */ }
    if (!['public', 'monitor', 'ambos'].includes(alvo)) alvo = 'public';
    let socket = null;

    const botoes = () => document.querySelectorAll('[data-tela-neutra]');
    const telasDoAlvo = () => (alvo === 'ambos' ? ['public', 'monitor'] : [alvo]);
    // Esta tela neutra está no ar em todas as telas escolhidas?
    const noAr = tipo => telasDoAlvo().every(t => estado[t] === tipo);

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
        document.querySelectorAll('[data-neutra-alvo]').forEach(b => {
            b.setAttribute('aria-pressed', b.dataset.neutraAlvo === alvo ? 'true' : 'false');
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

    // Estado vindo do servidor: evento 'blackout' ou /api/telao-status
    function mostrar(dados) {
        if (dados && dados.telas) estado = { public: dados.telas.public || null, monitor: dados.telas.monitor || null };
        else if (dados) estado = { ...estado, public: dados.active ? (dados.tipo || 'preta') : null };
        render();
    }

    function alternar(tipo) {
        const ligar = !noAr(tipo);
        const telas = telasDoAlvo();
        socket.emit('blackout', { active: ligar, tipo, telas });
        telas.forEach(t => { estado[t] = ligar ? tipo : null; });
        render();
    }

    function iniciar(sock) {
        socket = sock;
        botoes().forEach(btn => {
            btn.dataset.tituloOriginal = btn.title || '';
            btn.addEventListener('click', () => alternar(btn.dataset.telaNeutra));
        });
        document.querySelectorAll('[data-neutra-alvo]').forEach(b => b.addEventListener('click', () => {
            alvo = b.dataset.neutraAlvo;
            try { localStorage.setItem(CHAVE_ALVO, alvo); } catch (e) { /* sem storage */ }
            render();
        }));
        socket.on('blackout', mostrar);
        render();
    }

    // control.js avisa qual tela a prévia está mostrando (público/palco)
    function setPrevia(tela) { previa = tela; render(); }

    window.TelasNeutras = { iniciar, mostrar, setPrevia };
})();
