/* Cifra da versão simples (/lite/cifra/<id>): tamanho da letra (A−/A+) e
   rolagem automática. Opcional: sem JS a página funciona igual (Tom e Capo
   são links). Só ES5 (docs/PLANO-LITE.md, seção 4). */
(function () {
    var cifra = document.getElementById('cifra');
    var barra = document.querySelector ? document.querySelector('.lite-so-com-js') : null;
    if (!cifra || !barra) return;
    barra.removeAttribute('hidden');
    barra.style.display = '';

    var CHAVE = 'uc_lite_letra';
    var tamanho = 16;
    try { tamanho = parseInt(window.localStorage.getItem(CHAVE), 10) || 16; } catch (e) { /* sem storage */ }

    function aplicar() {
        tamanho = Math.max(10, Math.min(40, tamanho));
        cifra.style.fontSize = tamanho + 'px';
        try { window.localStorage.setItem(CHAVE, String(tamanho)); } catch (e) { /* vale só agora */ }
    }
    document.getElementById('letraMenor').onclick = function () { tamanho -= 2; aplicar(); };
    document.getElementById('letraMaior').onclick = function () { tamanho += 2; aplicar(); };
    aplicar();

    // Rolar: cada toque troca a velocidade (devagar, médio, rápido, parado)
    var VELOCIDADES = [0, 120, 70, 35];   // ms por pixel; 0 = parado
    var NOMES = ['', 'devagar', 'médio', 'rápido'];
    var nivel = 0;
    var timer = null;
    var botao = document.getElementById('rolar');
    var rotulo = document.getElementById('velocidade');
    botao.onclick = function () {
        nivel = (nivel + 1) % VELOCIDADES.length;
        if (timer) { clearInterval(timer); timer = null; }
        rotulo.innerHTML = '';
        rotulo.appendChild(document.createTextNode(NOMES[nivel]));
        botao.innerHTML = '';
        botao.appendChild(document.createTextNode(nivel ? 'Mais rápido / parar' : 'Rolar'));
        if (!nivel) return;
        timer = setInterval(function () { window.scrollBy(0, 1); }, VELOCIDADES[nivel]);
    };
})();
