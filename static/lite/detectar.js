/* Navegador antigo? Vai para a versão simples (docs/PLANO-LITE.md, Fase 1).
   Carregado logo no começo das páginas normais (base.html e as telas).
   Testa no próprio navegador, em vez de adivinhar pelo nome dele (o iPad
   novo se diz "Macintosh"):
   - toda página: o JS que o app usa (let/const, =>, template string,
     async, ...spread, ?. e ??, fetch, Promise). O ?./?? (2020) é o que
     falta no iOS 10.3: sem ele, o display.js da cifra e o control.js não rodam;
   - páginas do tema do app (data-tema="1"): também variáveis CSS.
   Cookie uc_lite (blueprints/lite.py): '0' = sempre a versão completa,
   '1' = sempre a simples, sem cookie = este teste decide.
   Só ES5: precisa rodar justamente onde o resto não roda. */
(function () {
    var cookie = document.cookie || '';
    if (/(^|;\s*)uc_lite=0/.test(cookie)) return;
    // Dentro de outra página (prévias do Controle): quem decide é a de fora
    try { if (window.top !== window.self) return; } catch (e) { return; }

    var scripts = document.getElementsByTagName('script');
    var este = scripts[scripts.length - 1];
    var tema = este && este.getAttribute('data-tema') === '1';

    function entende(codigo) {
        try { new Function(codigo); return true; } catch (e) { return false; }
    }

    var novo = entende('let a = 1; const b = (x) => `${x}`;') &&
        entende('async function f() { await 0; }') &&
        entende('var o = { ...{} }; var a = o?.b ?? 1;') && !!window.fetch && !!window.Promise;
    if (novo && tema) {
        novo = !!(window.CSS && window.CSS.supports && window.CSS.supports('--a', '0'));
    }
    var forcado = /(^|;\s*)uc_lite=1/.test(cookie);
    if (novo && !forcado) return;

    var caminho = location.pathname;
    var destino;
    if (caminho === '/monitor' || caminho === '/lyrics/display') {
        destino = '/lite/monitor';
    } else if (caminho.indexOf('/lyrics/display/public') === 0 || caminho === '/img') {
        destino = '/lite/publico';
    } else if (caminho === '/control' || caminho === '/presenter' || /^\/lyrics\/\d+$/.test(caminho)) {
        destino = '/lite/controle';
    } else if (caminho === '/view') {
        destino = '/lite/cifras' + location.search;
    } else if (/^\/view\/\d+$/.test(caminho)) {
        destino = '/lite/cifra/' + caminho.split('/')[2] + location.search;
    } else if (/^\/view\/order\/[0-9-]+$/.test(caminho)) {
        destino = '/lite/cifras?order=' + caminho.split('/')[3];
    } else if (caminho === '/login' || caminho === '/links') {
        if (forcado) return;   // já está no tema simples
        destino = caminho + (location.search ? location.search + '&' : '?') + 'lite=1';
    } else if (caminho === '/' || caminho === '/dashboard') {
        destino = '/lite/';
    } else {
        destino = '/lite/?de=' + encodeURIComponent(caminho + location.search);
    }
    location.replace(destino);
})();
