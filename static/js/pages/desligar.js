// Página /desligar (ver blueprints/desligar.py)
document.getElementById('desligar-btn').addEventListener('click', async function () {
    this.disabled = true;
    const texto = document.getElementById('desligar-texto');
    try {
        const r = await fetch('/api/desligar', { method: 'POST' });
        const d = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(d.error || _t('erro {status}', { status: r.status }));
        document.querySelector('.uc-btn-row').hidden = true;
        texto.innerHTML = _t('<strong>U-Control desligado.</strong> Pode fechar esta janela.');
    } catch (e) {
        texto.textContent = _t('Não deu pra desligar: {erro}', { erro: e.message });
        this.disabled = false;
    }
});
