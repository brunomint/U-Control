// Página /pacote (ver blueprints/pacote.py): escolher o que levar e
// importar o que veio de outro U-Control.
(function () {
    const $ = id => document.getElementById(id);
    const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
    const plural = (n, um, varios) => (n === 1 ? um : varios).replace('{n}', n);
    const escolhido = { musicas: new Set(), cultos: new Set(), pastas: new Set() };
    let itens = { musicas: [], cultos: [], pastas: [] };

    function dataCulto(chave) {
        const [a, m, d, n] = chave.split('-');
        const dt = new Date(+a, +m - 1, +d);
        const txt = dt.toLocaleDateString(ucLocale(), { weekday: 'short', day: '2-digit', month: '2-digit', year: 'numeric' });
        return n ? _t('{data} ({n}º culto)', { data: txt, n }) : txt;
    }

    function linha(tipo, valor, titulo, detalhe) {
        const marcado = escolhido[tipo].has(valor) ? 'checked' : '';
        return `<label class="pacote-item"><input type="checkbox" data-tipo="${tipo}" value="${esc(valor)}" ${marcado}>
            <span><span class="titulo">${esc(titulo)}</span>${detalhe ? ` <span class="detalhe">${esc(detalhe)}</span>` : ''}</span></label>`;
    }

    function renderCultos() {
        const proximos = itens.cultos.filter(c => !c.passado);
        const passados = itens.cultos.filter(c => c.passado);
        const um = c => linha('cultos', c.chave, dataCulto(c.chave),
            [c.tipo, c.tema, c.musicas ? plural(c.musicas, _t('{n} música'), _t('{n} músicas')) : ''].filter(Boolean).join(' · '));
        let html = '';
        if (proximos.length) html += '<div class="pacote-separador">' + _t('Próximos') + '</div>' + proximos.map(um).join('');
        if (passados.length) html += '<div class="pacote-separador">' + _t('Anteriores') + '</div>' + passados.map(um).join('');
        $('lista-cultos').innerHTML = html || '<p class="uc-muted">' + _t('Nenhum culto cadastrado.') + '</p>';
    }

    function renderMusicas() {
        const termo = $('busca-musicas').value.trim().toLowerCase();
        const lista = itens.musicas.filter(m => !termo || `${m.title} ${m.author}`.toLowerCase().includes(termo));
        $('lista-musicas').innerHTML = lista.map(m => linha('musicas', String(m.id), m.title, m.author)).join('')
            || '<p class="uc-muted">' + _t('Nenhuma música encontrada.') + '</p>';
    }

    function renderPastas() {
        $('lista-pastas').innerHTML = itens.pastas.map(p => linha('pastas', p.nome, p.nome, plural(p.arquivos, _t('{n} arquivo'), _t('{n} arquivos')))).join('')
            || '<p class="uc-muted">' + _t('Nenhuma foto na galeria.') + '</p>';
    }

    // Valores que a lista mostra agora — "Selecionar todas" das músicas vale
    // só pro resultado da busca (ex.: buscar um artista e levar as dele).
    // 'proximos' é o "Só os próximos" dos cultos: os que ainda vão acontecer.
    const conjunto = tipo => tipo === 'proximos' ? 'cultos' : tipo;
    function visiveis(tipo) {
        if (tipo === 'cultos') return itens.cultos.map(c => c.chave);
        if (tipo === 'proximos') return itens.cultos.filter(c => !c.passado).map(c => c.chave);
        if (tipo === 'pastas') return itens.pastas.map(p => p.nome);
        const termo = $('busca-musicas').value.trim().toLowerCase();
        return itens.musicas.filter(m => !termo || `${m.title} ${m.author}`.toLowerCase().includes(termo)).map(m => String(m.id));
    }

    function renderTodos() {
        for (const tipo of ['cultos', 'proximos', 'musicas', 'pastas']) {
            const caixa = document.querySelector(`[data-todos="${tipo}"]`);
            const lista = visiveis(tipo);
            const marcados = lista.filter(v => escolhido[conjunto(tipo)].has(v)).length;
            caixa.closest('label').hidden = !lista.length;
            caixa.checked = lista.length > 0 && marcados === lista.length;
            caixa.indeterminate = marcados > 0 && marcados < lista.length;
            if (tipo === 'musicas') {
                caixa.nextElementSibling.textContent = lista.length < itens.musicas.length
                    ? plural(lista.length, _t('Selecionar {n} encontrada'), _t('Selecionar {n} encontradas')) : _t('Selecionar todas');
            }
            if (tipo === 'proximos') {
                caixa.nextElementSibling.textContent = _t('Só os próximos ({n})', { n: lista.length });
                continue;
            }
            const total = itens[tipo].length;
            $('conta-' + tipo).textContent = escolhido[tipo].size ? _t('({n} de {total})', { n: escolhido[tipo].size, total }) : '';
        }
    }

    function renderResumo() {
        renderTodos();
        const partes = [];
        if (escolhido.cultos.size) partes.push(plural(escolhido.cultos.size, _t('{n} culto'), _t('{n} cultos')));
        if (escolhido.musicas.size) partes.push(plural(escolhido.musicas.size, _t('{n} música'), _t('{n} músicas')));
        if (escolhido.pastas.size) partes.push(plural(escolhido.pastas.size, _t('{n} pasta'), _t('{n} pastas')));
        $('exp-resumo').textContent = !partes.length ? _t('Nada escolhido.')
            : escolhido.cultos.size ? _t('Levar: {itens} (+ as músicas dos cultos)', { itens: partes.join(' · ') })
            : _t('Levar: {itens}', { itens: partes.join(' · ') });
        $('exp-baixar').disabled = !partes.length;
    }

    document.addEventListener('change', e => {
        const t = e.target;
        if (t.dataset && t.dataset.todos) {
            const tipo = conjunto(t.dataset.todos);
            visiveis(t.dataset.todos).forEach(v => t.checked ? escolhido[tipo].add(v) : escolhido[tipo].delete(v));
            ({ cultos: renderCultos, musicas: renderMusicas, pastas: renderPastas })[tipo]();
            renderResumo();
            return;
        }
        if (!t.dataset || !t.dataset.tipo) return;
        if (t.checked) escolhido[t.dataset.tipo].add(t.value);
        else escolhido[t.dataset.tipo].delete(t.value);
        renderResumo();
    });
    $('busca-musicas').addEventListener('input', () => { renderMusicas(); renderTodos(); });

    fetch('/api/pacote/itens').then(r => r.json()).then(d => {
        itens = d;
        renderCultos();
        renderMusicas();
        renderPastas();
        renderTodos();
    }).catch(() => { $('lista-cultos').textContent = _t('Não deu pra carregar.'); });

    $('exp-baixar').addEventListener('click', async () => {
        const botao = $('exp-baixar');
        botao.disabled = true;
        $('exp-msg').textContent = _t('Montando o pacote…');
        try {
            const r = await fetch('/api/pacote/exportar', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ musicas: [...escolhido.musicas].map(Number), cultos: [...escolhido.cultos], pastas: [...escolhido.pastas] }),
            });
            if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || _t('erro {status}', { status: r.status }));
            const nome = (/filename="?([^";]+)/.exec(r.headers.get('Content-Disposition') || '') || [])[1] || 'U-Control-pacote.zip';
            const url = URL.createObjectURL(await r.blob());
            const a = Object.assign(document.createElement('a'), { href: url, download: nome });
            document.body.appendChild(a);
            a.click();
            a.remove();
            setTimeout(() => URL.revokeObjectURL(url), 60000);
            $('exp-msg').textContent = _t('Pronto: {nome}. Leve esse arquivo para o outro computador e importe em Sistema → Exportar e importar.', { nome });
        } catch (e) {
            $('exp-msg').textContent = _t('Não deu pra montar o pacote: {erro}', { erro: e.message });
        }
        botao.disabled = false;
    });

    // --- Importar ---------------------------------------------------------
    let token = null;
    const STATUS = { nova: ['novo', _t('Nova')], novo: ['novo', _t('Novo')], igual: ['igual', _t('Já existe igual')], diferente: ['diferente', _t('Já existe, diferente')] };

    function selo(status) {
        const [classe, texto] = STATUS[status];
        return `<span class="selo selo-${classe}">${texto}</span>`;
    }
    function escolha(tipo, chave) {
        const nome = `${tipo}-${chave}`;
        return `<span class="escolha">
            <label><input type="radio" name="${esc(nome)}" data-imp="${tipo}" data-chave="${esc(chave)}" value="pacote" checked> ${_t('usar a do pacote')}</label>
            <label><input type="radio" name="${esc(nome)}" data-imp="${tipo}" data-chave="${esc(chave)}" value="daqui"> ${_t('manter a deste computador')}</label></span>`;
    }

    function renderPrevia(d) {
        let html = '';
        if (d.cultos.length) {
            html += '<h3>' + _t('Cultos') + '</h3>' + d.cultos.map(c => `<div class="previa-linha"><span class="titulo">${esc(dataCulto(c.chave))}
                ${c.tipo ? `<span class="uc-muted">· ${esc(c.tipo)}</span>` : ''}</span>${selo(c.status)}
                ${c.status === 'diferente' ? escolha('cultos', c.chave) : ''}</div>`).join('');
        }
        if (d.musicas.length) {
            html += '<h3>' + _t('Músicas') + '</h3>' + d.musicas.map(m => `<div class="previa-linha"><span class="titulo">${esc(m.title)}
                <span class="uc-muted">· ${esc(m.author)}</span></span>${selo(m.status)}
                ${m.status === 'diferente' ? escolha('musicas', m.ref) : ''}</div>`).join('');
        }
        if (d.pastas.length) {
            html += '<h3>' + _t('Fotos e slides') + '</h3>' + d.pastas.map(p => `<div class="previa-linha"><span class="titulo">${esc(p.nome)}</span>
                <span class="uc-muted">${plural(p.arquivos, _t('{n} arquivo'), _t('{n} arquivos'))}${p.ja_existem ? _t(' · {n} com o mesmo nome aqui serão substituídos', { n: p.ja_existem }) : ''}</span></div>`).join('');
        }
        $('imp-previa').innerHTML = html || '<p class="uc-muted">' + _t('O pacote está vazio.') + '</p>';
        $('imp-previa').hidden = false;
        const algo = d.cultos.length || d.musicas.length || d.pastas.length;
        $('imp-importar').hidden = !algo;
        $('imp-importar').disabled = !algo;
    }

    $('imp-arquivo').addEventListener('change', () => {
        $('imp-conferir').disabled = !$('imp-arquivo').files.length;
        $('imp-previa').hidden = true;
        $('imp-importar').hidden = true;
        $('imp-msg').textContent = '';
        token = null;
    });

    $('imp-conferir').addEventListener('click', async () => {
        const dados = new FormData();
        dados.append('arquivo', $('imp-arquivo').files[0]);
        $('imp-conferir').disabled = true;
        $('imp-msg').textContent = _t('Conferindo o pacote…');
        try {
            const r = await fetch('/api/pacote/analisar', { method: 'POST', body: dados });
            const d = await r.json().catch(() => ({}));
            if (!r.ok) throw new Error(d.error || (r.status === 413 ? _t('arquivo grande demais para o endereço da internet; use a rede da igreja') : _t('erro {status}', { status: r.status })));
            token = d.token;
            renderPrevia(d);
            const dif = d.musicas.filter(m => m.status === 'diferente').length + d.cultos.filter(c => c.status === 'diferente').length;
            const tudoIgual = !d.pastas.length && [...d.musicas, ...d.cultos].every(x => x.status === 'igual');
            if (tudoIgual) {
                $('imp-importar').hidden = true;
                $('imp-msg').textContent = _t('Este computador já tem tudo o que está no pacote, igual. Nada a importar.');
            } else {
                $('imp-msg').textContent = dif ? _t('Confira os {n} que já existem e estão diferentes, depois clique em Importar.', { n: dif }) : _t('Tudo certo. Clique em Importar.');
            }
        } catch (e) {
            $('imp-msg').textContent = _t('Não deu pra ler o pacote: {erro}', { erro: e.message });
        }
        $('imp-conferir').disabled = false;
    });

    $('imp-importar').addEventListener('click', async () => {
        const escolhas = { musicas: {}, cultos: {} };
        document.querySelectorAll('#imp-previa input[type=radio]:checked').forEach(r => { escolhas[r.dataset.imp][r.dataset.chave] = r.value; });
        $('imp-importar').disabled = true;
        $('imp-msg').textContent = _t('Importando…');
        try {
            const r = await fetch('/api/pacote/importar', {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token, escolhas }),
            });
            const d = await r.json().catch(() => ({}));
            if (!r.ok) throw new Error(d.error || _t('erro {status}', { status: r.status }));
            const partes = [];
            if (d.musicas_novas) partes.push(plural(d.musicas_novas, _t('{n} música nova'), _t('{n} músicas novas')));
            if (d.musicas_atualizadas) partes.push(plural(d.musicas_atualizadas, _t('{n} música atualizada'), _t('{n} músicas atualizadas')));
            if (d.cultos) partes.push(plural(d.cultos, _t('{n} culto'), _t('{n} cultos')));
            if (d.arquivos) partes.push(plural(d.arquivos, _t('{n} foto/slide'), _t('{n} fotos/slides')));
            $('imp-msg').textContent = partes.length ? _t('Importado: {itens}.', { itens: partes.join(' · ') }) : _t('Importado: nada mudou (já estava tudo igual).');
            $('imp-importar').hidden = true;
            token = null;
        } catch (e) {
            $('imp-msg').textContent = _t('Não deu pra importar: {erro}', { erro: e.message });
            $('imp-importar').disabled = false;
        }
    });
})();
