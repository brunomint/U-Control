// Página /atalhos (ver blueprints/atalhos.py)
(function () {
    const msg = document.getElementById('at-msg');
    const toast = (t, tipo) => (window.ucToast ? window.ucToast(t, tipo) : (msg.textContent = t));

    document.querySelectorAll('.at-copiar').forEach(b => b.addEventListener('click', async () => {
        const input = b.parentElement.querySelector('input');
        try {
            await navigator.clipboard.writeText(input.value);
        } catch (e) {  // http na rede: sem clipboard API, seleciona pra Ctrl+C
            input.select();
            document.execCommand && document.execCommand('copy');
        }
        toast(_t('Endereço copiado.'));
    }));

    document.querySelectorAll('.at-testar').forEach(b => b.addEventListener('click', async () => {
        const url = b.parentElement.querySelector('input').value;
        try {
            const r = await fetch(url, { method: 'POST' });
            const d = await r.json();
            msg.textContent = d.ok ? `✅ ${JSON.stringify(d)}` : `⚠️ ${d.erro || r.status}`;
        } catch (e) {
            msg.textContent = _t('Não deu pra testar: {erro}', { erro: e.message });
        }
    }));

    document.getElementById('at-trocar').addEventListener('click', async () => {
        try {
            const r = await fetch('/api/atalhos/trocar-chave', { method: 'POST' });
            const d = await r.json();
            document.getElementById('at-chave').textContent = d.chave;
            document.querySelectorAll('.at-url input').forEach(i => { i.value = `${i.dataset.base}?chave=${d.chave}`; });
            toast(_t('Chave trocada. Atualize os endereços nos botões.'));
        } catch (e) {
            toast(_t('Não deu pra trocar a chave.'), 'error');
        }
    });
})();
