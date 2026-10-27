// "Ordem no culto" dos editores de música (new_song.js / edit_song.js).
//
// A ordem é uma sequência de seções com repetição (Verso 1 → Refrão →
// Verso 2 → Refrão): o refrão fica escrito uma vez só. Aqui ela é guardada
// pelos ids dos blocos de seção do editor — renomear, mover ou apagar uma
// seção não bagunça a ordem —; ao salvar vira posições em song.sections
// (o servidor guarda em Song.order, ver songs_store.normalize_order).
// Sem ordem, a música é apresentada de cima pra baixo, como sempre.
(function () {
    let ids = [];           // ids dos blocos de seção, na ordem de apresentação
    let getBlocks = () => [];
    let box = null;

    const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => (
        { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

    // Só seções com nome: são as que dá pra reconhecer na sequência
    function secoes() {
        return getBlocks().filter(b => b.type === 'section' && (b.title || '').trim());
    }

    function render() {
        if (!box) return;
        const lista = secoes();
        const porId = new Map(lista.map(b => [b.id, b]));
        ids = ids.filter(id => porId.has(id));   // seção apagada sai da ordem
        const fichas = ids.map((id, i) => `
            <span class="ordem-ficha">${esc(porId.get(id).title)}
                <button type="button" data-tirar="${i}" title="${esc(_t('Tirar da ordem'))}" aria-label="${esc(_t('Tirar {secao} da ordem', { secao: porId.get(id).title }))}">×</button>
            </span>`).join('<span class="ordem-seta" aria-hidden="true">→</span>');
        box.querySelector('.ordem-sequencia').innerHTML = ids.length ? fichas
            : `<span class="ordem-vazia">${esc(_t('Sem ordem: as seções aparecem de cima pra baixo.'))}</span>`;
        box.querySelector('.ordem-botoes').innerHTML = lista.length
            ? lista.map(b => `<button type="button" class="uc-btn uc-btn-ghost uc-btn-sm" data-por="${b.id}">+ ${esc(b.title)}</button>`).join('')
            : `<span class="ordem-vazia">${esc(_t('Dê nome às seções para montar a ordem.'))}</span>`;
        box.querySelector('[data-limpar]').hidden = !ids.length;
    }

    function init(opcoes) {
        box = document.getElementById('songOrder');
        if (!box) return;
        getBlocks = opcoes.getBlocks;
        box.addEventListener('click', e => {
            const por = e.target.closest('[data-por]');
            const tirar = e.target.closest('[data-tirar]');
            if (por) ids.push(Number(por.dataset.por));
            else if (tirar) ids.splice(Number(tirar.dataset.tirar), 1);
            else if (e.target.closest('[data-limpar]')) ids = [];
            else return;
            render();
        });
        // As seções mudam no editor (nova, renomeada, apagada, movida):
        // acompanha sem precisar mexer no renderBlocks de cada editor
        const editor = document.getElementById('blockContainer');
        if (editor) {
            new MutationObserver(render).observe(editor, { childList: true, subtree: true });
            editor.addEventListener('input', () => setTimeout(render, 0));
        }
        render();
    }

    // Ao carregar uma música salva: posições -> ids dos blocos criados
    function carregar(ordem, idPorPosicao) {
        ids = (ordem || []).map(i => idPorPosicao[i]).filter(id => id != null);
        render();
    }

    // Ao salvar: ids -> posições das seções montadas pelo editor
    function posicoes(posicaoPorId) {
        return ids.map(id => posicaoPorId[id]).filter(i => i != null);
    }

    window.SongOrder = { init, carregar, posicoes, render };
})();
