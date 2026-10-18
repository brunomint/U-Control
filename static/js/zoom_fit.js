// Zoom do /presenter nas telas (tela pública, /monitor, /img) — foto em
// "object-fit: contain", transformação translate(pan%) scale(zoom) com
// origem no centro, igual à prévia do modal de zoom.
//
// O presenter limita o arraste pras bordas da foto num quadro 16:9; uma
// tela com outra proporção (monitor de palco, TV, navegador fora de tela
// cheia) mostrava preto além da borda. Aqui cada tela refaz esse limite
// com o PRÓPRIO tamanho: num 16:9 fica idêntico à prévia, nos outros o
// mais perto possível sem preto. Reaplica se a janela mudar de tamanho.
(function () {
    const lastZoom = new WeakMap();

    function apply(img, data) {
        lastZoom.set(img, data);
        const zoom = parseFloat(data.zoom) || 1;
        const pan = data.pan || { x: 0, y: 0 };
        let x = pan.x || 0;
        let y = pan.y || 0;
        const nW = img.naturalWidth, nH = img.naturalHeight;
        const eW = img.offsetWidth, eH = img.offsetHeight;
        if (nW && nH && eW && eH) {
            // Tamanho da foto dentro do elemento, em % dele ("contain")
            const ar = nW / nH, boxAr = eW / eH;
            const fw = ar > boxAr ? 100 : 100 * ar / boxAr;
            const fh = ar > boxAr ? 100 * boxAr / ar : 100;
            const maxX = Math.max(0, (zoom * fw - 100) / 2);
            const maxY = Math.max(0, (zoom * fh - 100) / 2);
            x = Math.max(-maxX, Math.min(maxX, x));
            y = Math.max(-maxY, Math.min(maxY, y));
        }
        img.style.transformOrigin = '50% 50%';
        img.style.transform = `translate(${x}%, ${y}%) scale(${zoom})`;
    }

    window.ucApplyZoom = apply;

    // Tela abriu/recarregou ou recebeu a mesma foto de novo: pergunta ao
    // servidor se ela está com zoom e reaplica (antes o zoom se perdia).
    // Espera a foto carregar — o limite do arraste usa o tamanho dela.
    const semQuery = (u) => (u || '').split('?')[0];
    function restore(img, url) {
        if (!img || !url) return;
        fetch('/api/image-zoom')
            .then((r) => (r.ok ? r.json() : null))
            .then((z) => {
                if (!z || !z.image_url || semQuery(z.image_url) !== semQuery(url)) return;
                const vai = () => { if (semQuery(img.getAttribute('src')) === semQuery(url)) apply(img, z); };
                if (img.complete && img.naturalWidth) vai();
                else img.addEventListener('load', vai, { once: true });
            })
            .catch(() => {});
    }
    window.ucRestoreZoom = restore;
    window.addEventListener('resize', () => {
        document.querySelectorAll('img').forEach((img) => {
            const data = lastZoom.get(img);
            if (data && img.style.transform) apply(img, data);
        });
    });
})();
