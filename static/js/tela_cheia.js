// Tela aberta pelo "Abrir no datashow" do Controle (?tela_cheia=1,
// screen_picker.js). O navegador só põe em tela cheia com um clique: o
// "Pôr em tela cheia" do Controle empresta o clique pra esta janela
// (postMessage com delegate: 'fullscreen'). Também vale um clique/tecla
// aqui mesmo.
(function () {
    if (!/[?&]tela_cheia=1/.test(location.search) || !document.documentElement.requestFullscreen) return;
    const cheia = () => !!document.fullscreenElement;
    const entrar = () => { if (!cheia()) document.documentElement.requestFullscreen().catch(() => {}); };
    entrar();
    const dica = document.createElement('div');
    dica.textContent = _t('Clique aqui para tela cheia');
    dica.style.cssText = 'position:fixed;left:50%;bottom:24px;transform:translateX(-50%);z-index:99999;' +
        'background:rgba(0,0,0,.75);color:#fff;font:600 18px system-ui,sans-serif;padding:12px 20px;border-radius:10px;';
    setTimeout(() => { if (!cheia()) document.body.appendChild(dica); }, 1200);
    const gesto = () => { entrar(); dica.remove(); };
    document.addEventListener('pointerdown', gesto, { once: true });
    document.addEventListener('keydown', gesto, { once: true });
    document.addEventListener('fullscreenchange', () => { if (cheia()) dica.remove(); });
    const responder = (uc) => { if (window.opener) window.opener.postMessage({ uc }, location.origin); };
    window.addEventListener('message', e => {
        if (e.origin !== location.origin || !e.data || e.data.uc !== 'tela_cheia') return;
        document.documentElement.requestFullscreen()
            .then(() => { dica.remove(); responder('tela_cheia_ok'); })
            .catch(() => responder('tela_cheia_falhou'));
    });
    responder('tela_pronta');
})();
