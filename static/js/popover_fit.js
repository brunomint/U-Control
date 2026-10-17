// Encaixa um menu flutuante (ex.: o "Tom" das páginas de música) dentro da
// tela ao abrir: mede onde ele caiu e empurra pro lado que faltar, com 8px
// de folga. A posição do botão muda com o layout (celular, tablet, PC), então
// regra fixa de CSS (left/right) deixava o menu meio pra fora em alguma
// largura. Usado por lyrics_2.js, new_song.js, edit_song.js e view_song.html.
(function () {
  const FOLGA = 8;
  function ucFitPopover(el) {
    if (!el) return;
    el.style.transform = '';
    el.style.maxWidth = `calc(100vw - ${FOLGA * 2}px)`;
    const r = el.getBoundingClientRect();
    if (!r.width) return;                       // escondido
    let dx = 0;
    if (r.right > window.innerWidth - FOLGA) dx = window.innerWidth - FOLGA - r.right;
    if (r.left + dx < FOLGA) dx = FOLGA - r.left;
    if (dx) el.style.transform = `translateX(${Math.round(dx)}px)`;
  }
  window.ucFitPopover = ucFitPopover;
})();
