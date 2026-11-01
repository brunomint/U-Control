// Página "Avisos em slides" (/avisos, blueprints/avisos.py): a lista de
// avisos, o tema e o tempo de cada um, com prévia (static/js/tema_render.js,
// o mesmo código do telão) e os botões Exibir/Parar.
(function () {
    const $ = id => document.getElementById(id);
    const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    let temas = [];          // temas completos (/api/temas), pra prévia
    let padrao = null;
    let textoPadrao = null;
    let alterado = false;
    let foco = 0;            // aviso mostrado na prévia
    let giro = null;

    function avisos() { return [...document.querySelectorAll('#av-lista textarea')].map(t => t.value); }

    function linhaAviso(texto) {
        const div = document.createElement('div');
        div.className = 'av-item';
        div.innerHTML = `<textarea class="uc-input" rows="2" maxlength="500">${esc(texto)}</textarea>
            <div class="av-item-botoes">
                <button type="button" class="uc-btn uc-btn-ghost uc-btn-sm" data-acao="subir" aria-label="${esc(_t('Subir'))}"><i class="fas fa-arrow-up"></i></button>
                <button type="button" class="uc-btn uc-btn-ghost uc-btn-sm" data-acao="descer" aria-label="${esc(_t('Descer'))}"><i class="fas fa-arrow-down"></i></button>
                <button type="button" class="uc-btn uc-btn-danger uc-btn-sm" data-acao="tirar" aria-label="${esc(_t('Tirar'))}"><i class="fas fa-trash"></i></button>
            </div>`;
        const area = div.querySelector('textarea');
        area.addEventListener('input', () => { mudou(); foco = posicao(div); desenharPrevia(); });
        area.addEventListener('focus', () => { foco = posicao(div); desenharPrevia(); });
        div.querySelector('[data-acao=subir]').addEventListener('click', () => { if (div.previousElementSibling) div.parentNode.insertBefore(div, div.previousElementSibling); mudou(); });
        div.querySelector('[data-acao=descer]').addEventListener('click', () => { if (div.nextElementSibling) div.parentNode.insertBefore(div.nextElementSibling, div); mudou(); });
        div.querySelector('[data-acao=tirar]').addEventListener('click', () => { div.remove(); mudou(); desenharPrevia(); });
        return div;
    }
    const posicao = el => [...el.parentNode.children].indexOf(el);

    function mudou() { alterado = true; $('av-status').textContent = _t('Alterações não salvas'); }

    function temaEscolhido() {
        const id = Number($('av-tema').value) || padrao;
        return temas.find(t => t.id === id) || { fundo: { type: 'color', color: '#000000' }, texto: textoPadrao, transicao: { tipo: 'nenhuma', duracao: 500 } };
    }

    function desenharPrevia() {
        const t = temaEscolhido();
        const f = t.fundo || {};
        const img = $('av-previa-img'), video = $('av-previa-video');
        $('av-previa-fundo').style.background = UcTema.fundoCss(f);
        img.hidden = !(f.type === 'image' && f.url);
        video.hidden = !(f.type === 'video' && f.url);
        if (!img.hidden && img.getAttribute('src') !== f.url) img.src = f.url;
        if (!video.hidden) { if (video.getAttribute('src') !== f.url) video.src = f.url; video.play().catch(() => {}); }
        else { video.pause(); video.removeAttribute('src'); }
        $('av-previa-escurecer').style.opacity = (f.type === 'image' || f.type === 'video') ? (Number(f.escurecer) || 0) / 100 : 0;
        const lista = avisos().filter(a => a.trim());
        const texto = lista.length ? (avisos()[foco] || lista[0]) : _t('Escreva um aviso ao lado');
        const letra = $('av-previa-letra'), el = $('av-previa-texto');
        el.innerHTML = esc(texto).replace(/\n/g, '<br>');
        if (t.texto) {
            UcTema.aplicarTexto(letra, el, t.texto);
            UcTema.ajustar(letra, el, t.texto.tamanho_max * $('av-previa').clientWidth / 100, 'px', 0.5);
        }
    }

    function carregar() {
        Promise.all([fetch('/api/avisos').then(r => r.json()), fetch('/api/temas').then(r => r.json())]).then(([a, t]) => {
            temas = t.temas;
            padrao = t.padrao;
            textoPadrao = t.texto_padrao;
            $('av-tema').innerHTML = `<option value="">${esc(_t('Tema padrão'))}</option>` + temas.map(x => `<option value="${x.id}">${esc(x.nome)}</option>`).join('');
            $('av-tema').value = a.tema_id || '';
            $('av-segundos').value = a.segundos;
            $('av-segundos-valor').textContent = a.segundos + ' s';
            $('av-embaralhar').checked = a.embaralhar;
            $('av-lista').innerHTML = '';
            (a.itens.length ? a.itens : ['']).forEach(texto => $('av-lista').appendChild(linhaAviso(texto)));
            $('av-no-ar').hidden = !a.no_ar;
            alterado = false;
            desenharPrevia();
        });
    }

    function salvar() {
        return fetch('/api/avisos', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ itens: avisos(), tema_id: Number($('av-tema').value) || null,
                segundos: Number($('av-segundos').value), embaralhar: $('av-embaralhar').checked }),
        }).then(r => r.json()).then(d => {
            alterado = false;
            $('av-status').textContent = _t('Salvo.');
            return d;
        });
    }

    $('av-adicionar').addEventListener('click', () => {
        const nova = linhaAviso('');
        $('av-lista').appendChild(nova);
        nova.querySelector('textarea').focus();
        mudou();
    });
    $('av-tema').addEventListener('change', () => { mudou(); desenharPrevia(); });
    $('av-segundos').addEventListener('input', () => { $('av-segundos-valor').textContent = $('av-segundos').value + ' s'; mudou(); });
    $('av-embaralhar').addEventListener('change', mudou);
    $('av-salvar').addEventListener('click', salvar);
    window.addEventListener('resize', desenharPrevia);
    window.addEventListener('beforeunload', (e) => { if (alterado) { e.preventDefault(); e.returnValue = ''; } });

    $('av-exibir').addEventListener('click', () => {
        salvar().then(() => fetch('/api/avisos/exibir', { method: 'POST' })).then(r => r.json().then(d => ({ ok: r.ok, d }))).then(({ ok, d }) => {
            $('av-status').textContent = ok ? _t('Os avisos estão passando no telão.') : (d.erro || _t('Não deu para exibir.'));
            $('av-no-ar').hidden = !ok;
        });
    });
    $('av-parar').addEventListener('click', () => {
        fetch('/api/avisos/parar', { method: 'POST' }).then(() => {
            $('av-status').textContent = _t('Avisos parados.');
            $('av-no-ar').hidden = true;
        });
    });

    // A prévia passa pelos avisos no tempo escolhido, com a transição do tema
    function girar() {
        clearTimeout(giro);
        giro = setTimeout(() => {
            const total = avisos().length;
            if (total > 1 && !document.activeElement.matches('#av-lista textarea')) {
                UcTema.trocarComTransicao($('av-previa-texto'), temaEscolhido().transicao, () => { foco = (foco + 1) % total; desenharPrevia(); });
            }
            girar();
        }, (Number($('av-segundos').value) || 10) * 1000);
    }

    carregar();
    girar();
})();
