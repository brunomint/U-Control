// Rola até um elemento (o versículo ou a parte da música no ar) só dentro
// da própria página. O scrollIntoView também rola as páginas de fora:
// aberta no painel do Controle (iframe), a página do Controle subia junto,
// levando a prévia e os botões. Aqui rola só o contêiner mais próximo
// que tem rolagem, ou a própria página.
(function () {
    function rolavel(el) {
        for (let p = el.parentElement; p && p !== document.body && p !== document.documentElement; p = p.parentElement) {
            const oy = getComputedStyle(p).overflowY;
            if ((oy === 'auto' || oy === 'scroll') && p.scrollHeight > p.clientHeight) return p;
        }
        return null;
    }

    window.ucRolarAte = function (el, opcoes) {
        if (!el) return;
        const suave = !(opcoes && opcoes.instantaneo);
        const caixa = rolavel(el);
        const r = el.getBoundingClientRect();
        if (caixa) {
            const c = caixa.getBoundingClientRect();
            const alvo = caixa.scrollTop + (r.top - c.top) - (caixa.clientHeight - r.height) / 2;
            caixa.scrollTo({ top: Math.max(0, alvo), behavior: suave ? 'smooth' : 'auto' });
        } else {
            const alvo = window.scrollY + r.top - (window.innerHeight - r.height) / 2;
            window.scrollTo({ top: Math.max(0, alvo), behavior: suave ? 'smooth' : 'auto' });
        }
    };
})();
