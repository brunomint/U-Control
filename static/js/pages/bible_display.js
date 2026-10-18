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
        version.textContent = data.version || '';

        // Formata versículos
        let html = '';
        if (data.verses && Array.isArray(data.verses)) {
            data.verses.forEach(verse => {
                html += `<span class="verse-number">${verse.num}</span>${verse.text} `;
            });
        } else if (data.text) {
            html = data.text;
        }

        verseText.innerHTML = html;

        // Ajusta tamanho do texto baseado no comprimento
        const textLength = verseText.textContent.length;
        verseText.classList.remove('small', 'medium', 'large');
        if (textLength > 500) {
            verseText.classList.add('small');
        } else if (textLength > 200) {
            verseText.classList.add('medium');
        } else {
            verseText.classList.add('large');
        }

        // Mostra conteúdo
        waiting.style.display = 'none';
        content.style.display = 'block';
        content.classList.remove('fade-out');
        caberNaTela();
    }, 300);
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
