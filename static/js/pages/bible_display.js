const socket = io();

let shownOnce = false;
// Botão Esconder/Mostrar (das páginas de música e da Bíblia): o mesmo
// evento que a tela pública usa — antes esta tela esperava um
// "bible_visibility_changed" que ninguém manda, e nunca escondia
let escondido = false;

function aplicarEscondido() {
    ['content', 'waiting'].forEach(id => {
        document.getElementById(id).style.visibility = escondido ? 'hidden' : '';
    });
}

// Ao abrir (ou reconectar) mostra o versículo que já está no telão — a
// página só recebia versículos NOVOS, então aberta depois do envio (prévia
// do /control, monitor, tela recarregada) ficava em "Aguardando versículos..."
socket.on('connect', function() {
    console.log('📖 Conectado ao servidor de Bíblia');
    // Dentro do /monitor (host=monitor): é o monitor — em "Só público" não
    // muda junto com o telão (ver noMonitor em monitor.js)
    if (new URLSearchParams(location.search).get('host') === 'monitor') socket.emit('identify', { role: 'monitor' });
    fetch('/api/lyrics/visible')
        .then(r => (r.ok ? r.json() : null))
        .then(d => { if (d) { escondido = d.visible === false; aplicarEscondido(); } })
        .catch(() => {});
    if (shownOnce) return;
    // No monitor: o versículo liberado pra ele (pode ser outro que o do público)
    fetch('/api/bible/current' + (new URLSearchParams(location.search).get('host') === 'monitor' ? '?host=monitor' : ''))
        .then(r => (r.ok ? r.json() : null))
        .then(data => {
            if (!shownOnce && data && (data.reference || data.text)) displayVerse(data);
        })
        .catch(() => {});
});

socket.on('update_bible', function(data) {
    console.log('📖 Recebido:', data);
    displayVerse(data);
});

function displayVerse(data) {
    shownOnce = true;
    const waiting = document.getElementById('waiting');
    const content = document.getElementById('content');
    const reference = document.getElementById('reference');
    const verseText = document.getElementById('verseText');
    const version = document.getElementById('verseVersion');

    // Fade out
    content.classList.add('fade-out');

    setTimeout(() => {
        // Atualiza conteúdo
        reference.textContent = data.reference || '';
        const duas = Array.isArray(data.verses2) && data.verses2.length > 0;
        version.textContent = duas ? [data.version, data.version2].filter(Boolean).join(' · ') : (data.version || '');

        verseText.innerHTML = versosHtml(data.verses, data.text);
        // Segunda versão embaixo, cada uma com a sigla
        document.getElementById('verseBox2').hidden = !duas;
        document.getElementById('verseSigla').hidden = !duas;
        document.getElementById('verseSigla').textContent = data.version_abbrev || '';
        document.getElementById('verseSigla2').textContent = data.version2_abbrev || '';
        const verseText2 = document.getElementById('verseText2');
        verseText2.innerHTML = duas ? versosHtml(data.verses2, data.text2) : '';

        // Ajusta tamanho do texto baseado no comprimento (as duas somadas)
        const textLength = verseText.textContent.length + verseText2.textContent.length;
        [verseText, verseText2].forEach(el => {
            el.classList.remove('small', 'medium', 'large');
            el.classList.add(textLength > 500 ? 'small' : textLength > 200 ? 'medium' : 'large');
        });

        // Mostra conteúdo
        waiting.style.display = 'none';
        content.style.display = 'block';
        content.classList.remove('fade-out');
        caberNaTela();
    }, 300);
}

function versosHtml(verses, text) {
    const esc = t => String(t == null ? '' : t).replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' })[c]);
    if (Array.isArray(verses)) {
        return verses.map(v => `<span class="verse-number">${esc(v.num)}</span>${esc(v.text)} `).join('');
    }
    return text ? esc(text) : '';
}

// Texto longo (vários versículos, tela baixa como o celular deitado no
// app) passava da borda de baixo: diminui tudo junto (referência, texto,
// versão e espaçamentos estão em "em") até caber na altura da tela —
// mesma ideia do ajuste da letra (display.js/display_public.js).
function caberNaTela() {
    const content = document.getElementById('content');
    if (!content || content.style.display === 'none') return;
    const cs = getComputedStyle(document.body);
    const altura = window.innerHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom);
    const largura = window.innerWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
    let tam = 16;                                   // tamanho normal (o do CSS)
    content.style.fontSize = tam + 'px';
    while ((content.scrollHeight > altura || content.scrollWidth > largura) && tam > 5) {
        tam -= 0.5;
        content.style.fontSize = tam + 'px';
    }
}
window.addEventListener('resize', caberNaTela);
// A fonte (Merriweather) chegando depois muda o tamanho do texto
if (document.fonts && document.fonts.ready) document.fonts.ready.then(caberNaTela);

socket.on('lyrics_visibility_changed', function(data) {
    escondido = data.visible === false;
    aplicarEscondido();
});
