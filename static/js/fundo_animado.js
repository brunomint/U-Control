// Fundo animado dos temas do telão ({type: 'animado'}, temas_store.py).
// Luzes grandes que se movem devagar sobre uma cor de base. Só CSS, e só
// "transform" e "opacity" animados: a placa de vídeo compõe as camadas sem
// redesenhar a tela a cada quadro — leve até no Raspberry Pi e na TV.
// O mesmo código no telão do público, na Bíblia e nas prévias (temas, slides).
window.UcFundoAnimado = (function () {
    const ESTILOS = ['luzes', 'aurora', 'respirar', 'estrelas'];
    // Multiplica as durações do CSS. Antes 1,7/1/0,55: lento demais, ninguém
    // via mexer (medido 25/11: 'lenta' mudava ~1/255 da tela em 5 s)
    const VELOCIDADES = { lenta: 0.8, normal: 0.45, rapida: 0.25 };
    const ESTRELAS = 70;

    function div(classe, estilo) {
        const d = document.createElement('div');
        d.className = classe;
        if (estilo) d.setAttribute('style', estilo);
        return d;
    }

    // Mesma "sorte" toda vez (prévia e telão com as estrelas no mesmo lugar)
    function sorteador(semente) {
        let s = semente >>> 0;
        return () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; };
    }

    function camadaDe(fundo) {
        const estilo = ESTILOS.includes(fundo.estilo) ? fundo.estilo : 'luzes';
        const cores = (fundo.cores || []).concat(['#4c1d95', '#0e7490', '#1e3a8a']).slice(0, 3);
        const camada = div('uc-fa uc-fa-' + estilo);
        camada.style.background = fundo.base || '#05050c';
        camada.style.setProperty('--uc-fa-vel', VELOCIDADES[fundo.velocidade] || 1);
        if (estilo === 'estrelas') {
            camada.appendChild(div('uc-fa-bolha uc-fa-b1', `--uc-fa-cor:${cores[0]}`));
            camada.appendChild(div('uc-fa-bolha uc-fa-b2', `--uc-fa-cor:${cores[1]}`));
            const sorte = sorteador(7);
            for (let i = 0; i < ESTRELAS; i++) {
                const tam = (0.12 + sorte() * 0.22).toFixed(3);
                camada.appendChild(div('uc-fa-estrela',
                    `left:${(sorte() * 100).toFixed(2)}%;top:${(sorte() * 100).toFixed(2)}%;width:${tam}%;padding-top:${tam}%;` +
                    `background:${i % 4 === 0 ? cores[2] : '#ffffff'};animation-delay:${(-sorte() * 9).toFixed(2)}s;` +
                    `animation-duration:calc(${(4 + sorte() * 6).toFixed(2)}s * var(--uc-fa-vel))`));
            }
        } else {
            cores.forEach((cor, i) => camada.appendChild(div(`uc-fa-bolha uc-fa-b${i + 1}`, `--uc-fa-cor:${cor}`)));
        }
        return camada;
    }

    // el: o contêiner do fundo (posicionado, com overflow escondido).
    // Chamar de novo com o mesmo fundo não recomeça a animação.
    function montar(el, fundo) {
        if (!el) return;
        if (!fundo || fundo.type !== 'animado') { desmontar(el); return; }
        const chave = JSON.stringify(fundo);
        if (el._ucFundoAnimado === chave) return;
        desmontar(el);
        el._ucFundoAnimado = chave;
        el.insertBefore(camadaDe(fundo), el.firstChild);
    }

    function desmontar(el) {
        if (!el) return;
        el._ucFundoAnimado = null;
        el.querySelectorAll(':scope > .uc-fa').forEach(c => c.remove());
    }

    // Parado (tela escondida): não gasta nada
    function pausar(el, parar) {
        if (el) el.querySelectorAll(':scope > .uc-fa').forEach(c => c.classList.toggle('uc-fa-pausado', !!parar));
    }

    // Versão parada, como degradê (miniaturas, e telas que não animam)
    function css(fundo) {
        const c = (fundo.cores || []).concat(['#4c1d95', '#0e7490', '#1e3a8a']);
        return `radial-gradient(circle at 20% 25%,${c[0]} 0%,transparent 50%),` +
            `radial-gradient(circle at 80% 75%,${c[1]} 0%,transparent 50%),` +
            `radial-gradient(circle at 60% 10%,${c[2]} 0%,transparent 40%),${fundo.base || '#05050c'}`;
    }

    return { ESTILOS, VELOCIDADES, montar, desmontar, pausar, css };
})();
