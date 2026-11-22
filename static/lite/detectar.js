/* Navegador antigo? Vai para a versão simples (docs/PLANO-LITE.md, Fase 1).
   Carregado logo no começo das páginas normais (base.html e as telas).
   Testa no próprio navegador, em vez de adivinhar pelo nome dele (o iPad
   novo se diz "Macintosh"):
   - toda página: JS novo (let/const, =>, template string, fetch, Promise);
   - páginas do tema do app (data-tema="1"): também variáveis CSS e async.
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

    var novo = entende('let a = 1; const b = (x) => `${x}`;') && !!window.fetch && !!window.Promise;
    if (novo && tema) {
        novo = entende('async function f() { await 0; }') &&
            !!(window.CSS && window.CSS.supports && window.CSS.supports('--a', '0'));
    }
    var forcado = /(^|;\s*)uc_lite=1/.test(cookie);
    if (novo && !forcado) return;

    var caminho = location.pathname;
    var destino;
    if (caminho === '/monitor' || caminho === '/lyrics/display') {
        destino = '/lite/monitor';
    } else if (caminho.indexOf('/lyrics/display/public') === 0 || caminho === '/img') {
        destino = '/lite/publico';
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
