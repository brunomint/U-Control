// Capotraste no monitor dos músicos (display.html?host=monitor).
//
// Cada aparelho escolhe o seu: a música em Lá com capo na 2ª casa aparece
// em Sol — os acordes que o violonista vai fazer, com o aviso "Capo 2".
// Fica só neste aparelho (localStorage) e não muda o tom de ninguém; o
// tom escolhido pelo operador já vem aplicado no texto, o capo vem por cima.
(function () {
    const CHAVE = 'ucCapo';
    let casa = 0;
    try { casa = Math.max(0, Math.min(11, parseInt(localStorage.getItem(CHAVE), 10) || 0)); } catch (e) { /* sem storage */ }

    let botao = null, menu = null, aoMudar = () => {};

    function rotulo() { return casa ? _t('Capo {n}', { n: casa }) : _t('Capo'); }

    function definir(n) {
        casa = n;
        try { localStorage.setItem(CHAVE, String(n)); } catch (e) { /* sem storage */ }
        botao.textContent = rotulo();
        botao.classList.toggle('ligado', casa > 0);
        menu.querySelectorAll('button').forEach(b => b.classList.toggle('ativo', Number(b.dataset.casa) === casa));
        menu.hidden = true;
        aoMudar();
    }

    // Monta o botão (uma vez) e chama onChange quando a casa muda
    function iniciar(onChange) {
        aoMudar = onChange || aoMudar;
        botao = document.createElement('button');
        botao.type = 'button';
        botao.id = 'capo-botao';
        botao.hidden = true;
        botao.title = _t('Capotraste: mostra os acordes como você vai tocar (só neste aparelho)');
        menu = document.createElement('div');
        menu.id = 'capo-menu';
        menu.hidden = true;
        menu.setAttribute('role', 'menu');
        menu.innerHTML = Array.from({ length: 8 }, (_, n) =>
            `<button type="button" role="menuitem" data-casa="${n}">${n ? n : _t('Sem capo')}</button>`).join('');
        botao.addEventListener('click', e => { e.stopPropagation(); menu.hidden = !menu.hidden; });
        menu.addEventListener('click', e => {
            const b = e.target.closest('[data-casa]');
            if (b) definir(Number(b.dataset.casa));
        });
        document.addEventListener('click', () => { menu.hidden = true; });
        document.body.append(botao, menu);
        botao.textContent = rotulo();
        botao.classList.toggle('ligado', casa > 0);
        menu.querySelectorAll('button').forEach(b => b.classList.toggle('ativo', Number(b.dataset.casa) === casa));
    }

    // Texto com as linhas de acorde descidas `casa` semitons
    function aplicar(texto) {
        return casa && texto ? ChordLines.transposeBlockContent(texto, -casa) : texto;
    }

    // O botão só aparece quando a tela tem cifra
    function mostrar(temCifra) {
        if (!botao) return;
        botao.hidden = !temCifra;
        if (!temCifra) menu.hidden = true;
    }

    window.Capo = { iniciar, aplicar, mostrar, get casa() { return casa; } };
})();
