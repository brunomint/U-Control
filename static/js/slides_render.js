// Uma tela dos Slides (slides_store.py: texto ou lista) em HTML — o mesmo
// código no telão do público (display_public.js) e na prévia da página
// /slides, pra prévia mostrar o que vai pro ar. O tamanho da letra vem de
// fora (o telão encolhe o bloco até caber); aqui tudo é em "em".
window.UcSlides = (function () {
    const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

    function html(tela) {
        if (typeof tela === 'string') return UcFormato.html(tela);   // avisos antigos (só texto)
        if (!tela) return '';
        if (tela.tipo !== 'lista') return UcFormato.html(tela.texto || '');
        const titulo = tela.titulo || tela.parte
            ? `<div class="sl-titulo">${esc(tela.titulo)}${tela.parte ? ` <span class="sl-parte">${esc(tela.parte)}</span>` : ''}</div>` : '';
        const linhas = (tela.linhas || []).map(([rotulo, valor]) => {
            // Só uma das partes (ex.: uma lista de nomes): ocupa a linha inteira
            if (!rotulo || !valor) return `<div class="sl-linha sl-linha-uma">${esc(rotulo || valor)}</div>`;
            return `<div class="sl-linha"><span class="sl-rotulo">${esc(rotulo)}</span><span class="sl-valor">${esc(valor)}</span></div>`;
        }).join('') + '<div class="sl-linha sl-vazia"><span class="sl-rotulo">&nbsp;</span><span class="sl-valor">&nbsp;</span></div>'
            .repeat(Math.max(0, Math.min(15, Number(tela.completar) || 0)));   // mesma altura das outras telas da lista
        return `<div class="sl-lista">${titulo}<div class="sl-linhas">${linhas}</div></div>`;
    }

    return { html };
})();
