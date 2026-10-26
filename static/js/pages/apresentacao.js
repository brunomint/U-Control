// PowerPoint animado numa tela (templates/apresentacao.html). O tocador é
// o do LibreOffice, dentro do SVG; aqui só se comanda e se conta a posição
// ao servidor (blueprints/apresentacao.py).
//
// Posição = slide (a partir de 0) + quantas animações de clique daquele
// slide já tocaram (step). Um "next" sempre termina na hora o que estiver
// tocando antes de avançar um passo: assim todas as telas fazem o mesmo
// passo, mesmo que uma esteja um pouco atrasada na transição.
(function () {
    const params = new URLSearchParams(location.search);
    const svg = params.get('svg');
    const frame = document.getElementById('tocador');
    const aviso = document.getElementById('aviso');
    const socket = io();
    let pronto = false;
    let fila = [];
    // Onde a apresentação está (ou está indo): no meio de uma transição o
    // tocador ainda diz o slide antigo, e contar isso ao servidor fazia as
    // telas "alcançarem" de volta o slide de antes no clique seguinte
    let atual = { slide: 0, step: 0 };

    if (!svg || !svg.startsWith('/static/imagens/') || !svg.endsWith('.svg')) {
        aviso.textContent = _t('Apresentação não encontrada');
        return;
    }

    function w() { return frame.contentWindow; }
    function show() { return w().aSlideShow; }
    function totalSlides() { return w().theMetaDoc.nNumberOfSlides; }
    function totalSteps() {
        const a = show().aNextEffectEventArray;
        return a ? a.size() : 0;
    }
    function posicao() {
        return { svg: svg, slide: atual.slide, step: atual.step, slides: totalSlides(), steps: totalSteps() };
    }
    let recontar = null;
    function contar() {
        socket.emit('apresentacao_pos', posicao());
        // O total de animações do slide novo só existe depois da transição
        clearTimeout(recontar);
        recontar = setTimeout(function () { socket.emit('apresentacao_pos', posicao()); }, 1500);
    }

    function terminarOQueToca() {
        const s = show();
        if (s.isTransitionPlaying()) s.skipTransition();
        if (s.isAnyEffectPlaying()) s.skipAllPlayingEffects();
    }

    // Pula direto (sem transição nem animação) pro slide, com 'step'
    // animações já no fim. step = Infinity: todas (voltar pro slide anterior
    // mostra ele completo, como no PowerPoint)
    function irPara(slide, step) {
        const s = show();
        slide = Math.max(0, Math.min(slide, totalSlides() - 1));
        terminarOQueToca();
        if (w().nCurSlide !== slide || (s.nCurrentEffect || 0) > step) s.displaySlide(slide, true);
        terminarOQueToca();
        while ((s.nCurrentEffect || 0) < Math.min(step, totalSteps())) s.skipNextEffect();
        atual = { slide: slide, step: s.nCurrentEffect || 0 };
    }

    function avancar() {
        const s = show();
        terminarOQueToca();
        if ((s.nCurrentEffect || 0) < totalSteps()) {
            s.nextEffect();
            atual = { slide: atual.slide, step: atual.step + 1 };
        } else if (atual.slide < totalSlides() - 1) {
            s.displaySlide(atual.slide + 1, false);
            atual = { slide: atual.slide + 1, step: 0 };
        }
    }

    function voltar() {
        if (atual.step > 0) irPara(atual.slide, atual.step - 1);
        else if (atual.slide > 0) irPara(atual.slide - 1, Infinity);
    }

    function executar(d) {
        if (d.svg !== svg) return;
        if (d.cmd === 'goto') irPara(d.slide, d.step);
        else {
            if (atual.slide !== d.slide || atual.step !== d.step) irPara(d.slide, d.step);  // alcança as outras
            if (d.cmd === 'next') avancar();
            else if (d.cmd === 'prev') voltar();
        }
        contar();
    }

    socket.on('apresentacao_cmd', function (d) {
        if (pronto) executar(d);
        else fila.push(d);
    });

    function aoCarregar() {
        // O tocador nasce no fim do carregamento do SVG; espera ele existir
        let tentativas = 0;
        (function esperar() {
            let ok = false;
            try { ok = !!(w().aSlideShow && w().theMetaDoc && w().nCurSlide !== undefined); } catch (e) { /* ainda não */ }
            if (!ok) {
                if (++tentativas > 200) { aviso.textContent = _t('Não deu pra abrir a apresentação'); return; }
                setTimeout(esperar, 50);
                return;
            }
            try { w().alert = function (m) { console.warn('Apresentação:', m); }; } catch (e) { /* segue */ }
            fetch('/api/apresentacao').then(r => r.json()).catch(() => ({})).then(function (e) {
                // Mesma apresentação no ar: entra onde as outras telas estão
                if (e && e.svg === svg) irPara(e.slide, e.step);
                else irPara(parseInt(params.get('slide') || '0', 10) || 0, 0);
                pronto = true;
                frame.style.visibility = 'visible';
                aviso.hidden = true;
                fila.splice(0).forEach(executar);
                contar();
            });
        })();
    }

    frame.addEventListener('load', aoCarregar);
    frame.src = svg;

    // Reconectou (Wi-Fi caiu, servidor reiniciou): volta pra onde o
    // servidor diz que a apresentação está
    socket.on('connect', function () {
        if (!pronto) return;
        fetch('/api/apresentacao').then(r => r.json()).then(function (e) {
            if (e && e.svg === svg && e.slides !== null) { irPara(e.slide, e.step); contar(); }
            else contar();
        }).catch(function () {});
    });
})();
