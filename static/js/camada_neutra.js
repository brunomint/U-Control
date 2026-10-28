// Camada das telas neutras (preta, branca, logo da igreja) nas telas que
// vão pro datashow ou pro palco: telão público, /monitor e /img. Cobre
// tudo — letra, Bíblia, foto, vídeo, site, tela do PC, aviso. O estado
// vem do evento 'blackout' (blueprints/display.py handle_blackout), um por
// tela: `tela` é 'public' ou 'monitor'. Os botões ficam em
// static/js/telas_neutras.js.
window.ucCamadaNeutra = function (socket, tela) {
    let camada = document.getElementById('blackout-layer');
    if (!camada) {
        camada = document.createElement('div');
        camada.id = 'blackout-layer';
        camada.innerHTML = '<img id="blackout-logo" alt="">';
        document.body.appendChild(camada);
    }
    socket.on('blackout', (d) => {
        // Servidor antigo (sem `telas`): só a pública tinha tela preta
        const tipo = d && d.telas ? d.telas[tela] : (tela === 'public' && d && d.active ? (d.tipo || 'preta') : null);
        camada.classList.toggle('active', !!tipo);
        // Troca a cor só quando liga — ao desligar fica a mesma, pro
        // esmaecer não piscar outra cor
        if (tipo) {
            camada.dataset.tipo = tipo;
            if (tipo === 'logo') camada.querySelector('img').src = '/logo-igreja.png?v=' + Date.now();
        }
    });
};
