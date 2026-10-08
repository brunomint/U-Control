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
        'z-index:9999;display:none;align-items:center;gap:12px;background:var(--uc-surface-3,#262c44);' +
        'border:1px solid var(--uc-warn,#f2b84b);border-radius:10px;padding:10px 16px;' +
        'box-shadow:0 12px 30px rgba(0,0,0,.45);font-family:inherit;color:var(--uc-text,#e9ebf4);';
    el.innerHTML =
        '<span style="width:8px;height:8px;border-radius:50%;background:var(--uc-warn,#f2b84b);flex:none;"></span>' +
        '<span id="release-banner-label" style="font-size:.9rem;max-width:40vw;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;"></span>' +
        '<button id="release-banner-btn" style="background:var(--uc-live,#f04b55);color:#fff;border:none;' +
            'border-radius:6px;padding:6px 14px;font-weight:700;cursor:pointer;font:inherit;font-weight:700;">Liberar no telão</button>' +
        '<button id="release-banner-discard" style="background:transparent;color:var(--uc-muted,#9198b3);' +
            'border:1px solid var(--uc-line,#2a3050);border-radius:6px;padding:6px 10px;cursor:pointer;" ' +
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
