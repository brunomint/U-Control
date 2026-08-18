// Banner "Liberar" embutido nas páginas de origem (letra/bíblia/foto) —
// pra quem está operando não precisar abrir o /control só pra liberar o
// que acabou de preparar (confusão real reportada: a seção não aparece
// em lugar nenhum até alguém liberar, e a pessoa que está clicando na
// letra normalmente não é quem está no /control). Mantém a segurança do
// "preparar vs liberar" — só libera com uma ação explícita, ainda exige
// clicar em algo — só tira a necessidade de trocar de aba/janela pra
// isso. Auto-contido (injeta seu próprio HTML/CSS) pra não precisar
// editar o template/CSS de cada página que usa.
function initReleaseBanner(socket, kind) {
    const el = document.createElement('div');
    el.id = 'release-banner';
    el.style.cssText = 'position:fixed;left:50%;bottom:24px;transform:translateX(-50%);' +
        'z-index:9999;display:none;align-items:center;gap:12px;background:#1e1e2e;' +
        'border:1px solid #f59e0b;border-radius:10px;padding:10px 16px;' +
        'box-shadow:0 4px 16px rgba(0,0,0,.4);font-family:inherit;color:#fff;';
    el.innerHTML =
        '<span style="font-size:1.1rem;">🔔</span>' +
        '<span id="release-banner-label" style="font-size:.9rem;max-width:40vw;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;"></span>' +
        '<button id="release-banner-btn" style="background:#f59e0b;color:#1e1e2e;border:none;' +
            'border-radius:6px;padding:6px 14px;font-weight:600;cursor:pointer;">Liberar</button>' +
        '<button id="release-banner-discard" style="background:transparent;color:#94a3b8;' +
            'border:1px solid #475569;border-radius:6px;padding:6px 10px;cursor:pointer;" ' +
            'title="Descartar sem exibir">✕</button>';
    document.body.appendChild(el);

    const labelEl = el.querySelector('#release-banner-label');

    function show(label) {
        labelEl.textContent = label || 'Preparado';
        el.style.display = 'flex';
    }
    function hide() {
        el.style.display = 'none';
    }

    el.querySelector('#release-banner-btn').onclick = () => socket.emit('release_staged_content', { kind });
    el.querySelector('#release-banner-discard').onclick = () => socket.emit('discard_staged_content', { kind });

    socket.on('content_staged', (data) => {
        if (data.kind === kind) show(data.label);
    });
    socket.on('content_released', (data) => {
        if (data.kind === kind) hide();
    });
    socket.on('content_discarded', (data) => {
        if (data.kind === kind) hide();
    });

    // Recupera estado já preparado ao abrir a página (ex: outra pessoa
    // preparou antes desta página abrir) — mesmo endpoint que /control usa.
    fetch('/api/staged-content')
        .then(r => r.json())
        .then(data => {
            if (data[kind]) show(data[kind].label);
        })
        .catch(() => {});
}
