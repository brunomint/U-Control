/* /lite/diag: o que o navegador do aparelho entende.
   Só ES5 (regra da versão simples, docs/PLANO-LITE.md seção 4): este
   arquivo precisa rodar justamente onde o resto do U-Control não roda. */
(function () {
    var resultados = [];

    function mostrar(el) { if (el) { el.removeAttribute('hidden'); el.style.display = ''; } }
    function esconder(el) { if (el) { el.style.display = 'none'; } }

    // Sintaxe nova: testada com new Function, que só falha aqui dentro
    function sintaxe(codigo) {
        try { new Function(codigo); return true; } catch (e) { return false; }
    }

    function css(propriedade, valor) {
        var el = document.createElement('div');
        try { el.style[propriedade] = valor; } catch (e) { return false; }
        return el.style[propriedade] === valor || el.style[propriedade] !== '';
    }

    function cssUnidade(valor) {
        var el = document.createElement('div');
        try { el.style.width = valor; } catch (e) { return false; }
        return el.style.width !== '';
    }

    function variaveisCss() {
        var el = document.createElement('div');
        try {
            el.style.setProperty('--teste', '1px');
            el.style.setProperty('width', 'var(--teste)');
        } catch (e) { return false; }
        return el.style.getPropertyValue('width') !== '';
    }

    function storage() {
        try {
            window.localStorage.setItem('uc_diag', '1');
            window.localStorage.removeItem('uc_diag');
            return true;
        } catch (e) { return false; }
    }

    function existe(nome, valor) { resultados.push({ grupo: 'API', nome: nome, ok: !!valor }); }
    function sint(nome, codigo) { resultados.push({ grupo: 'Sintaxe', nome: nome, ok: sintaxe(codigo) }); }
    function estilo(nome, ok) { resultados.push({ grupo: 'CSS', nome: nome, ok: !!ok }); }

    sint('let/const', '"use strict"; let a = 1; const b = 2;');
    sint('let/const fora do modo estrito', 'let a = 1; const b = 2;');
    sint('arrow (=>)', 'var f = function () {}; f = (x) => x;');
    sint('template string', 'var s = `a${1}`;');
    sint('class', '"use strict"; class A {}');
    sint('async/await', 'async function f() { await 1; }');
    sint('desestruturação', 'var o = {}; var { a } = o;');
    sint('?. e ??', 'var o = null; var a = o?.b ?? 1;');

    existe('XMLHttpRequest', window.XMLHttpRequest);
    existe('fetch', window.fetch);
    existe('Promise', window.Promise);
    existe('WebSocket', window.WebSocket);
    existe('localStorage (gravar)', storage());
    existe('requestAnimationFrame', window.requestAnimationFrame || window.webkitRequestAnimationFrame);
    existe('JSON', window.JSON);
    existe('addEventListener', document.addEventListener);
    existe('querySelector', document.querySelector);
    existe('classList', 'classList' in document.documentElement);
    existe('Object.assign', Object.assign);
    existe('String.startsWith', String.prototype.startsWith);
    existe('NodeList.forEach', window.NodeList && NodeList.prototype.forEach);
    existe('EventSource', window.EventSource);

    estilo('flexbox', css('display', 'flex') || css('display', '-webkit-flex'));
    estilo('flexbox antigo (-webkit-box)', css('display', '-webkit-box'));
    estilo('grid', css('display', 'grid'));
    estilo('variáveis CSS (var(--))', variaveisCss());
    estilo('unidade vh', cssUnidade('50vh'));
    estilo('unidade rem', cssUnidade('2rem'));
    estilo('calc()', cssUnidade('calc(10px + 1px)') || cssUnidade('-webkit-calc(10px + 1px)'));
    estilo('position: sticky', css('position', 'sticky') || css('position', '-webkit-sticky'));
    estilo('object-fit', css('objectFit', 'contain'));

    var tela = 'tela ' + screen.width + 'x' + screen.height +
        ', janela ' + window.innerWidth + 'x' + window.innerHeight +
        ', densidade ' + (window.devicePixelRatio || 1);

    // ---- Na página ----
    esconder(document.getElementById('semJs'));
    mostrar(document.getElementById('comJs'));
    document.getElementById('ua').appendChild(document.createTextNode(navigator.userAgent + ' — ' + tela));

    var corpo = document.getElementById('tabela').getElementsByTagName('tbody')[0];
    var grupoAnterior = '';
    for (var i = 0; i < resultados.length; i++) {
        var r = resultados[i];
        if (r.grupo !== grupoAnterior) {
            var cab = document.createElement('tr');
            var th = document.createElement('th');
            th.colSpan = 2;
            th.appendChild(document.createTextNode(r.grupo));
            cab.appendChild(th);
            corpo.appendChild(cab);
            grupoAnterior = r.grupo;
        }
        var tr = document.createElement('tr');
        var nome = document.createElement('td');
        nome.appendChild(document.createTextNode(r.nome));
        var res = document.createElement('td');
        res.className = r.ok ? 'lite-sim' : 'lite-nao';
        res.appendChild(document.createTextNode(r.ok ? 'sim' : 'não'));
        tr.appendChild(nome);
        tr.appendChild(res);
        corpo.appendChild(tr);
    }

    // ---- Mandar ao servidor (uma imagem: funciona em qualquer navegador) ----
    var botao = document.getElementById('enviar');
    var aviso = document.getElementById('enviado');
    mostrar(botao);
    botao.onclick = function () {
        var nao = [];
        for (var j = 0; j < resultados.length; j++) if (!resultados[j].ok) nao.push(resultados[j].nome);
        var texto = navigator.userAgent + ' | ' + tela + ' | NÃO TEM: ' + (nao.length ? nao.join(', ') : 'nada');
        var img = new Image();
        img.onload = img.onerror = function () { aviso.innerHTML = ''; aviso.appendChild(document.createTextNode('Enviado. Obrigado!')); };
        img.src = '/lite/diag/relatorio?d=' + encodeURIComponent(texto) + '&t=' + new Date().getTime();
        aviso.innerHTML = '';
        aviso.appendChild(document.createTextNode('Enviando…'));
    };
})();
