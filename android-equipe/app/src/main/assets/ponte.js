// Roda em cada página do U-Control aberta no app (PaginaActivity.onPageFinished).
// O WebView não sabe salvar arquivo gerado na própria página (blob:/data: —
// o PDF da ordem pelo jsPDF, a imagem do calendário) nem imprimir: isto
// entrega os dois ao app (objeto UCApp, PaginaActivity.Ponte).
(function () {
    if (window.__ucApp || !window.UCApp) return;
    window.__ucApp = true;

    function salvarSeFor(a) {
        var href = a.href || '';
        if (href.indexOf('blob:') !== 0 && href.indexOf('data:') !== 0) return false;
        var nome = a.getAttribute('download') || 'arquivo';
        fetch(href)
            .then(function (r) { return r.blob(); })
            .then(function (b) {
                var leitor = new FileReader();
                leitor.onload = function () { UCApp.salvar(leitor.result, nome); };
                leitor.readAsDataURL(b);
            })
            .catch(function () { UCApp.salvar('', nome); });
        return true;
    }

    // Link com download clicado pela pessoa
    document.addEventListener('click', function (e) {
        var a = e.target && e.target.closest ? e.target.closest('a[download]') : null;
        if (a && salvarSeFor(a)) e.preventDefault();
    }, true);

    // Link criado e "clicado" pelo código, fora da página: a.click() ou
    // a.dispatchEvent(new MouseEvent('click')) (o FileSaver do jsPDF faz assim)
    var clicar = HTMLAnchorElement.prototype.click;
    HTMLAnchorElement.prototype.click = function () {
        if (this.hasAttribute('download') && salvarSeFor(this)) return;
        return clicar.apply(this, arguments);
    };
    var disparar = HTMLAnchorElement.prototype.dispatchEvent;
    HTMLAnchorElement.prototype.dispatchEvent = function (ev) {
        if (ev && ev.type === 'click' && !this.isConnected && this.hasAttribute('download') && salvarSeFor(this)) return false;
        return disparar.apply(this, arguments);
    };

    window.print = function () { UCApp.imprimir(); };

    // Aba nova (ex.: o PDF da cifra em /view/<id>/print): o app não tem abas.
    // Da própria igreja abre aqui mesmo — PDF vira download —; de fora, o
    // app certo abre (PaginaActivity.shouldOverrideUrlLoading).
    var abrir = window.open;
    window.open = function (url) {
        if (!url) return abrir.apply(window, arguments);
        location.href = new URL(url, location.href).href;
        return null;
    };
})();
