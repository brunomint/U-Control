// Uma tela dos Slides (slides_store.py: texto ou lista) em HTML — o mesmo
// código no telão do público (display_public.js) e na prévia da página
// /slides, pra prévia mostrar o que vai pro ar. O tamanho da letra vem de
// fora (o telão encolhe o bloco até caber); aqui tudo é em "em".
window.UcSlides = (function () {
    const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

    // anterior: a tela que estava no ar. Se for a mesma lista revelando
    // (mesmo 'grupo'), só a linha nova ganha a animação de entrada.
    function html(tela, anterior) {
        if (typeof tela === 'string') return UcFormato.html(tela);   // avisos antigos (só texto)
        if (!tela) return '';
        if (tela.tipo !== 'lista') return UcFormato.html(tela.texto || '');
        const titulo = tela.titulo || tela.parte
            ? `<div class="sl-titulo">${esc(tela.titulo)}${tela.parte ? ` <span class="sl-parte">${esc(tela.parte)}</span>` : ''}</div>` : '';
        const mostrar = tela.mostrar == null ? Infinity : Number(tela.mostrar);
        const revelando = mesmaLista(tela, anterior) && Number(anterior.mostrar) === mostrar - 1;
        const linhas = (tela.linhas || []).map(([rotulo, valor], k) => {
            // Ainda não revelada: invisível, mas guarda o lugar (nada pula)
            const extra = k >= mostrar ? ' sl-oculta' : (revelando && k === mostrar - 1 ? ' sl-entra' : '');
            // Só uma das partes (ex.: uma lista de nomes): ocupa a linha inteira
            if (!rotulo || !valor) return `<div class="sl-linha sl-linha-uma${extra}">${esc(rotulo || valor)}</div>`;
            return `<div class="sl-linha${extra}"><span class="sl-rotulo">${esc(rotulo)}</span><span class="sl-valor">${esc(valor)}</span></div>`;
        }).join('') + '<div class="sl-linha sl-vazia"><span class="sl-rotulo">&nbsp;</span><span class="sl-valor">&nbsp;</span></div>'
            .repeat(Math.max(0, Math.min(15, Number(tela.completar) || 0)));   // mesma altura das outras telas da lista
        return `<div class="sl-lista">${titulo}<div class="sl-linhas">${linhas}</div></div>`;
    }

    // Mesma lista revelando aos poucos (slides_store.telas: 'grupo'):
    // o telão troca sem a transição do tema
    function mesmaLista(tela, anterior) {
        return !!(tela && anterior && tela.grupo && tela.grupo === anterior.grupo);
    }

    return { html, mesmaLista };
})();
