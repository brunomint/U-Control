// Painel "Site" do Controle (templates/_site_telao.html): abre um site no
// telão e manda os comandos (blueprints/site.py -> navegador_telao.py).
(function () {
    const pane = document.querySelector('.site-telao');
    if (!pane) return;
    const $ = id => document.getElementById(id);
    const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
    let atual = {};

    function msg(t) { $('site-msg').textContent = t || ''; }

    function mostrar(e) {
        atual = e || {};
        $('site-aberto').hidden = !atual.aberto;
        $('site-titulo').textContent = atual.aberto ? (atual.titulo || atual.url || _t('Site aberto')) : '';
        $('site-zoom').textContent = Math.round((atual.zoom || 1) * 100) + '%';
    }

    async function post(url, corpo) {
        const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corpo || {}) });
        const d = await r.json().catch(() => ({}));
        if (!r.ok || d.ok === false) throw new Error(d.erro || _t('erro {status}', { status: r.status }));
        return d;
    }

    async function abrir(url) {
        msg(_t('Abrindo no telão…'));
        try {
            mostrar(await post('/api/site/abrir', { url }));
            msg('');
        } catch (e) { msg(e.message); }
    }

    $('site-form').addEventListener('submit', e => {
        e.preventDefault();
        if ($('site-url').value.trim()) abrir($('site-url').value);
    });

    pane.addEventListener('click', async e => {
        const b = e.target.closest('[data-site]');
        if (!b) return;
        try { mostrar(await post('/api/site/comando', { acao: b.dataset.site })); msg(''); }
        catch (err) { msg(err.message); }
    });

    $('site-fechar').addEventListener('click', async () => {
        try { mostrar(await post('/api/site/fechar')); msg(_t('Site fechado. O telão volta ao que estava.')); }
        catch (err) { msg(err.message); }
    });

    // Sites salvos (os mesmos em todos os Controles)
    function renderSalvos(lista) {
        $('site-salvos').innerHTML = (lista || []).map(s => `<span class="site-salvo">
            <button type="button" class="site-ir" data-url="${esc(s.url)}" title="${esc(s.url)}">${esc(s.nome)}</button>
            <button type="button" class="site-tirar" data-url="${esc(s.url)}" title="${esc(_t('Tirar dos salvos'))}" aria-label="${esc(_t('Tirar {nome} dos salvos', { nome: s.nome }))}">×</button></span>`).join('');
    }
    $('site-salvos').addEventListener('click', async e => {
        const ir = e.target.closest('.site-ir');
        const tirar = e.target.closest('.site-tirar');
        if (ir) abrir(ir.dataset.url);
        if (tirar) { try { renderSalvos((await post('/api/site/salvos/remover', { url: tirar.dataset.url })).salvos); } catch (err) { msg(err.message); } }
    });
    $('site-salvar').addEventListener('click', async () => {
        const nome = (atual.titulo || '').slice(0, 40);
        try { renderSalvos((await post('/api/site/salvos', { url: atual.url, nome })).salvos); msg(_t('Salvo nos sites.')); }
        catch (err) { msg(err.message); }
    });

    fetch('/api/site/salvos').then(r => r.json()).then(renderSalvos).catch(() => {});
    fetch('/api/site/estado').then(r => r.json()).then(mostrar).catch(() => {});
    if (typeof socket !== 'undefined') socket.on('site_estado', mostrar);  // outro Controle abriu/fechou
})();
