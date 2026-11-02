// Quem cuida do palco, no /control: outro aparelho conectado em "Só monitor"
// aparece aqui, com o botão pra assumir quando ele sair ou der problema. O
// botão pede um segundo toque, porque tira o palco de quem está com ele. O
// servidor decide (telao_status: palco_com; assumir_palco em
// blueprints/display.py). Usa o `socket` de pages/control.js.
(function () {
    const CONFIRMAR_MS = 4000;
    const caixa = document.getElementById('palco-com');
    const texto = document.getElementById('palco-com-texto');
    const botao = document.getElementById('assumir-palco');
    if (!caixa) return;
    let espera = null;

    function normal() {
        clearTimeout(espera);
        espera = null;
        botao.textContent = _t('Assumir o palco');
    }

    function mostrar(st) {
        if (!st) return;
        const nome = st.palco_com;
        caixa.hidden = nome === null || nome === undefined;
        if (caixa.hidden) return normal();
        texto.textContent = nome ? _t('Palco com {nome}', { nome }) : _t('Palco com outro aparelho');
    }

    botao.addEventListener('click', () => {
        if (!espera) {
            botao.textContent = _t('Confirmar: assumir o palco');
            espera = setTimeout(normal, CONFIRMAR_MS);
            return;
        }
        normal();
        socket.emit('assumir_palco', {});
    });

    socket.on('telao_status', mostrar);
    socket.on('palco_assumido', d => {
        if (window.ucToast) window.ucToast(_t('{nome} assumiu o palco. Você está em Só público.', { nome: d.por }), 'error');
    });
    fetch('/api/telao-status').then(r => (r.ok ? r.json() : null)).then(mostrar).catch(() => {});
})();
