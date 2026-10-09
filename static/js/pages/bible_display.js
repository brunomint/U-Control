const socket = io();

let shownOnce = false;

// Ao abrir (ou reconectar) mostra o versículo que já está no telão — a
// página só recebia versículos NOVOS, então aberta depois do envio (prévia
// do /control, monitor, tela recarregada) ficava em "Aguardando versículos..."
socket.on('connect', function() {
    console.log('📖 Conectado ao servidor de Bíblia');
    if (shownOnce) return;
    fetch('/api/bible/current')
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
    }, 300);
}

// Escuta também eventos de visibilidade (para esconder/mostrar)
socket.on('bible_visibility_changed', function(data) {
    const content = document.getElementById('content');
    const waiting = document.getElementById('waiting');

    if (data.visible) {
        content.style.display = 'block';
    } else {
        content.style.display = 'none';
        waiting.style.display = 'block';
    }
});
