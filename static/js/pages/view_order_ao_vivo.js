// /view/order/<data>: a página vem pronta do servidor — mudou esta ordem
// em outro aparelho, recarrega (static/js/ordens_ao_vivo.js). Os "feitos"
// continuam vindo pelo view_order.js.
(function () {
    let data = '';
    try { data = JSON.parse(document.getElementById('view-order-data').textContent).date || ''; } catch (e) { /* sem dados: recarrega com qualquer mudança */ }
    ucOrdensAoVivo(datas => {
        if (!data || !datas.length || datas.includes(data)) location.reload();
    });
})();
