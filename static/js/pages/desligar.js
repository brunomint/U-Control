// Página /desligar (ver blueprints/desligar.py)
document.getElementById('desligar-btn').addEventListener('click', async function () {
    this.disabled = true;
    const texto = document.getElementById('desligar-texto');
    try {
        const r = await fetch('/api/desligar', { method: 'POST' });
        const d = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(d.error || `erro ${r.status}`);
        document.querySelector('.uc-btn-row').hidden = true;
        texto.innerHTML = '<strong>U-Control desligado.</strong> Pode fechar esta janela.';
    } catch (e) {
        texto.textContent = 'Não deu pra desligar: ' + e.message;
        this.disabled = false;
    }
});
