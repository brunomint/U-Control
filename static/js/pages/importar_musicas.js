// Página /importar-musicas (ver blueprints/importar.py e importar_musicas.py)
(function () {
    const $ = id => document.getElementById(id);
    const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
    const plural = (n, um, varios) => `${n} ${n === 1 ? um : varios}`;
    const SELO = { nova: 'Nova', igual: 'Já existe igual', diferente: 'Já existe, diferente', repetida: 'Repetida no arquivo' };
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
        $('imp-msg').textContent = 'Lendo os arquivos…';
        $('imp-resultado').hidden = true;
        try {
            const r = await fetch('/api/importar-musicas/analisar', { method: 'POST', body: dados });
            const d = await r.json().catch(() => ({}));
            if (!r.ok) throw new Error(d.error || (r.status === 413 ? 'arquivos grandes demais para o endereço da internet; use a rede da igreja' : `erro ${r.status}`));
            token = d.token;
            musicas = d.musicas;
            marcadas.clear();
            substituir.clear();
            musicas.forEach(m => { if (m.status === 'nova') marcadas.add(m.i); });
            $('imp-erros').hidden = !d.erros.length;
            $('imp-erros').innerHTML = d.erros.length ? '<strong>Arquivos não lidos:</strong><br>' + d.erros.map(esc).join('<br>') : '';
            $('imp-busca').value = '';
            $('imp-feito').textContent = '';
            renderResumo();
            renderLista();
            $('imp-resultado').hidden = false;
            $('imp-msg').textContent = '';
        } catch (e) {
            $('imp-msg').textContent = 'Não deu pra ler: ' + e.message;
        }
        $('imp-conferir').disabled = false;
    });

    function renderResumo() {
        const conta = s => musicas.filter(m => m.status === s).length;
        const partes = [plural(conta('nova'), 'nova', 'novas')];
        if (conta('diferente')) partes.push(`${conta('diferente')} já existem e estão diferentes`);
        if (conta('igual')) partes.push(`${conta('igual')} já existem iguais`);
        if (conta('repetida')) partes.push(`${conta('repetida')} repetidas nos arquivos`);
        $('imp-resumo').textContent = `${plural(musicas.length, 'música lida', 'músicas lidas')}: ${partes.join(' · ')}`;
        const n = marcadas.size;
        $('imp-importar').disabled = !n;
        $('imp-importar').innerHTML = `<i class="fas fa-file-import"></i> Importar ${plural(n, 'música', 'músicas')}`;
    }

    function renderLista() {
        const termo = $('imp-busca').value.trim().toLowerCase();
        const visiveis = musicas.filter(m => !termo || `${m.title} ${m.author}`.toLowerCase().includes(termo));
        $('imp-lista').innerHTML = visiveis.slice(0, 1500).map(m => {
            const bloqueada = m.status === 'igual' || m.status === 'repetida';
            return `<div class="imp-item">
                <div class="imp-linha">
                    <label><input type="checkbox" data-i="${m.i}" ${marcadas.has(m.i) ? 'checked' : ''} ${bloqueada ? 'disabled' : ''}>
                        <span><span class="titulo">${esc(m.title)}</span> <span class="detalhe">${esc(m.author || 'sem artista')} · ${plural(m.secoes, 'trecho', 'trechos')}</span></span></label>
                    <span class="selo selo-${m.status}">${SELO[m.status]}</span>
                    ${m.status === 'diferente' ? `<label class="imp-substituir"><input type="checkbox" data-sub="${m.i}" ${substituir.has(m.i) ? 'checked' : ''}> substituir a deste computador</label>` : ''}
                </div>
                <details><summary>ver o começo</summary><pre>${esc(m.preview)}</pre></details>
            </div>`;
        }).join('') + (visiveis.length > 1500 ? `<p class="uc-muted" style="padding:8px">Mostrando 1500 de ${visiveis.length}; use a busca.</p>` : '')
            || '<p class="uc-muted" style="padding:8px">Nenhuma música encontrada.</p>';
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
        $('imp-feito').textContent = 'Importando…';
        try {
            const r = await fetch('/api/importar-musicas/importar', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token, importar: [...marcadas], substituir: [...substituir] }),
            });
            const d = await r.json().catch(() => ({}));
            if (!r.ok) throw new Error(d.error || `erro ${r.status}`);
            const partes = [];
            if (d.novas) partes.push(plural(d.novas, 'música nova', 'músicas novas'));
            if (d.substituidas) partes.push(plural(d.substituidas, 'substituída', 'substituídas'));
            if (d.puladas) partes.push(plural(d.puladas, 'pulada (já existia)', 'puladas (já existiam)'));
            $('imp-feito').innerHTML = `✅ Importado: ${esc(partes.join(' · ') || 'nada')}. <a href="/songs">Ver as músicas</a>`;
            token = null;
        } catch (e) {
            $('imp-feito').textContent = 'Não deu pra importar: ' + e.message;
            $('imp-importar').disabled = false;
        }
    });
})();
