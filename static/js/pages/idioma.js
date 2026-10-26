// Página /idioma (blueprints/idioma.py): salva e recarrega, já no idioma novo.
(function () {
    const botao = document.getElementById('idioma-salvar');
    const msg = document.getElementById('idioma-msg');
    botao.addEventListener('click', async () => {
        const escolhido = document.querySelector('input[name="idioma"]:checked');
        botao.disabled = true;
        try {
            const r = await fetch('/api/idioma', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ idioma: escolhido ? escolhido.value : '' }),
            });
            if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || `erro ${r.status}`);
            location.reload();
        } catch (e) {
            msg.textContent = _t('Não deu pra salvar: {erro}', { erro: e.message });
            botao.disabled = false;
        }
    });
})();
