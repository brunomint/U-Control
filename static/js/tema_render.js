// Estilo da letra de um tema do telão (temas_store.py) — o mesmo código no
// telão do público (display_public.js) e na prévia do editor (temas.js),
// para a prévia mostrar exatamente o que vai pro telão.
window.UcTema = (function () {
    // Mesmas fontes de temas_store.FONTES (o teste confere)
    const FONTES = {
        arial: "Arial, 'Liberation Sans', Helvetica, sans-serif",
        manrope: "Manrope, Arial, sans-serif",
        roboto: "Roboto, Arial, sans-serif",
        merriweather: "Merriweather, Georgia, serif",
        georgia: "Georgia, 'DejaVu Serif', serif",
        verdana: "Verdana, 'DejaVu Sans', sans-serif",
    };

    function rgba(hex, opacidade) {
        const n = parseInt(String(hex || '#000000').slice(1), 16);
        return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${opacidade})`;
    }

    // Contorno com 8 sombras (fica igual em toda fonte e tamanho; o
    // text-stroke "come" a letra por dentro) + sombra projetada opcional
    function sombras(t) {
        const lista = [];
        const e = (Number(t.contorno) || 0) * 0.005;
        if (e > 0) {
            for (let a = 0; a < 8; a++) {
                const x = Math.cos(a * Math.PI / 4) * e, y = Math.sin(a * Math.PI / 4) * e;
                lista.push(`${x.toFixed(4)}em ${y.toFixed(4)}em 0 ${t.contorno_cor}`);
            }
        }
        if (t.sombra) lista.push(`0 0.04em 0.08em ${rgba(t.sombra_cor, 0.7)}`);
        return lista.length ? lista.join(', ') : 'none';
    }

    const EIXO = { esquerda: 'flex-start', centro: 'center', direita: 'flex-end', topo: 'flex-start', meio: 'center', base: 'flex-end' };
    const ALINHA = { esquerda: 'left', centro: 'center', direita: 'right' };

    // lyricsEl: a área inteira (flex coluna); textEl: o bloco da letra
    function aplicarTexto(lyricsEl, textEl, t) {
        lyricsEl.style.justifyContent = EIXO[t.posicao] || 'center';
        lyricsEl.style.alignItems = EIXO[t.alinhamento] || 'center';
        // Padding em % é sempre da largura: em cima e embaixo, margem% da altura de uma tela 16:9
        lyricsEl.style.padding = `${(t.margem * 9 / 16).toFixed(2)}% ${t.margem}%`;
        const s = textEl.style;
        s.fontFamily = FONTES[t.fonte] || FONTES.arial;
        s.fontWeight = t.negrito ? '900' : '400';
        s.fontStyle = t.italico ? 'italic' : 'normal';
        s.color = t.cor;
        s.textTransform = t.maiusculas ? 'uppercase' : 'none';
        s.lineHeight = String(t.entrelinhas);
        s.textAlign = ALINHA[t.alinhamento] || 'center';
        s.textShadow = sombras(t);
        s.maxWidth = '100%';
        s.margin = '0';
        if (t.caixa) {
            s.width = 'fit-content';
            s.background = rgba(t.caixa_cor, (Number(t.caixa_opacidade) || 0) / 100);
            s.padding = '0.25em 0.6em';
            s.borderRadius = `${(Number(t.caixa_arredondada) || 0) * 0.06}em`;
        } else {
            s.width = '';
            s.background = 'transparent';
            s.padding = '0';
            s.borderRadius = '0';
        }
    }

    // Maior tamanho (até max, na unidade dada) em que a letra cabe na área
    // (descontada a margem). unidade: 'vw' no telão, 'px' na prévia.
    function ajustar(lyricsEl, textEl, max, unidade, passo) {
        const estilo = getComputedStyle(lyricsEl);
        const altura = lyricsEl.clientHeight - parseFloat(estilo.paddingTop) - parseFloat(estilo.paddingBottom);
        let tamanho = max;
        textEl.style.fontSize = tamanho + unidade;
        while (textEl.scrollHeight > altura && tamanho > passo * 2) {
            tamanho -= passo;
            textEl.style.fontSize = tamanho + unidade;
        }
        return tamanho;
    }

    // Fundo como CSS (prévias pequenas); vídeo e imagem a página trata à parte
    function fundoCss(fundo) {
        if (!fundo) return '#000';
        if (fundo.type === 'color') return fundo.color;
        if (fundo.type === 'gradient') return fundo.css;
        return '#000';
    }

    return { FONTES, aplicarTexto, ajustar, fundoCss };
})();
