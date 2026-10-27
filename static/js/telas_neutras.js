// Telas neutras do telão público: preta, branca e com o logo da igreja.
// Botões com data-tela="preta|branca|logo" em qualquer página de operador
// (control.html, presenter.html). Tocar liga aquela tela; tocar de novo
// (ou "Voltar a imagem") volta o que estava no ar. O servidor guarda qual
// está ligada (handle_blackout) e avisa todo mundo pelo evento 'blackout'.
(function () {
    const ROTULO = { preta: 'Preta', branca: 'Branca', logo: 'Logo' };
    const ICONE = { preta: 'fas fa-moon', branca: 'far fa-square', logo: 'fas fa-church' };
    const AVISO = {
        preta: 'Tela preta: o público vê tudo preto',
        branca: 'Tela branca: o público vê tudo branco',
        logo: 'Logo: o público vê o logo da igreja',
    };
    let ativo = false, tipo = 'preta';
    let socket = null;

    function botoes() { return document.querySelectorAll('[data-tela]'); }

    function mostrar(novoAtivo, novoTipo) {
        ativo = !!novoAtivo;
        if (novoTipo) tipo = novoTipo;
        botoes().forEach(btn => {
            const este = ativo && btn.dataset.tela === tipo;
            btn.classList.toggle('active', este);
            btn.setAttribute('aria-pressed', este ? 'true' : 'false');
            // No ar: o mesmo botão volta a imagem (como o antigo "Tela preta")
            const span = btn.querySelector('span');
            if (span) span.textContent = este ? _t('Voltar') : _t(ROTULO[btn.dataset.tela]);
            const icone = btn.querySelector('i');
            if (icone) icone.className = este ? 'fas fa-rotate-left' : ICONE[btn.dataset.tela];
            if (este) btn.title = _t('Voltar a imagem');
            else if (btn.dataset.tituloOriginal != null) btn.title = btn.dataset.tituloOriginal;
        });
        // Aviso em cima da prévia do Controle
        const aviso = document.getElementById('preview-blackout');
        if (aviso) {
            aviso.hidden = !ativo;
            aviso.dataset.tipo = tipo;
            const txt = aviso.querySelector('span');
            if (txt) txt.textContent = _t(AVISO[tipo]);
            const icone = aviso.querySelector('i');
            if (icone) icone.className = ICONE[tipo];
        }
    }

    function alternar(qual) {
        const ligar = !(ativo && tipo === qual);
        socket.emit('blackout', { active: ligar, tipo: qual });
        mostrar(ligar, qual);
    }

    function iniciar(sock) {
        socket = sock;
        botoes().forEach(btn => {
            btn.dataset.tituloOriginal = btn.title || '';
            btn.addEventListener('click', () => alternar(btn.dataset.tela));
        });
        socket.on('blackout', d => mostrar(d && d.active, d && d.tipo));
    }

    window.TelasNeutras = { iniciar, mostrar };
})();
