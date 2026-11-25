// Página "Slides: avisos e listas" (/slides, blueprints/slides.py): os
// conjuntos (Avisos, Diretoria...), o editor de slides de texto e de lista,
// a prévia (o mesmo desenho do telão: tema_render.js + slides_render.js) e
// os botões Exibir / Anterior / Próximo / Parar.
(function () {
    const CONFIG = JSON.parse(document.getElementById('sl-config').textContent);
    const $ = id => document.getElementById(id);
    const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    const toast = (msg, tipo) => { if (window.ucToast) window.ucToast(msg, tipo); };
    const json = (url, metodo, corpo) => fetch(url, {
        method: metodo || 'GET', headers: corpo ? { 'Content-Type': 'application/json' } : {},
        body: corpo ? JSON.stringify(corpo) : undefined,
    }).then(r => r.json().then(d => ({ ok: r.ok, d })));

    let conjuntos = [];
    let temas = [];          // completos (/api/temas), pra prévia
    let temaPadrao = null;
    let textoPadrao = null;
    let atual = null;        // conjunto em edição {id?, nome, tema_id, segundos, automatica, embaralhar, slides}
    let alterado = false;
    let previaPos = 0;       // tela mostrada na prévia
    let noAr = null;         // resumo do que está no telão (blueprints/slides.py resumo_no_ar)
    let previaAnterior = null;   // tela anterior da prévia (revelar aos poucos anima só a linha nova)

    // ── Telas (igual a slides_store.telas: a lista longa vira várias) ──
    function telas(c) {
        const saida = [];
        (c.slides || []).forEach((s, i) => {
            if (s.tipo !== 'lista') { saida.push({ tela: s, slide: i }); return; }
            const por = s.por_tela || CONFIG.porTela;
            const linhas = s.linhas.filter(l => (l[0] || '').trim() || (l[1] || '').trim());
            const grupos = [];
            for (let k = 0; k < linhas.length; k += por) grupos.push(linhas.slice(k, k + por));
            if (!grupos.length) grupos.push([]);
            grupos.forEach((g, n) => {
                const tela = { tipo: 'lista', titulo: s.titulo, linhas: g,
                    parte: grupos.length > 1 ? `${n + 1}/${grupos.length}` : '',
                    completar: grupos.length > 1 && g.length < por ? por - g.length : 0 };
                if (!s.aos_poucos) { saida.push({ slide: i, tela }); return; }
                // Uma linha por clique: de só o título até todas (slides_store.telas)
                for (let k = 0; k <= g.length; k++) saida.push({ slide: i, tela: Object.assign({}, tela, { mostrar: k, grupo: `${i}.${n + 1}` }) });
            });
        });
        return saida;
    }

    // ── Prévia ──────────────────────────────────────────────────────
    function temaEscolhido() {
        const id = Number($('sl-tema').value) || temaPadrao;
        return temas.find(t => t.id === id) || { fundo: { type: 'color', color: '#000000' }, texto: textoPadrao, transicao: { tipo: 'nenhuma', duracao: 500 } };
    }
    function desenharPrevia() {
        if (!atual) return;
        const t = temaEscolhido();
        const f = t.fundo || {};
        const img = $('sl-previa-img'), video = $('sl-previa-video');
        $('sl-previa-fundo').style.background = UcTema.fundoCss(f);
        UcFundoAnimado.montar($('sl-previa-fundo'), f);
        img.hidden = !(f.type === 'image' && f.url);
        video.hidden = !(f.type === 'video' && f.url);
        if (!img.hidden && img.getAttribute('src') !== f.url) img.src = f.url;
        if (!video.hidden) { if (video.getAttribute('src') !== f.url) video.src = f.url; video.play().catch(() => {}); }
        else { video.pause(); video.removeAttribute('src'); }
        $('sl-previa-escurecer').style.opacity = (f.type === 'image' || f.type === 'video') ? (Number(f.escurecer) || 0) / 100 : 0;

        const lista = telas(atual);
        previaPos = Math.max(0, Math.min(previaPos, lista.length - 1));
        const el = $('sl-previa-texto'), letra = $('sl-previa-letra');
        const tela = lista.length ? lista[previaPos].tela : null;
        el.innerHTML = tela ? UcSlides.html(tela, previaAnterior) : esc(_t('Adicione um slide'));
        previaAnterior = tela;
        if (t.texto) {
            UcTema.aplicarTexto(letra, el, t.texto);
            UcTema.ajustar(letra, el, t.texto.tamanho_max * $('sl-previa').clientWidth / 100, 'px', 0.5);
        }
        $('sl-previa-pos').textContent = lista.length ? _t('Tela {n} de {total}', { n: previaPos + 1, total: lista.length }) : '';
        document.querySelectorAll('.sl-slide').forEach((card, i) => card.classList.toggle('foco', !!lista[previaPos] && lista[previaPos].slide === i));
    }
    function focarSlide(i) {
        const k = telas(atual).findIndex(x => x.slide === i);
        if (k >= 0 && k !== previaPos) { previaPos = k; desenharPrevia(); }
    }
    $('sl-previa-ant').addEventListener('click', () => { previaPos--; desenharPrevia(); });
    $('sl-previa-prox').addEventListener('click', () => { previaPos++; desenharPrevia(); });

    // ── Editor de slides ────────────────────────────────────────────
    function mudou() { alterado = true; $('sl-status').textContent = _t('Alterações não salvas'); desenharPrevia(); atualizarContagens(); }

    function botoesOrdem() {
        return `<button type="button" class="uc-btn uc-btn-ghost uc-btn-sm" data-acao="subir" aria-label="${esc(_t('Subir'))}"><i class="fas fa-arrow-up"></i></button>
            <button type="button" class="uc-btn uc-btn-ghost uc-btn-sm" data-acao="descer" aria-label="${esc(_t('Descer'))}"><i class="fas fa-arrow-down"></i></button>
            <button type="button" class="uc-btn uc-btn-danger uc-btn-sm" data-acao="tirar" aria-label="${esc(_t('Tirar o slide'))}"><i class="fas fa-trash"></i></button>`;
    }

    function linhaLista(slide, i, k) {
        const [rotulo, valor] = slide.linhas[k];
        return `<div class="sl-linha-ed" data-linha="${k}">
            <input class="uc-input" data-parte="0" maxlength="120" value="${esc(rotulo)}" placeholder="${esc(_t('Cargo ou função'))}" aria-label="${esc(_t('Cargo ou função'))}">
            <input class="uc-input" data-parte="1" maxlength="120" value="${esc(valor)}" placeholder="${esc(_t('Nome'))}" aria-label="${esc(_t('Nome'))}">
            <button type="button" class="uc-btn uc-btn-ghost uc-btn-sm" data-acao="tirar-linha" aria-label="${esc(_t('Tirar a linha'))}"><i class="fas fa-xmark"></i></button>
        </div>`;
    }

    function cartao(slide, i) {
        const div = document.createElement('div');
        div.className = 'sl-slide';
        const lista = slide.tipo === 'lista';
        div.innerHTML = `<div class="sl-slide-topo">
                <i class="fas ${lista ? 'fa-list' : 'fa-align-center'}"></i>
                <span class="sl-tipo">${esc(lista ? _t('Lista') : _t('Texto'))}</span>
                <span class="sl-telas"></span>
                ${botoesOrdem()}
            </div>` + (lista ? `<div class="sl-campos">
                <div class="sl-titulo-linha">
                    <label class="tm-controle">${esc(_t('Título'))}
                        <input class="uc-input" data-campo="titulo" maxlength="120" value="${esc(slide.titulo)}" placeholder="${esc(_t('Ex.: Diretoria 2026'))}">
                    </label>
                    <label class="tm-controle">${esc(_t('Linhas por tela'))}
                        <input class="uc-input sl-por-tela" data-campo="por_tela" type="number" min="2" max="15" value="${slide.por_tela}">
                    </label>
                </div>
                <label class="tm-check" title="${esc(_t('Começa só com o título; cada Próximo mostra mais uma linha. Bom para valores e para apresentar a diretoria.'))}">
                    <input type="checkbox" data-campo="aos_poucos"${slide.aos_poucos ? ' checked' : ''}> ${esc(_t('Mostrar uma linha por clique'))}
                </label>
                <div class="sl-linhas-ed">${slide.linhas.map((_, k) => linhaLista(slide, i, k)).join('')}</div>
                <div class="uc-btn-row">
                    <button type="button" class="uc-btn uc-btn-secondary uc-btn-sm" data-acao="mais-linha"><i class="fas fa-plus"></i> ${esc(_t('Linha'))}</button>
                    <button type="button" class="uc-btn uc-btn-ghost uc-btn-sm" data-acao="colar"><i class="fas fa-paste"></i> ${esc(_t('Colar várias linhas'))}</button>
                </div>
                <div class="sl-colar" hidden>
                    <textarea class="uc-input" rows="4" placeholder="${esc(_t('Uma por linha. Ex.: Presidente: Fulano de Tal'))}"></textarea>
                    <div><button type="button" class="uc-btn uc-btn-primary uc-btn-sm" data-acao="colar-ok">${esc(_t('Adicionar as linhas'))}</button></div>
                </div>
            </div>` : `<textarea class="uc-input" data-campo="texto" rows="3" maxlength="500" placeholder="${esc(_t('Texto do slide'))}">${esc(slide.texto)}</textarea>
            <p class="tm-dica">${esc(_t('Formatação: **negrito**, *itálico*, {amarelo}cor{/}, {grande}tamanho{/}.'))}</p>`);

        div.addEventListener('focusin', () => focarSlide(posicao(div)));
        div.addEventListener('input', (e) => {
            const s = atual.slides[posicao(div)];
            const campo = e.target.dataset.campo;
            if (campo === 'por_tela') s.por_tela = Math.max(2, Math.min(15, Number(e.target.value) || CONFIG.porTela));
            else if (campo === 'aos_poucos') {
                s.aos_poucos = e.target.checked;
                // Passando sozinho, um clique por linha raramente é o que se quer: avisa
                if (s.aos_poucos && atual.automatica !== false) toast(_t('Uma linha por clique funciona melhor com "Na mão".'));
            }
            else if (campo) s[campo] = e.target.value;
            else if (e.target.dataset.parte != null) {
                const k = Number(e.target.closest('[data-linha]').dataset.linha);
                s.linhas[k][Number(e.target.dataset.parte)] = e.target.value;
            } else return;
            mudou();
        });
        div.addEventListener('click', (e) => {
            const botao = e.target.closest('[data-acao]');
            if (!botao) return;
            const i = posicao(div), s = atual.slides[i];
            const acao = botao.dataset.acao;
            if (acao === 'subir' && i > 0) { [atual.slides[i - 1], atual.slides[i]] = [atual.slides[i], atual.slides[i - 1]]; montarSlides(); mudou(); }
            else if (acao === 'descer' && i < atual.slides.length - 1) { [atual.slides[i + 1], atual.slides[i]] = [atual.slides[i], atual.slides[i + 1]]; montarSlides(); mudou(); }
            else if (acao === 'tirar') { atual.slides.splice(i, 1); montarSlides(); mudou(); }
            else if (acao === 'mais-linha') {
                s.linhas.push(['', '']);
                montarSlides(); mudou();
                const linhas = $('sl-slides').children[i].querySelectorAll('.sl-linha-ed input[data-parte="0"]');
                if (linhas.length) linhas[linhas.length - 1].focus();
            } else if (acao === 'tirar-linha') {
                s.linhas.splice(Number(botao.closest('[data-linha]').dataset.linha), 1);
                montarSlides(); mudou();
            } else if (acao === 'colar') {
                const caixa = div.querySelector('.sl-colar');
                caixa.hidden = !caixa.hidden;
                if (!caixa.hidden) caixa.querySelector('textarea').focus();
            } else if (acao === 'colar-ok') {
                const novas = lerLinhas(div.querySelector('.sl-colar textarea').value);
                if (!novas.length) return;
                s.linhas = s.linhas.filter(l => l[0].trim() || l[1].trim()).concat(novas);
                montarSlides(); mudou();
            }
        });
        return div;
    }
    const posicao = el => [...el.parentNode.children].indexOf(el);

    // "Presidente: Fulano", "Presidente - Fulano", "Presidente<TAB>Fulano"
    // (copiado do WhatsApp ou de uma planilha); sem separador: só o nome
    function lerLinhas(texto) {
        return String(texto || '').split('\n').map(l => l.trim()).filter(Boolean).map(l => {
            const m = l.match(/^(.*?)\s*(?:\t|:|\s[-–—]\s)\s*(.+)$/);
            return m ? [m[1].trim().slice(0, 120), m[2].trim().slice(0, 120)] : ['', l.slice(0, 120)];
        });
    }

    function montarSlides() {
        const caixa = $('sl-slides');
        caixa.innerHTML = '';
        atual.slides.forEach((s, i) => caixa.appendChild(cartao(s, i)));
        if (!atual.slides.length) caixa.innerHTML = `<p class="tm-dica">${esc(_t('Nenhum slide ainda. Adicione um de texto ou de lista.'))}</p>`;
        atualizarContagens();
    }
    function atualizarContagens() {
        const lista = telas(atual);
        document.querySelectorAll('.sl-slide').forEach((card, i) => {
            const n = lista.filter(x => x.slide === i).length;
            const s = atual.slides[i];
            card.querySelector('.sl-telas').textContent = s.tipo !== 'lista' || n < 2 ? ''
                : s.aos_poucos ? _t('{n} cliques', { n }) : _t('vira {n} telas', { n });
        });
    }

    document.querySelectorAll('[data-novo]').forEach(b => b.addEventListener('click', () => {
        atual.slides.push(b.dataset.novo === 'lista'
            ? { tipo: 'lista', titulo: '', linhas: [['', '']], por_tela: CONFIG.porTela }
            : { tipo: 'texto', texto: '' });
        montarSlides();
        mudou();
        const ultimo = $('sl-slides').lastElementChild;
        const campo = ultimo && ultimo.querySelector('input, textarea');
        if (campo) campo.focus();
        focarSlide(atual.slides.length - 1);
    }));

    // ── Configuração do conjunto ────────────────────────────────────
    function marcarPassagem() {
        const mao = atual.automatica === false;
        document.querySelectorAll('#sl-passagem button').forEach(b => b.classList.toggle('ativo', (b.dataset.valor === 'mao') === mao));
        $('sl-sozinho').hidden = mao;
        $('sl-mao-dica').hidden = !mao;
    }
    document.querySelectorAll('#sl-passagem button').forEach(b => b.addEventListener('click', () => {
        atual.automatica = b.dataset.valor !== 'mao';
        marcarPassagem(); mudou();
    }));
    $('sl-tema').addEventListener('change', () => { atual.tema_id = Number($('sl-tema').value) || null; mudou(); });
    $('sl-segundos').addEventListener('input', () => { atual.segundos = Number($('sl-segundos').value); $('sl-segundos-valor').textContent = atual.segundos + ' s'; mudou(); });
    $('sl-embaralhar').addEventListener('change', () => { atual.embaralhar = $('sl-embaralhar').checked; mudou(); });
    $('sl-nome').addEventListener('input', () => { atual.nome = $('sl-nome').value; alterado = true; $('sl-status').textContent = _t('Alterações não salvas'); });

    // ── Lista de conjuntos ──────────────────────────────────────────
    function desenharLista() {
        $('sl-lista').innerHTML = conjuntos.map(c => {
            const n = telas(c).length;
            const passando = noAr && noAr.id === c.id;
            return `<button type="button" class="tm-item${atual && atual.id === c.id ? ' ativo' : ''}" data-id="${c.id}">
                <span class="tm-item-nome">${esc(c.nome)}</span>
                ${passando ? `<span class="uc-pill uc-pill-live">${esc(_t('No telão'))}</span>` : ''}
                <span class="tm-status">${esc(_t('{n} telas', { n }))} · ${esc(c.automatica ? _t('sozinhos') : _t('na mão'))}</span>
            </button>`;
        }).join('');
        $('sl-lista').querySelectorAll('[data-id]').forEach(b => b.addEventListener('click', () => abrir(conjuntos.find(c => c.id === Number(b.dataset.id)))));
    }

    function abrir(conjunto) {
        if (alterado && !confirm(_t('Descartar as alterações não salvas?'))) return;
        atual = JSON.parse(JSON.stringify(conjunto));
        atual.slides.forEach(s => { if (s.tipo === 'lista' && !s.linhas.length) s.linhas.push(['', '']); });
        alterado = false;
        previaPos = 0;
        $('sl-editor').hidden = false;
        $('sl-nome').value = atual.nome || '';
        $('sl-tema').value = atual.tema_id || '';
        $('sl-segundos').value = atual.segundos;
        $('sl-segundos-valor').textContent = atual.segundos + ' s';
        $('sl-embaralhar').checked = !!atual.embaralhar;
        $('sl-apagar').hidden = !atual.id;
        $('sl-duplicar').hidden = !atual.id;
        $('sl-status').textContent = '';
        marcarPassagem();
        montarSlides();
        desenharLista();
        desenharPrevia();
    }

    function novo(base) {
        abrir(Object.assign({ nome: '', tema_id: null, segundos: 10, automatica: false, embaralhar: false,
            slides: [{ tipo: 'lista', titulo: '', linhas: [['', '']], por_tela: CONFIG.porTela }] }, base || {}, { id: undefined }));
        alterado = true;
        $('sl-nome').focus();
    }
    $('sl-novo').addEventListener('click', () => novo());
    $('sl-duplicar').addEventListener('click', () => novo(Object.assign({}, atual, { nome: _t('{nome} (cópia)', { nome: atual.nome }) })));

    function carregar(abrirId) {
        return Promise.all([json('/api/slides'), json('/api/temas')]).then(([s, t]) => {
            conjuntos = s.d.conjuntos;
            noAr = s.d.no_ar;
            temas = t.d.temas;
            temaPadrao = t.d.padrao;
            textoPadrao = t.d.texto_padrao;
            const valor = $('sl-tema').value;
            $('sl-tema').innerHTML = `<option value="">${esc(_t('Tema padrão'))}</option>` + temas.map(x => `<option value="${x.id}">${esc(x.nome)}</option>`).join('');
            $('sl-tema').value = valor;
            const alvo = conjuntos.find(c => c.id === abrirId) || (atual ? null : conjuntos[0]);
            if (alvo) abrir(alvo); else desenharLista();
            mostrarNoAr();
        });
    }

    function corpo() {
        return { nome: atual.nome, tema_id: atual.tema_id, segundos: atual.segundos, automatica: atual.automatica !== false,
            embaralhar: atual.embaralhar, slides: atual.slides };
    }
    function salvar() {
        if (!(atual.nome || '').trim()) { toast(_t('Dê um nome ao conjunto de slides.'), 'error'); $('sl-nome').focus(); return Promise.resolve(null); }
        return json(atual.id ? `/api/slides/${atual.id}` : '/api/slides', atual.id ? 'PUT' : 'POST', corpo()).then(({ ok, d }) => {
            if (!ok) { toast(d.erro || _t('Não deu para salvar.'), 'error'); return null; }
            alterado = false;
            return carregar(d.conjunto.id).then(() => { $('sl-status').textContent = _t('Salvo.'); return d.conjunto; });
        });
    }
    $('sl-salvar').addEventListener('click', salvar);
    $('sl-apagar').addEventListener('click', () => {
        if (!atual.id || !confirm(_t('Apagar "{nome}"? Não dá para desfazer.', { nome: atual.nome }))) return;
        json(`/api/slides/${atual.id}`, 'DELETE').then(() => { alterado = false; atual = null; $('sl-editor').hidden = true; carregar(); });
    });

    // ── No telão ────────────────────────────────────────────────────
    $('sl-exibir').addEventListener('click', () => {
        salvar().then(c => {
            if (!c) return;
            // Na mão: começa na tela que está na prévia
            json(`/api/slides/${c.id}/exibir`, 'POST', { pos: c.automatica ? 0 : previaPos }).then(({ ok, d }) => {
                $('sl-status').textContent = ok ? _t('No telão.') : (d.erro || _t('Não deu para exibir.'));
                if (!ok) toast(d.erro || _t('Não deu para exibir.'), 'error');
            });
        });
    });
    const passo = direcao => json('/api/slides/passo', 'POST', { direcao });
    $('sl-anterior').addEventListener('click', () => passo(-1));
    $('sl-proximo').addEventListener('click', () => passo(1));
    $('sl-parar').addEventListener('click', () => json('/api/slides/parar', 'POST'));

    function mostrarNoAr() {
        const barra = $('sl-no-ar');
        barra.hidden = !noAr;
        if (!noAr) { desenharLista(); return; }
        $('sl-no-ar-nome').textContent = noAr.nome;
        $('sl-no-ar-pos').textContent = noAr.automatica ? _t('passando sozinhos') : _t('tela {n} de {total}', { n: noAr.pos + 1, total: noAr.total });
        $('sl-anterior').hidden = $('sl-proximo').hidden = noAr.automatica;
        $('sl-anterior').disabled = noAr.pos <= 0;
        $('sl-proximo').disabled = noAr.pos >= noAr.total - 1;
        desenharLista();
    }
    // Status do telão (static/js/telao_bar.js): vale também pro que outro aparelho fizer
    window.addEventListener('uc-telao-status', (e) => {
        const s = e.detail && e.detail.slides;
        if (JSON.stringify(s || null) === JSON.stringify(noAr)) return;
        noAr = s || null;
        mostrarNoAr();
    });

    // Setas/PageUp/PageDown (pedal) passam os slides que estão na mão no telão
    document.addEventListener('keydown', (e) => {
        if (!noAr || noAr.automatica || e.target.closest('input, textarea, select, [contenteditable="true"]')) return;
        if (['ArrowRight', 'ArrowDown', 'PageDown'].includes(e.key)) { e.preventDefault(); passo(1); }
        else if (['ArrowLeft', 'ArrowUp', 'PageUp'].includes(e.key)) { e.preventDefault(); passo(-1); }
    });

    window.addEventListener('resize', desenharPrevia);
    if (document.fonts) document.fonts.addEventListener('loadingdone', () => desenharPrevia());
    window.addEventListener('beforeunload', (e) => { if (alterado) { e.preventDefault(); e.returnValue = ''; } });

    carregar();
})();
