// Página /importar-musicas (ver blueprints/importar.py e importar_musicas.py)
(function () {
    const $ = id => document.getElementById(id);
    const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
    const plural = (n, um, varios) => (n === 1 ? um : varios).replace('{n}', n);
    const SELO = { nova: _t('Nova'), igual: _t('Já existe igual'), diferente: _t('Já existe, diferente'), repetida: _t('Repetida no arquivo') };
    let token = null;
    let musicas = [];
    const marcadas = new Set();
    const substituir = new Set();

    $('imp-arquivos').addEventListener('change', () => {
        $('imp-conferir').disabled = !$('imp-arquivos').files.length;
        $('imp-msg').textContent = '';
    });

    $('imp-conferir').addEventListener('click', async () => {
        const dados = new FormData();
        [...$('imp-arquivos').files].forEach(f => dados.append('arquivos', f));
        $('imp-conferir').disabled = true;
        $('imp-msg').textContent = _t('Lendo os arquivos…');
        $('imp-resultado').hidden = true;
        try {
            const r = await fetch('/api/importar-musicas/analisar', { method: 'POST', body: dados });
            const d = await r.json().catch(() => ({}));
            if (!r.ok) throw new Error(d.error || (r.status === 413 ? _t('arquivos grandes demais para o endereço da internet; use a rede da igreja') : _t('erro {status}', { status: r.status })));
            token = d.token;
            musicas = d.musicas;
            marcadas.clear();
            substituir.clear();
            musicas.forEach(m => { if (m.status === 'nova') marcadas.add(m.i); });
            $('imp-erros').hidden = !d.erros.length;
            $('imp-erros').innerHTML = d.erros.length ? '<strong>' + _t('Arquivos não lidos:') + '</strong><br>' + d.erros.map(esc).join('<br>') : '';
            $('imp-busca').value = '';
            $('imp-feito').textContent = '';
            renderResumo();
            renderLista();
            $('imp-resultado').hidden = false;
            $('imp-msg').textContent = '';
        } catch (e) {
            $('imp-msg').textContent = _t('Não deu pra ler: {erro}', { erro: e.message });
        }
        $('imp-conferir').disabled = false;
    });

    function renderResumo() {
        const conta = s => musicas.filter(m => m.status === s).length;
        const partes = [plural(conta('nova'), _t('{n} nova'), _t('{n} novas'))];
        if (conta('diferente')) partes.push(_t('{n} já existem e estão diferentes', { n: conta('diferente') }));
        if (conta('igual')) partes.push(_t('{n} já existem iguais', { n: conta('igual') }));
        if (conta('repetida')) partes.push(_t('{n} repetidas nos arquivos', { n: conta('repetida') }));
        $('imp-resumo').textContent = `${plural(musicas.length, _t('{n} música lida'), _t('{n} músicas lidas'))}: ${partes.join(' · ')}`;
        const n = marcadas.size;
        $('imp-importar').disabled = !n;
        $('imp-importar').innerHTML = `<i class="fas fa-file-import"></i> ${plural(n, _t('Importar {n} música'), _t('Importar {n} músicas'))}`;
    }

    function renderLista() {
        const termo = $('imp-busca').value.trim().toLowerCase();
        const visiveis = musicas.filter(m => !termo || `${m.title} ${m.author}`.toLowerCase().includes(termo));
        $('imp-lista').innerHTML = visiveis.slice(0, 1500).map(m => {
            const bloqueada = m.status === 'igual' || m.status === 'repetida';
            return `<div class="imp-item">
                <div class="imp-linha">
                    <label><input type="checkbox" data-i="${m.i}" ${marcadas.has(m.i) ? 'checked' : ''} ${bloqueada ? 'disabled' : ''}>
                        <span><span class="titulo">${esc(m.title)}</span> <span class="detalhe">${esc(m.author || _t('sem artista'))} · ${plural(m.secoes, _t('{n} trecho'), _t('{n} trechos'))}</span></span></label>
                    <span class="selo selo-${m.status}">${SELO[m.status]}</span>
                    ${m.status === 'diferente' ? `<label class="imp-substituir"><input type="checkbox" data-sub="${m.i}" ${substituir.has(m.i) ? 'checked' : ''}> ${_t('substituir a deste computador')}</label>` : ''}
                </div>
                <details><summary>${_t('ver o começo')}</summary><pre>${esc(m.preview)}</pre></details>
            </div>`;
        }).join('') + (visiveis.length > 1500 ? `<p class="uc-muted" style="padding:8px">${_t('Mostrando 1500 de {total}; use a busca.', { total: visiveis.length })}</p>` : '')
            || '<p class="uc-muted" style="padding:8px">' + _t('Nenhuma música encontrada.') + '</p>';
    }

    $('imp-busca').addEventListener('input', renderLista);
    $('imp-lista').addEventListener('change', e => {
        const t = e.target;
        if (t.dataset.i !== undefined) {
            const i = Number(t.dataset.i);
            t.checked ? marcadas.add(i) : marcadas.delete(i);
        } else if (t.dataset.sub !== undefined) {
            const i = Number(t.dataset.sub);
            if (t.checked) { substituir.add(i); marcadas.add(i); } else substituir.delete(i);
            renderLista();
        }
        renderResumo();
    });
    function marcarTodas(sim) {
        const termo = $('imp-busca').value.trim().toLowerCase();
        musicas.filter(m => m.status !== 'igual' && m.status !== 'repetida')
            .filter(m => !termo || `${m.title} ${m.author}`.toLowerCase().includes(termo))
            .forEach(m => { sim ? marcadas.add(m.i) : marcadas.delete(m.i); });
        renderLista();
        renderResumo();
    }
    $('imp-todas').addEventListener('click', () => marcarTodas(true));
    $('imp-nenhuma').addEventListener('click', () => marcarTodas(false));

    $('imp-importar').addEventListener('click', async () => {
        $('imp-importar').disabled = true;
        $('imp-feito').textContent = _t('Importando…');
        try {
            const r = await fetch('/api/importar-musicas/importar', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token, importar: [...marcadas], substituir: [...substituir] }),
            });
            const d = await r.json().catch(() => ({}));
            if (!r.ok) throw new Error(d.error || _t('erro {status}', { status: r.status }));
            const partes = [];
            if (d.novas) partes.push(plural(d.novas, _t('{n} música nova'), _t('{n} músicas novas')));
            if (d.substituidas) partes.push(plural(d.substituidas, _t('{n} substituída'), _t('{n} substituídas')));
            if (d.puladas) partes.push(plural(d.puladas, _t('{n} pulada (já existia)'), _t('{n} puladas (já existiam)')));
            $('imp-feito').innerHTML = _t('✅ Importado: {itens}.', { itens: esc(partes.join(' · ') || _t('nada')) }) + ' <a href="/songs">' + _t('Ver as músicas') + '</a>';
            token = null;
        } catch (e) {
            $('imp-feito').textContent = _t('Não deu pra importar: {erro}', { erro: e.message });
            $('imp-importar').disabled = false;
        }
    });
})();
