/* Tela da versão simples (/lite/monitor e /lite/publico).
   Pergunta ao U-Control o que mostrar (/lite/api/estado) a cada 1,5 s e só
   redesenha quando a `rev` muda. Sem Socket.IO: navegador antigo.
   Só ES5 (docs/PLANO-LITE.md, seção 4). */
(function () {
    var INTERVALO = 1500;
    var ESPERA_SEM_CONEXAO = 3000;
    var LIMITE_PEDIDO = 6000;

    var tela = document.body.getAttribute('data-tela');
    var palco = document.getElementById('palco');
    var conteudo = document.getElementById('conteudo');
    var semConexao = document.getElementById('semConexao');
    var letreiro = document.getElementById('letreiro');
    var rev = '';
    // Diferença entre a hora do servidor e a deste aparelho (o relógio de
    // aparelho antigo costuma estar errado): relógio e cronômetro usam a do servidor
    var diferenca = 0;
    var falhas = 0;
    var ultimo = null;
    var relogio = null;
    var avisos = null;

    // ---- Ajudantes ----

    function texto(t) { return document.createTextNode(t == null ? '' : String(t)); }

    function el(tag, classe, filho) {
        var e = document.createElement(tag);
        if (classe) e.className = classe;
        if (filho != null) e.appendChild(typeof filho === 'string' ? texto(filho) : filho);
        return e;
    }

    function limpar(no) { while (no.firstChild) no.removeChild(no.firstChild); }

    function mostrar(no, sim) {
        if (sim) { no.removeAttribute('hidden'); no.style.display = ''; } else { no.style.display = 'none'; }
    }

    function altura() { return window.innerHeight || document.documentElement.clientHeight; }
    function largura() { return window.innerWidth || document.documentElement.clientWidth; }

    function ajustarPalco() {
        palco.style.height = altura() + 'px';
        if (ultimo) caber();
    }

    // Maior fonte em que o bloco cabe na tela (busca binária: poucas medidas)
    function caberBloco(bloco, maximo, minimo) {
        var h = altura() * 0.92, w = largura() * 0.96;
        var lo = minimo, hi = maximo;
        for (var i = 0; i < 9; i++) {
            var meio = Math.floor((lo + hi) / 2);
            bloco.style.fontSize = meio + 'px';
            if (bloco.offsetHeight <= h && bloco.scrollWidth <= w) lo = meio; else hi = meio;
            if (hi - lo <= 1) break;
        }
        bloco.style.fontSize = lo + 'px';
    }

    function caber() {
        var blocos = conteudo.getElementsByTagName('div');
        for (var i = 0; i < blocos.length; i++) {
            if (blocos[i].className.indexOf('lite-caber') >= 0) {
                caberBloco(blocos[i], Math.floor(altura() / 4), 12);
            }
        }
    }

    function pararTimers() {
        if (relogio) { clearInterval(relogio); relogio = null; }
        if (avisos) { clearInterval(avisos); avisos = null; }
    }

    function doisDigitos(n) { return n < 10 ? '0' + n : '' + n; }

    function agoraServidor() { return new Date().getTime() + diferenca; }

    // ---- Cada modo ----

    function desenharLetra(e) {
        var bloco = el('div', 'lite-caber lite-letra');
        for (var i = 0; i < (e.linhas || []).length; i++) {
            if (i) bloco.appendChild(document.createElement('br'));
            bloco.appendChild(texto(e.linhas[i]));
        }
        conteudo.appendChild(bloco);
    }

    function desenharCifra(e) {
        var bloco = el('div', 'lite-caber lite-cifra-bloco');
        var titulo = e.musica ? e.musica + (e.secao ? ' — ' + e.secao : '') : e.secao;
        if (titulo) bloco.appendChild(el('div', 'lite-cifra-titulo', titulo));
        if (e.html != null) {
            var pre = el('pre', 'lite-cifra');
            pre.innerHTML = e.html;   // HTML montado e escapado pelo servidor (chord_lines.py)
            bloco.appendChild(pre);
        }
        if (e.a_seguir) bloco.appendChild(el('div', 'lite-a-seguir', 'A seguir: ' + e.a_seguir));
        conteudo.appendChild(bloco);
    }

    function desenharBiblia(e) {
        var bloco = el('div', 'lite-caber lite-biblia');
        bloco.appendChild(el('div', 'lite-biblia-texto', e.texto));
        bloco.appendChild(el('div', 'lite-biblia-ref', e.referencia + (e.versao ? ' (' + e.versao + ')' : '')));
        conteudo.appendChild(bloco);
    }

    function desenharImagem(url) {
        var img = el('img', 'lite-imagem');
        img.style.maxHeight = altura() + 'px';
        img.src = url;
        conteudo.appendChild(img);
    }

    function desenharRelogio() {
        var bloco = el('div', 'lite-relogio');
        function agora() {
            var d = new Date(agoraServidor());
            limpar(bloco);
            bloco.appendChild(texto(doisDigitos(d.getHours()) + ':' + doisDigitos(d.getMinutes())));
        }
        agora();
        relogio = setInterval(agora, 1000);
        conteudo.appendChild(bloco);
    }

    // Tempo que falta (mm:ss); passou do tempo: "+mm:ss" em vermelho
    function desenharCronometro(e) {
        var bloco = el('div', 'lite-cronometro');
        var numero = el('div', 'lite-cronometro-tempo');
        if (e.titulo) bloco.appendChild(el('div', 'lite-cronometro-titulo', e.titulo));
        bloco.appendChild(numero);
        function mostrar() {
            var ms = e.pausado ? (e.restante || 0) : (e.fim - agoraServidor());
            var passou = ms < 0;
            var s = Math.floor(Math.abs(ms) / 1000) + (passou ? 0 : (Math.abs(ms) % 1000 ? 1 : 0));
            var texto = (passou ? '+' : '') + Math.floor(s / 60) + ':' + doisDigitos(s % 60);
            numero.className = 'lite-cronometro-tempo' + (passou ? ' lite-passou' : s <= 60 ? ' lite-acabando' : '');
            limpar(numero);
            numero.appendChild(document.createTextNode(texto));
        }
        mostrar();
        if (!e.pausado) relogio = setInterval(mostrar, 250);
        else bloco.appendChild(el('div', 'lite-cronometro-titulo', 'pausado'));
        conteudo.appendChild(bloco);
    }

    function desenharLetreiro(texto) {
        limpar(letreiro);
        if (texto) letreiro.appendChild(document.createTextNode(texto));
        mostrar(letreiro, !!texto);
    }

    function desenharAvisos(e) {
        var lista = e.avisos || [];
        var bloco = el('div', 'lite-caber lite-letra');
        var i = 0;
        function proximo() {
            limpar(bloco);
            bloco.appendChild(texto(lista.length ? lista[i % lista.length] : ''));
            i++;
            caber();
        }
        conteudo.appendChild(bloco);
        proximo();
        if (lista.length > 1) avisos = setInterval(proximo, Math.max(3, e.segundos || 8) * 1000);
    }

    function desenhar(e) {
        pararTimers();
        limpar(conteudo);
        ultimo = e;
        var fundo = 'lite-tela lite-tela-' + tela + ' lite-modo-' + e.modo;
        if (e.modo === 'neutra') fundo += ' lite-neutra-' + e.tipo;
        document.body.className = fundo;

        if (e.modo === 'neutra') {
            if (e.tipo === 'logo' && e.url) desenharImagem(e.url);
        } else if (e.modo === 'letra') {
            desenharLetra(e);
        } else if (e.modo === 'cifra') {
            desenharCifra(e);
        } else if (e.modo === 'biblia') {
            desenharBiblia(e);
        } else if (e.modo === 'imagem') {
            desenharImagem(e.url);
        } else if (e.modo === 'relogio') {
            desenharRelogio();
        } else if (e.modo === 'cronometro') {
            desenharCronometro(e);
        } else if (e.modo === 'avisos') {
            desenharAvisos(e);
        } else if (e.modo === 'outro' && e.texto) {
            conteudo.appendChild(el('p', 'lite-espera', e.texto));
        }
        if (e.aviso) conteudo.appendChild(el('p', 'lite-aviso', e.aviso));
        desenharLetreiro(e.letreiro);
        caber();
    }

    // ---- Conversa com o U-Control ----

    function proximaVez(ms) { setTimeout(pedir, ms); }

    function falhou() {
        falhas++;
        if (falhas >= 2) mostrar(semConexao, true);   // o que estava na tela continua
        proximaVez(ESPERA_SEM_CONEXAO);
    }

    function pedir() {
        var xhr = new XMLHttpRequest();
        var terminou = false;
        var limite = setTimeout(function () {
            if (terminou) return;
            terminou = true;
            try { xhr.abort(); } catch (e) { /* já fechado */ }
            falhou();
        }, LIMITE_PEDIDO);
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== 4 || terminou) return;
            terminou = true;
            clearTimeout(limite);
            if (xhr.status !== 200) { falhou(); return; }
            var e;
            try { e = JSON.parse(xhr.responseText); } catch (erro) { falhou(); return; }
            falhas = 0;
            mostrar(semConexao, false);
            if (e.agora) diferenca = e.agora - new Date().getTime();
            if (!e.igual && e.rev !== rev) {
                rev = e.rev;
                desenhar(e);
            }
            proximaVez(INTERVALO);
        };
        xhr.open('GET', '/lite/api/estado?tela=' + tela + '&rev=' + rev + '&t=' + new Date().getTime(), true);
        xhr.send(null);
    }

    window.onresize = ajustarPalco;
    window.onorientationchange = function () { setTimeout(ajustarPalco, 300); };
    ajustarPalco();
    pedir();
})();
