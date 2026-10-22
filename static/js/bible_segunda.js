// Seletor "+ 2ª versão" das páginas da Bíblia (templates/_bible_segunda.html).
// Vale pro próximo versículo mandado ao telão, em todas as telas.
(function () {
    const sel = document.getElementById('translation2Select');
    if (!sel) return;
    sel.addEventListener('change', async () => {
        try {
            const r = await fetch('/api/bible/set_translation2', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ translation: sel.value }),
            });
            if (!r.ok) throw new Error();
            if (window.ucToast) window.ucToast(sel.value
                ? 'Os próximos versículos vão ao telão com as duas versões.'
                : 'Os próximos versículos vão ao telão só com uma versão.');
        } catch (e) {
            if (window.ucToast) window.ucToast('Não deu pra salvar a 2ª versão.', 'error');
        }
    });
})();
