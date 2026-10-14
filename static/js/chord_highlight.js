// Acordes coloridos dentro do editor de música (edit_song / new_song).
//
// <textarea> não aceita cor por trecho, então o texto colorido é desenhado
// numa camada atrás dela (.chord-backdrop) e a textarea fica com o texto
// transparente — só o cursor e a seleção aparecem por cima. As duas usam a
// mesma fonte monoespaçada, padding e borda, então os caracteres ficam
// exatamente um em cima do outro. A regra de cor é a mesma da página /view:
// ChordLines.highlightLineHtml (static/js/chord_lines.js).
(function () {
  function escapeHtml(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  // Liga a camada colorida a uma textarea que já está (ou vai estar) num
  // container com position: relative. Devolve a função que redesenha.
  function attach(ta) {
    const back = document.createElement('div');
    back.className = 'chord-backdrop';
    back.setAttribute('aria-hidden', 'true');
    ta.classList.add('has-chord-backdrop');
    let styled = false;

    function copyBoxStyle() {
      // Só dá pra ler o estilo calculado com a textarea já na página
      if (!ta.isConnected) return;
      const cs = getComputedStyle(ta);
      ['paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft',
       'borderTopWidth', 'borderRightWidth', 'borderBottomWidth', 'borderLeftWidth',
       'borderRadius', 'fontFamily', 'fontSize', 'lineHeight', 'letterSpacing', 'tabSize']
        .forEach((p) => { back.style[p] = cs[p]; });
      back.style.backgroundColor = cs.backgroundColor;
      ta.style.background = 'transparent';
      styled = true;
    }

    function sync() {
      if (!back.isConnected && ta.parentNode) ta.parentNode.insertBefore(back, ta);
      if (!styled) copyBoxStyle();
      // "\n" no fim: a última linha vazia também ocupa altura
      back.innerHTML = ta.value.split('\n').map((l) => ChordLines.highlightLineHtml(escapeHtml(l))).join('\n') + '\n';
      back.scrollLeft = ta.scrollLeft;
    }

    ta.addEventListener('input', sync);
    ta.addEventListener('scroll', () => { back.scrollLeft = ta.scrollLeft; });
    ta._chordSync = sync;
    return sync;
  }

  window.ChordHighlight = { attach };
})();
