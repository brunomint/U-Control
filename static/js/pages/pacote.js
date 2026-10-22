// Página /pacote (ver blueprints/pacote.py): escolher o que levar e
// importar o que veio de outro U-Control.
(function () {
    const $ = id => document.getElementById(id);
    const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
    const plural = (n, um, varios) => `${n} ${n === 1 ? um : varios}`;
    const escolhido = { musicas: new Set(), cultos: new Set(), pastas: new Set() };
    let itens = { musicas: [], cultos: [], pastas: [] };

    function dataCulto(chave) {
        const [a, m, d, n] = chave.split('-');
        const dt = new Date(+a, +m - 1, +d);
        const txt = dt.toLocaleDateString('pt-BR', { weekday: 'short', day: '2-digit', month: '2-digit', year: 'numeric' });
        return n ? `${txt} (${n}º culto)` : txt;
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
            [c.tipo, c.tema, c.musicas ? plural(c.musicas, 'música', 'músicas') : ''].filter(Boolean).join(' · '));
        let html = '';
        if (proximos.length) html += '<div class="pacote-separador">Próximos</div>' + proximos.map(um).join('');
        if (passados.length) html += '<div class="pacote-separador">Anteriores</div>' + passados.map(um).join('');
        $('lista-cultos').innerHTML = html || '<p class="uc-muted">Nenhum culto cadastrado.</p>';
    }

    function renderMusicas() {
        const termo = $('busca-musicas').value.trim().toLowerCase();
        const lista = itens.musicas.filter(m => !termo || `${m.title} ${m.author}`.toLowerCase().includes(termo));
        $('lista-musicas').innerHTML = lista.map(m => linha('musicas', String(m.id), m.title, m.author)).join('')
            || '<p class="uc-muted">Nenhuma música encontrada.</p>';
    }

    function renderPastas() {
        $('lista-pastas').innerHTML = itens.pastas.map(p => linha('pastas', p.nome, p.nome, plural(p.arquivos, 'arquivo', 'arquivos'))).join('')
            || '<p class="uc-muted">Nenhuma foto na galeria.</p>';
    }

    function renderResumo() {
        const partes = [];
        if (escolhido.cultos.size) partes.push(plural(escolhido.cultos.size, 'culto', 'cultos'));
        if (escolhido.musicas.size) partes.push(plural(escolhido.musicas.size, 'música', 'músicas'));
        if (escolhido.pastas.size) partes.push(plural(escolhido.pastas.size, 'pasta', 'pastas'));
        $('exp-resumo').textContent = partes.length ? 'Levar: ' + partes.join(' · ') + (escolhido.cultos.size ? ' (+ as músicas dos cultos)' : '') : 'Nada escolhido.';
        $('exp-baixar').disabled = !partes.length;
    }

    document.addEventListener('change', e => {
        const t = e.target;
        if (!t.dataset || !t.dataset.tipo) return;
        if (t.checked) escolhido[t.dataset.tipo].add(t.value);
        else escolhido[t.dataset.tipo].delete(t.value);
        renderResumo();
    });
    $('busca-musicas').addEventListener('input', renderMusicas);

    fetch('/api/pacote/itens').then(r => r.json()).then(d => {
        itens = d;
        renderCultos();
        renderMusicas();
        renderPastas();
    }).catch(() => { $('lista-cultos').textContent = 'Não deu pra carregar.'; });

    $('exp-baixar').addEventListener('click', async () => {
        const botao = $('exp-baixar');
        botao.disabled = true;
        $('exp-msg').textContent = 'Montando o pacote…';
        try {
            const r = await fetch('/api/pacote/exportar', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ musicas: [...escolhido.musicas].map(Number), cultos: [...escolhido.cultos], pastas: [...escolhido.pastas] }),
            });
            if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || `erro ${r.status}`);
            const nome = (/filename="?([^";]+)/.exec(r.headers.get('Content-Disposition') || '') || [])[1] || 'U-Control-pacote.zip';
            const url = URL.createObjectURL(await r.blob());
            const a = Object.assign(document.createElement('a'), { href: url, download: nome });
            document.body.appendChild(a);
            a.click();
            a.remove();
            setTimeout(() => URL.revokeObjectURL(url), 60000);
            $('exp-msg').textContent = `Pronto: ${nome}. Leve esse arquivo para o outro computador e importe em Sistema → Exportar e importar.`;
        } catch (e) {
            $('exp-msg').textContent = 'Não deu pra montar o pacote: ' + e.message;
        }
        botao.disabled = false;
    });

    // --- Importar ---------------------------------------------------------
    let token = null;
    const STATUS = { nova: ['novo', 'Nova'], novo: ['novo', 'Novo'], igual: ['igual', 'Já existe igual'], diferente: ['diferente', 'Já existe, diferente'] };

    function selo(status) {
        const [classe, texto] = STATUS[status];
        return `<span class="selo selo-${classe}">${texto}</span>`;
    }
    function escolha(tipo, chave) {
        const nome = `${tipo}-${chave}`;
        return `<span class="escolha">
            <label><input type="radio" name="${esc(nome)}" data-imp="${tipo}" data-chave="${esc(chave)}" value="pacote" checked> usar a do pacote</label>
            <label><input type="radio" name="${esc(nome)}" data-imp="${tipo}" data-chave="${esc(chave)}" value="daqui"> manter a deste computador</label></span>`;
    }

    function renderPrevia(d) {
        let html = '';
        if (d.cultos.length) {
            html += '<h3>Cultos</h3>' + d.cultos.map(c => `<div class="previa-linha"><span class="titulo">${esc(dataCulto(c.chave))}
                ${c.tipo ? `<span class="uc-muted">· ${esc(c.tipo)}</span>` : ''}</span>${selo(c.status)}
                ${c.status === 'diferente' ? escolha('cultos', c.chave) : ''}</div>`).join('');
        }
        if (d.musicas.length) {
            html += '<h3>Músicas</h3>' + d.musicas.map(m => `<div class="previa-linha"><span class="titulo">${esc(m.title)}
                <span class="uc-muted">· ${esc(m.author)}</span></span>${selo(m.status)}
                ${m.status === 'diferente' ? escolha('musicas', m.ref) : ''}</div>`).join('');
        }
        if (d.pastas.length) {
            html += '<h3>Fotos e slides</h3>' + d.pastas.map(p => `<div class="previa-linha"><span class="titulo">${esc(p.nome)}</span>
                <span class="uc-muted">${plural(p.arquivos, 'arquivo', 'arquivos')}${p.ja_existem ? ` · ${p.ja_existem} com o mesmo nome aqui serão substituídos` : ''}</span></div>`).join('');
        }
        $('imp-previa').innerHTML = html || '<p class="uc-muted">O pacote está vazio.</p>';
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
        $('imp-msg').textContent = 'Conferindo o pacote…';
        try {
            const r = await fetch('/api/pacote/analisar', { method: 'POST', body: dados });
            const d = await r.json().catch(() => ({}));
            if (!r.ok) throw new Error(d.error || (r.status === 413 ? 'arquivo grande demais para o endereço da internet; use a rede da igreja' : `erro ${r.status}`));
            token = d.token;
            renderPrevia(d);
            const dif = d.musicas.filter(m => m.status === 'diferente').length + d.cultos.filter(c => c.status === 'diferente').length;
            const tudoIgual = !d.pastas.length && [...d.musicas, ...d.cultos].every(x => x.status === 'igual');
            if (tudoIgual) {
                $('imp-importar').hidden = true;
                $('imp-msg').textContent = 'Este computador já tem tudo o que está no pacote, igual. Nada a importar.';
            } else {
                $('imp-msg').textContent = dif ? `Confira os ${dif} que já existem e estão diferentes, depois clique em Importar.` : 'Tudo certo. Clique em Importar.';
            }
        } catch (e) {
            $('imp-msg').textContent = 'Não deu pra ler o pacote: ' + e.message;
        }
        $('imp-conferir').disabled = false;
    });

    $('imp-importar').addEventListener('click', async () => {
        const escolhas = { musicas: {}, cultos: {} };
        document.querySelectorAll('#imp-previa input[type=radio]:checked').forEach(r => { escolhas[r.dataset.imp][r.dataset.chave] = r.value; });
        $('imp-importar').disabled = true;
        $('imp-msg').textContent = 'Importando…';
        try {
            const r = await fetch('/api/pacote/importar', {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token, escolhas }),
            });
            const d = await r.json().catch(() => ({}));
            if (!r.ok) throw new Error(d.error || `erro ${r.status}`);
            const partes = [];
            if (d.musicas_novas) partes.push(plural(d.musicas_novas, 'música nova', 'músicas novas'));
            if (d.musicas_atualizadas) partes.push(plural(d.musicas_atualizadas, 'música atualizada', 'músicas atualizadas'));
            if (d.cultos) partes.push(plural(d.cultos, 'culto', 'cultos'));
            if (d.arquivos) partes.push(plural(d.arquivos, 'foto/slide', 'fotos/slides'));
            $('imp-msg').textContent = 'Importado: ' + (partes.join(' · ') || 'nada mudou (já estava tudo igual)') + '.';
            $('imp-importar').hidden = true;
            token = null;
        } catch (e) {
            $('imp-msg').textContent = 'Não deu pra importar: ' + e.message;
            $('imp-importar').disabled = false;
        }
    });
})();
