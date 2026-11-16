// Ordem do culto ao vivo (ordens_ao_vivo.py): alguém salvou uma ordem em
// qualquer aparelho → as páginas abertas que mostram ordens recarregam a
// lista sozinhas, em vez de só ler a ordem ao abrir.
//
// Uso: ucOrdensAoVivo(datas => recarregar());
//   datas: as datas que mudaram ([] = pode ter sido qualquer uma).
//
// Usa o socket que a página já tem (variável global `socket`, ex.:
// control.js); sem ele, abre um (páginas públicas /view e /agenda — o
// aviso leva só as datas, não o conteúdo).
(function () {
    const ouvintes = [];
    let ligado = false;
    let espera = null;
    let pendentes = null;   // null = nada pendente; [] = todas

    function disparar() {
        const datas = pendentes || [];
        pendentes = null;
        ouvintes.forEach(fn => {
            try { fn(datas); } catch (e) { console.error('ordens_ao_vivo:', e); }
        });
    }

    function chegou(msg) {
        const datas = (msg && Array.isArray(msg.datas)) ? msg.datas : [];
        if (pendentes === null) pendentes = datas.slice();
        else pendentes = (pendentes.length && datas.length) ? pendentes.concat(datas) : [];
        // Várias gravações seguidas (a agenda salva dia a dia) = uma recarga só
        clearTimeout(espera);
        espera = setTimeout(disparar, 300);
    }

    function ligar() {
        if (ligado || typeof io !== 'function') return;
        ligado = true;
        const s = (typeof socket !== 'undefined' && socket && typeof socket.on === 'function') ? socket : io();
        s.on('ordens_mudaram', chegou);
        // Voltou a conexão (Wi-Fi caiu, servidor reiniciou): pode ter perdido um aviso
        if (s.io && typeof s.io.on === 'function') s.io.on('reconnect', () => chegou({ datas: [] }));
    }

    window.ucOrdensAoVivo = function (fn) {
        ouvintes.push(fn);
        // Espera os scripts da página (que criam o `socket` deles) rodarem
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ligar);
        else ligar();
    };
})();
