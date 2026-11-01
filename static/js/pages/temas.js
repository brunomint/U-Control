// Página "Temas e fundos" (/temas, blueprints/temas.py): lista de temas,
// editor com prévia ao vivo (static/js/tema_render.js, o mesmo código do
// telão) e os vídeos de fundo (blueprints/fundos.py).
(function () {
    const CONFIG = JSON.parse(document.getElementById('tm-config').textContent);
    const $ = id => document.getElementById(id);
    const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    const toast = (msg, tipo) => { if (window.ucToast) window.ucToast(msg, tipo); };

    let temas = [];
    let padrao = null;
    let biblia = null;
    let atual = null;        // tema em edição: {id?, nome, fundo, texto}
    let alterado = false;
    let segundoSlide = false;   // "Ver a transição" alterna a prévia entre dois slides

    // ── Prévia ──────────────────────────────────────────────────────
    function desenharPrevia() {
        if (!atual) return;
        const f = atual.fundo || { type: 'color', color: '#000000' };
        const img = $('tm-previa-img'), video = $('tm-previa-video');
        $('tm-previa-fundo').style.background = UcTema.fundoCss(f);
        img.hidden = !(f.type === 'image' && f.url);
        video.hidden = !(f.type === 'video' && f.url);
        if (!img.hidden && img.getAttribute('src') !== f.url) img.src = f.url;
        if (!video.hidden) {
            if (video.getAttribute('src') !== f.url) video.src = f.url;
            video.play().catch(() => {});
        } else { video.pause(); video.removeAttribute('src'); }
        const midia = f.type === 'image' || f.type === 'video';
        $('tm-previa-escurecer').style.opacity = midia ? (Number(f.escurecer) || 0) / 100 : 0;
        $('tm-escurecer-linha').hidden = !midia;

        const letra = $('tm-previa-letra'), texto = $('tm-previa-texto');
        const exemplo = segundoSlide ? 'Santo, santo, santo\nÉ o Senhor' : $('tm-exemplo').value;
        texto.innerHTML = esc(exemplo).replace(/\n/g, '<br>');
        UcTema.aplicarTexto(letra, texto, atual.texto);
        // vw do telão -> px da prévia (a prévia tem a proporção de uma tela 16:9)
        const largura = $('tm-previa').clientWidth;
        UcTema.ajustar(letra, texto, atual.texto.tamanho_max * largura / 100, 'px', 0.5);
    }

    // ── Formulário <-> tema ─────────────────────────────────────────
    const DESLIZANTES = {
        'tm-tamanho': ['tamanho_max', v => v + ''],
        'tm-entrelinhas': ['entrelinhas', v => Number(v).toFixed(2)],
        'tm-margem': ['margem', v => v + '%'],
        'tm-contorno': ['contorno', v => v + ''],
        'tm-caixa-opacidade': ['caixa_opacidade', v => v + '%'],
        'tm-caixa-arredondada': ['caixa_arredondada', v => v + ''],
    };
    const CHECKS = { 'tm-negrito': 'negrito', 'tm-italico': 'italico', 'tm-maiusculas': 'maiusculas', 'tm-sombra': 'sombra', 'tm-caixa': 'caixa' };
    const CORES = { 'tm-cor': 'cor', 'tm-contorno-cor': 'contorno_cor', 'tm-sombra-cor': 'sombra_cor', 'tm-caixa-cor': 'caixa_cor' };

    function preencher() {
        const t = atual.texto;
        $('tm-nome').value = atual.nome || '';
        $('tm-fonte').value = t.fonte;
        for (const [id, [chave, fmt]] of Object.entries(DESLIZANTES)) { $(id).value = t[chave]; $(id + '-valor').textContent = fmt(t[chave]); }
        for (const [id, chave] of Object.entries(CHECKS)) $(id).checked = !!t[chave];
        for (const [id, chave] of Object.entries(CORES)) $(id).value = t[chave];
        const tr = atual.transicao || CONFIG.transicaoPadrao;
        atual.transicao = Object.assign({}, tr);
        $('tm-transicao').value = tr.tipo;
        $('tm-duracao').value = tr.duracao;
        $('tm-duracao-valor').textContent = (tr.duracao / 1000).toFixed(1) + ' s';
        segundoSlide = false;
        marcarSegmento('tm-alinhamento', t.alinhamento);
        marcarSegmento('tm-posicao', t.posicao);
        const f = atual.fundo || {};
        if (f.type === 'color') $('tm-fundo-cor').value = f.color;
        const e = Number(f.escurecer) || 0;
        $('tm-escurecer').value = e;
        $('tm-escurecer-valor').textContent = e + '%';
        mostrarPainelFundo(f.type || 'color');
        $('tm-selo-padrao').hidden = !(atual.id && atual.id === padrao);
        $('tm-apagar').hidden = !atual.id;
        $('tm-duplicar').hidden = !atual.id;
        $('tm-padrao').hidden = !atual.id || atual.id === padrao;
        desenharPrevia();
    }

    function mudou() { alterado = true; $('tm-status').textContent = _t('Alterações não salvas'); desenharPrevia(); }

    function marcarSegmento(id, valor) {
        $(id).querySelectorAll('button').forEach(b => b.classList.toggle('ativo', b.dataset.valor === valor));
    }
    [['tm-alinhamento', 'alinhamento'], ['tm-posicao', 'posicao']].forEach(([id, chave]) => {
        $(id).querySelectorAll('button').forEach(b => b.addEventListener('click', () => {
            atual.texto[chave] = b.dataset.valor;
            marcarSegmento(id, b.dataset.valor);
            mudou();
        }));
    });
    for (const [id, [chave, fmt]] of Object.entries(DESLIZANTES)) {
        $(id).addEventListener('input', () => { atual.texto[chave] = Number($(id).value); $(id + '-valor').textContent = fmt($(id).value); mudou(); });
    }
    for (const [id, chave] of Object.entries(CHECKS)) $(id).addEventListener('change', () => { atual.texto[chave] = $(id).checked; mudou(); });
    for (const [id, chave] of Object.entries(CORES)) $(id).addEventListener('input', () => { atual.texto[chave] = $(id).value; mudou(); });
    $('tm-fonte').addEventListener('change', () => { atual.texto.fonte = $('tm-fonte').value; mudou(); });
    $('tm-transicao').addEventListener('change', () => { atual.transicao.tipo = $('tm-transicao').value; mudou(); verTransicao(); });
    $('tm-duracao').addEventListener('input', () => {
        atual.transicao.duracao = Number($('tm-duracao').value);
        $('tm-duracao-valor').textContent = (atual.transicao.duracao / 1000).toFixed(1) + ' s';
        mudou();
    });
    function verTransicao() {
        UcTema.trocarComTransicao($('tm-previa-texto'), atual.transicao, () => { segundoSlide = !segundoSlide; desenharPrevia(); });
    }
    $('tm-ver-transicao').addEventListener('click', verTransicao);
    $('tm-nome').addEventListener('input', () => { atual.nome = $('tm-nome').value; alterado = true; $('tm-status').textContent = _t('Alterações não salvas'); });
    $('tm-exemplo').addEventListener('input', desenharPrevia);
    window.addEventListener('resize', desenharPrevia);

    // ── Fundo ───────────────────────────────────────────────────────
    function mostrarPainelFundo(tipo) {
        document.querySelectorAll('.tm-abas button').forEach(b => b.classList.toggle('ativo', b.dataset.fundo === tipo));
        document.querySelectorAll('.tm-fundo-painel').forEach(p => { p.hidden = p.dataset.painel !== tipo; });
        if (tipo === 'image') carregarPastas();
        if (tipo === 'video') carregarVideosEscolha();
    }
    function trocarFundo(fundo) {
        const e = Number($('tm-escurecer').value) || 0;
        if ((fundo.type === 'image' || fundo.type === 'video') && e) fundo.escurecer = e;
        atual.fundo = fundo;
        marcarMidiaAtiva();
        mudou();
    }
    document.querySelectorAll('.tm-abas button').forEach(b => b.addEventListener('click', () => mostrarPainelFundo(b.dataset.fundo)));
    $('tm-fundo-cor').addEventListener('input', () => trocarFundo({ type: 'color', color: $('tm-fundo-cor').value }));
    document.querySelectorAll('.tm-swatch').forEach(b => b.addEventListener('click', () => trocarFundo({ type: 'gradient', css: b.dataset.css })));
    $('tm-escurecer').addEventListener('input', () => {
        $('tm-escurecer-valor').textContent = $('tm-escurecer').value + '%';
        if (atual.fundo && (atual.fundo.type === 'image' || atual.fundo.type === 'video')) {
            atual.fundo = Object.assign({}, atual.fundo, { escurecer: Number($('tm-escurecer').value) });
            mudou();
        }
    });

    function marcarMidiaAtiva() {
        const url = atual && atual.fundo ? atual.fundo.url : null;
        document.querySelectorAll('.tm-midias [data-url]').forEach(b => b.classList.toggle('ativo', b.dataset.url === url));
    }

    let pastaAtiva = 'Geral';
    function carregarPastas() {
        fetch('/api/image_folders').then(r => r.json()).then(data => {
            const todas = Array.isArray(data) ? data : (data.folders || []);
            const pastas = ['Geral', ...todas.filter(f => f !== 'Geral' && f !== 'Fundos')];
            $('tm-pastas').innerHTML = pastas.map(p => `<button type="button" class="${p === pastaAtiva ? 'ativo' : ''}" data-pasta="${esc(p)}">${esc(p)}</button>`).join('');
            $('tm-pastas').querySelectorAll('button').forEach(b => b.addEventListener('click', () => { pastaAtiva = b.dataset.pasta; carregarPastas(); }));
            carregarImagens(pastaAtiva);
        }).catch(() => carregarImagens('Geral'));
    }
    function carregarImagens(pasta) {
        fetch(`/imagens?folder=${encodeURIComponent(pasta)}`).then(r => r.json()).then(urls => {
            $('tm-imagens').innerHTML = urls.length
                ? urls.map(u => `<button type="button" class="tm-midia" data-url="${esc(u)}"><img src="${esc(u)}" alt="" loading="lazy"></button>`).join('')
                : `<p class="tm-dica">${esc(_t('Nenhuma imagem nesta pasta.'))}</p>`;
            $('tm-imagens').querySelectorAll('[data-url]').forEach(b => b.addEventListener('click', () => trocarFundo({ type: 'image', url: b.dataset.url })));
            marcarMidiaAtiva();
        });
    }
    function carregarVideosEscolha() {
        fetch('/api/fundos').then(r => r.json()).then(d => {
            $('tm-videos-escolha').innerHTML = d.videos.length
                ? d.videos.map(v => `<button type="button" class="tm-midia" data-url="${esc(v.url)}" title="${esc(v.nome)}"><video src="${esc(v.url)}#t=1" muted preload="metadata"></video></button>`).join('')
                : `<p class="tm-dica">${esc(_t('Nenhum vídeo de fundo ainda.'))}</p>`;
            $('tm-videos-escolha').querySelectorAll('[data-url]').forEach(b => b.addEventListener('click', () => trocarFundo({ type: 'video', url: b.dataset.url })));
            marcarMidiaAtiva();
        });
    }

    // ── Lista de temas ──────────────────────────────────────────────
    function miniatura(t) {
        const f = t.fundo || {};
        const midia = f.type === 'image' ? `<img src="${esc(f.url)}" alt="" loading="lazy">`
            : f.type === 'video' ? `<video src="${esc(f.url)}#t=1" muted preload="metadata"></video>` : '';
        const tx = t.texto;
        const estilo = `font-family:${UcTema.FONTES[tx.fonte]};color:${tx.cor};font-weight:${tx.negrito ? 900 : 400};` +
            `text-transform:${tx.maiusculas ? 'uppercase' : 'none'};text-shadow:0 0 2px ${tx.contorno ? tx.contorno_cor : 'transparent'}`;
        return `<span class="tm-mini" style="background:${esc(UcTema.fundoCss(f))}">${midia}<span style="${esc(estilo)}">Aa</span></span>`;
    }
    function desenharLista() {
        $('tm-lista').innerHTML = temas.length ? temas.map(t => `
            <button type="button" class="tm-item${atual && atual.id === t.id ? ' ativo' : ''}" data-id="${t.id}">
                ${miniatura(t)}
                <span class="tm-item-nome">${esc(t.nome)}</span>
                ${t.id === padrao ? `<span class="uc-pill uc-pill-ok">${esc(_t('Padrão'))}</span>` : ''}
                ${t.id === biblia ? `<span class="uc-pill uc-pill-muted">${esc(_t('Bíblia'))}</span>` : ''}
            </button>`).join('')
            : `<p class="tm-dica">${esc(_t('Nenhum tema ainda. Sem tema, o telão usa fundo preto e letra branca com contorno.'))}</p>`;
        $('tm-lista').querySelectorAll('[data-id]').forEach(b => b.addEventListener('click', () => abrir(temas.find(t => t.id === Number(b.dataset.id)))));
    }

    function abrir(tema) {
        if (alterado && !confirm(_t('Descartar as alterações não salvas?'))) return;
        atual = JSON.parse(JSON.stringify(tema));
        alterado = false;
        $('tm-status').textContent = '';
        $('tm-editor').hidden = false;
        $('tm-vazio').hidden = true;
        desenharLista();
        preencher();
    }

    function carregar(abrirId) {
        return fetch('/api/temas').then(r => r.json()).then(d => {
            temas = d.temas;
            padrao = d.padrao;
            biblia = d.biblia;
            desenharLista();
            const sel = $('tm-biblia');
            sel.innerHTML = `<option value="">${esc(_t('O visual de sempre da Bíblia'))}</option>` +
                temas.map(t => `<option value="${t.id}">${esc(t.nome)}</option>`).join('');
            sel.value = biblia || '';
            if (abrirId) { alterado = false; abrir(temas.find(t => t.id === abrirId)); }
        });
    }

    $('tm-novo').addEventListener('click', () => abrir({
        nome: _t('Novo tema'), fundo: { type: 'color', color: '#000000' }, texto: Object.assign({}, CONFIG.textoPadrao),
        transicao: Object.assign({}, CONFIG.transicaoPadrao),
    }));
    $('tm-duplicar').addEventListener('click', () => {
        const copia = JSON.parse(JSON.stringify(atual));
        delete copia.id;
        copia.nome = _t('{nome} (cópia)', { nome: atual.nome });
        alterado = false;
        abrir(copia);
        alterado = true;
        $('tm-status').textContent = _t('Alterações não salvas');
    });

    $('tm-salvar').addEventListener('click', () => {
        const corpo = { nome: $('tm-nome').value, fundo: atual.fundo, texto: atual.texto, transicao: atual.transicao };
        fetch(atual.id ? `/api/temas/${atual.id}` : '/api/temas', {
            method: atual.id ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corpo),
        }).then(r => r.json().then(d => ({ ok: r.ok, d }))).then(({ ok, d }) => {
            if (!ok) { $('tm-status').textContent = d.erro || _t('Não deu para salvar.'); return; }
            alterado = false;
            carregar(d.tema.id).then(() => { $('tm-status').textContent = _t('Salvo. O telão já mostra o tema novo se ele estiver em uso.'); });
        }).catch(() => { $('tm-status').textContent = _t('Não deu para salvar.'); });
    });

    $('tm-padrao').addEventListener('click', () => {
        if (alterado) { $('tm-status').textContent = _t('Salve o tema antes de usar como padrão.'); return; }
        fetch('/api/temas/padrao', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: atual.id }) })
            .then(r => r.json()).then(() => carregar(atual.id)).then(() => { $('tm-status').textContent = _t('Agora é o tema padrão.'); });
    });

    $('tm-apagar').addEventListener('click', () => {
        if (!confirm(_t('Apagar o tema "{nome}"? As músicas e cultos que usam este tema voltam para o tema padrão.', { nome: atual.nome }))) return;
        fetch(`/api/temas/${atual.id}`, { method: 'DELETE' }).then(() => {
            alterado = false;
            atual = null;
            $('tm-editor').hidden = true;
            $('tm-vazio').hidden = false;
            carregar();
        });
    });

    $('tm-biblia').addEventListener('change', () => {
        fetch('/api/temas/biblia', { method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: Number($('tm-biblia').value) || null }) })
            .then(r => r.json()).then(d => {
                biblia = d.biblia;
                desenharLista();
                $('tm-biblia-status').textContent = biblia ? _t('Os versículos já aparecem com este tema.') : _t('A Bíblia voltou ao visual de sempre.');
            });
    });

    window.addEventListener('beforeunload', (e) => { if (alterado) { e.preventDefault(); e.returnValue = ''; } });

    // ── Vídeos de fundo ─────────────────────────────────────────────
    let espera = null;
    function carregarVideos() {
        clearTimeout(espera);
        fetch('/api/fundos').then(r => r.json()).then(d => {
            const itens = d.videos.map(v => `
                <div class="tm-video">
                    <video src="${esc(v.url)}#t=1" muted loop preload="metadata"></video>
                    <span class="tm-video-nome" title="${esc(v.nome)}">${esc(v.nome)}</span>
                    <button type="button" class="uc-btn uc-btn-danger uc-btn-sm" data-apagar="${esc(v.arquivo)}" aria-label="${esc(_t('Apagar'))}"><i class="fas fa-trash"></i></button>
                </div>`);
            d.convertendo.forEach(n => itens.push(`<div class="tm-video tm-video-convertendo"><i class="fas fa-spinner fa-spin"></i><span class="tm-video-nome">${esc(n)}</span><span class="tm-dica">${esc(_t('Preparando…'))}</span></div>`));
            $('tm-videos').innerHTML = itens.length ? itens.join('') : `<p class="tm-dica">${esc(_t('Nenhum vídeo de fundo ainda.'))}</p>`;
            $('tm-videos').querySelectorAll('video').forEach(v => {
                v.addEventListener('mouseenter', () => v.play().catch(() => {}));
                v.addEventListener('mouseleave', () => v.pause());
            });
            $('tm-videos').querySelectorAll('[data-apagar]').forEach(b => b.addEventListener('click', () => {
                if (!confirm(_t('Apagar este vídeo? Temas e músicas que usam ele ficam com fundo preto.'))) return;
                fetch(`/api/fundos/${encodeURIComponent(b.dataset.apagar)}`, { method: 'DELETE' }).then(carregarVideos);
            }));
            if (d.convertendo.length) espera = setTimeout(carregarVideos, 4000);
            else if (!$('tm-editor').hidden && atual && atual.fundo && atual.fundo.type === 'video') carregarVideosEscolha();
        });
    }
    $('tm-enviar-video').addEventListener('click', () => $('tm-video-arquivo').click());
    $('tm-video-arquivo').addEventListener('change', () => {
        const arquivo = $('tm-video-arquivo').files[0];
        $('tm-video-arquivo').value = '';
        if (!arquivo) return;
        $('tm-video-status').textContent = _t('Enviando…');
        const dados = new FormData();
        dados.append('video', arquivo);
        fetch('/api/fundos', { method: 'POST', body: dados })
            .then(r => r.json().then(d => ({ ok: r.ok, d })))
            .then(({ ok, d }) => {
                $('tm-video-status').textContent = ok ? _t('Recebido. O vídeo fica pronto em alguns minutos.') : (d.erro || _t('Não deu para enviar o vídeo.'));
                carregarVideos();
            })
            .catch(() => { $('tm-video-status').textContent = _t('Não deu para enviar o vídeo.'); });
    });

    carregar();
    carregarVideos();
})();
