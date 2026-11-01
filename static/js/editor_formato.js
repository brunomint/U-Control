// Botões de formatação do editor de música (_song_editor.html): escrevem as
// marcações de static/js/letra_formato.js em volta do texto selecionado na
// letra (a última caixa de letra usada). Negrito e itálico: clicar de novo
// tira. Usa insertText, então o Ctrl+Z do navegador desfaz.
(function () {
    const barra = document.getElementById('fmtBarra');
    if (!barra) return;
    let caixa = null;   // última caixa de letra com foco

    document.addEventListener('focusin', (e) => {
        if (e.target.matches && e.target.matches('#blockEditor textarea.text-block')) caixa = e.target;
    });
    const aviso = (msg) => { if (window.ucToast) window.ucToast(msg); else alert(msg); };

    function escrever(ta, inicio, fim, texto, selIni, selFim) {
        ta.focus();
        ta.setSelectionRange(inicio, fim);
        if (!document.execCommand || !document.execCommand('insertText', false, texto)) {
            ta.setRangeText(texto, inicio, fim, 'end');
            ta.dispatchEvent(new Event('input', { bubbles: true }));
        }
        ta.setSelectionRange(selIni, selFim);
    }

    function envolver(abre, fecha, alternar) {
        const ta = caixa && document.contains(caixa) ? caixa : null;
        if (!ta) { aviso(_t('Clique na letra e selecione as palavras primeiro.')); return; }
        let ini = ta.selectionStart, fim = ta.selectionEnd;
        const v = ta.value;
        // Clicar de novo no que já está marcado tira a marcação
        if (alternar && v.slice(ini - abre.length, ini) === abre && v.slice(fim, fim + fecha.length) === fecha) {
            const dentro = v.slice(ini, fim);
            escrever(ta, ini - abre.length, fim + fecha.length, dentro, ini - abre.length, fim - abre.length);
            return;
        }
        // Seleção com espaço nas pontas: a marcação fica só em volta das palavras
        while (ini < fim && /\s/.test(v[ini])) ini++;
        while (fim > ini && /\s/.test(v[fim - 1])) fim--;
        const dentro = v.slice(ini, fim);
        escrever(ta, ini, fim, abre + dentro + fecha, ini + abre.length, ini + abre.length + dentro.length);
    }

    function tirar() {
        const ta = caixa && document.contains(caixa) ? caixa : null;
        if (!ta) { aviso(_t('Clique na letra e selecione as palavras primeiro.')); return; }
        let ini = ta.selectionStart, fim = ta.selectionEnd;
        if (ini === fim) { ini = 0; fim = ta.value.length; }   // sem seleção: a caixa inteira
        const limpo = UcFormato.limpar(ta.value.slice(ini, fim));
        escrever(ta, ini, fim, limpo, ini, ini + limpo.length);
    }

    // Menus de cor e tamanho: fixos na tela (a barra rola de lado no celular e cortaria)
    let aberto = null;
    function fecharMenu() { if (aberto) { aberto.remove(); aberto = null; } }
    function menu(botao, itens) {
        fecharMenu();
        const m = document.createElement('div');
        m.className = 'fmt-menu';
        m.setAttribute('role', 'menu');
        itens.forEach(({ html, titulo, acao }) => {
            const b = document.createElement('button');
            b.type = 'button';
            b.setAttribute('role', 'menuitem');
            b.title = titulo;
            b.setAttribute('aria-label', titulo);
            b.innerHTML = html;
            b.addEventListener('mousedown', (e) => e.preventDefault());   // não tira o foco/seleção da letra
            b.addEventListener('click', () => { fecharMenu(); acao(); });
            m.appendChild(b);
        });
        document.body.appendChild(m);
        const r = botao.getBoundingClientRect();
        m.style.top = `${r.bottom + 6}px`;
        m.style.left = `${Math.max(8, Math.min(r.left, window.innerWidth - m.offsetWidth - 8))}px`;
        aberto = m;
    }
    document.addEventListener('click', (e) => { if (aberto && !aberto.contains(e.target) && !e.target.closest('#fmtCor, #fmtTamanho')) fecharMenu(); });
    window.addEventListener('scroll', fecharMenu, true);

    const NOMES = {
        amarelo: _t('Amarelo'), dourado: _t('Dourado'), vermelho: _t('Vermelho'), laranja: _t('Laranja'), verde: _t('Verde'),
        azul: _t('Azul'), roxo: _t('Roxo'), rosa: _t('Rosa'), branco: _t('Branco'), preto: _t('Preto'), cinza: _t('Cinza'),
    };
    const TAMANHOS = { pequeno: _t('Pequeno'), grande: _t('Grande'), maior: _t('Maior') };

    barra.querySelectorAll('button').forEach(b => b.addEventListener('mousedown', (e) => e.preventDefault()));
    document.getElementById('fmtNegrito').addEventListener('click', () => envolver('**', '**', true));
    document.getElementById('fmtItalico').addEventListener('click', () => envolver('*', '*', true));
    document.getElementById('fmtTirar').addEventListener('click', tirar);
    document.getElementById('fmtCor').addEventListener('click', (e) => menu(e.currentTarget,
        Object.entries(UcFormato.CORES).map(([nome, cor]) => ({
            html: `<span class="fmt-cor" style="background:${cor}"></span>`, titulo: NOMES[nome] || nome,
            acao: () => envolver(`{${nome}}`, '{/}'),
        }))));
    document.getElementById('fmtTamanho').addEventListener('click', (e) => menu(e.currentTarget,
        Object.entries(TAMANHOS).map(([nome, rotulo]) => ({
            html: `<span style="font-size:${UcFormato.TAMANHOS[nome]}">A</span> ${rotulo}`, titulo: rotulo,
            acao: () => envolver(`{${nome}}`, '{/}'),
        }))));

    // Atalhos de teclado na letra: Ctrl+B e Ctrl+I
    document.addEventListener('keydown', (e) => {
        if (!(e.ctrlKey || e.metaKey) || e.altKey || !e.target.matches || !e.target.matches('#blockEditor textarea.text-block')) return;
        const k = e.key.toLowerCase();
        if (k === 'b') { e.preventDefault(); caixa = e.target; envolver('**', '**', true); }
        if (k === 'i') { e.preventDefault(); caixa = e.target; envolver('*', '*', true); }
    });
})();
