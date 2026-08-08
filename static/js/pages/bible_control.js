const socket = io();
const CONFIG = JSON.parse(document.getElementById('bible-control-data').textContent);
const bookName = CONFIG.bookName;
const bookAbbrev = CONFIG.bookAbbrev;
const chapter = CONFIG.chapter;
const totalVerses = CONFIG.verses.length;
let currentVerse = 1;
let isVisible = true;

// Dados dos versículos
const versesData = CONFIG.verses.map((text, i) => ({ num: i + 1, text: text }));

function selectVerse(verseNum) {
    currentVerse = verseNum;

    // Remove active de todos
    document.querySelectorAll('.verse-item').forEach(el => {
        el.classList.remove('active');
    });

    // Adiciona active ao selecionado
    const verseEl = document.getElementById(`verse-${verseNum}`);
    if (verseEl) {
        verseEl.classList.add('active');
        verseEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    // Envia para o display
    sendToDisplay();
}

function sendToDisplay() {
    const verse = versesData[currentVerse - 1];
    const reference = `${bookName} ${chapter}:${currentVerse}`;

    socket.emit('update_bible', {
        reference: reference,
        text: `${verse.num} ${verse.text}`,
        book: bookName,
        chapter: chapter,
        verses: [verse]
    });

    console.log(`📖 Enviado: ${reference}`);
}

function prevVerse() {
    if (currentVerse > 1) {
        selectVerse(currentVerse - 1);
    }
}

function nextVerse() {
    if (currentVerse < totalVerses) {
        selectVerse(currentVerse + 1);
    }
}

function toggleVisibility() {
    isVisible = !isVisible;
    const btn = document.getElementById('toggle-bible');
    const text = document.getElementById('toggle-text');
    const icon = btn.querySelector('i');

    if (isVisible) {
        btn.classList.remove('show-mode');
        text.textContent = 'Esconder';
        icon.className = 'fas fa-eye';
        sendToDisplay();
    } else {
        btn.classList.add('show-mode');
        text.textContent = 'Mostrar';
        icon.className = 'fas fa-eye-slash';

        // Envia texto vazio para esconder
        socket.emit('update_bible', {
            reference: '',
            text: '',
            verses: []
        });
    }
}

async function changeTranslation() {
    const translation = document.getElementById('translationSelect').value;

    // Salva a tradução preferida no servidor
    try {
        await fetch('/api/bible/set_translation', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ translation: translation })
        });
    } catch (error) {
        console.error('Erro ao salvar tradução:', error);
    }

    window.location.href = `/bible/control/${bookAbbrev}/${chapter}?translation=${translation}`;
}

function goToChapter() {
    const chapterNum = document.getElementById('chapterSelect').value;
    const translation = document.getElementById('translationSelect').value;
    window.location.href = `/bible/control/${bookAbbrev}/${chapterNum}?translation=${translation}`;
}

// Toggle menu
function toggleMenu() {
    document.getElementById('menu').classList.toggle('active');
}

// Adicionar passagem do menu
async function addBibleFromMenu() {
    const input = document.getElementById('menuBibleRef');
    const reference = input.value.trim();

    if (!reference) {
        alert('Digite uma referência bíblica');
        return;
    }

    try {
        const response = await fetch('/api/bible/add_to_order', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reference: reference })
        });

        const data = await response.json();

        if (data.success) {
            if (data.message) alert(data.message);
            window.location.reload();
        } else {
            alert(data.error || 'Erro ao adicionar passagem');
        }
    } catch (error) {
        console.error('Erro:', error);
        alert('Erro ao adicionar passagem');
    }
}

// Enter para adicionar no menu
document.getElementById('menuBibleRef').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        addBibleFromMenu();
    }
});

// Remover passagem do menu
async function removeBibleFromMenu(reference) {
    if (!confirm(`Remover "${reference}"?`)) {
        return;
    }

    try {
        const response = await fetch('/api/bible/remove_from_order', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reference: reference })
        });

        const data = await response.json();

        if (data.success) {
            window.location.reload();
        } else {
            alert(data.error || 'Erro ao remover');
        }
    } catch (error) {
        console.error('Erro:', error);
        alert('Erro ao remover');
    }
}

// Keyboard navigation
document.addEventListener('keydown', function(e) {
    // Ignora atalhos quando está digitando em um input
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
        return;
    }

    if (e.key === 'ArrowUp' || e.key === 'ArrowLeft') {
        e.preventDefault();
        prevVerse();
    } else if (e.key === 'ArrowDown' || e.key === 'ArrowRight') {
        e.preventDefault();
        nextVerse();
    } else if (e.key === ' ') {
        e.preventDefault();
        toggleVisibility();
    } else if (e.key === 'Escape') {
        document.getElementById('menu').classList.remove('active');
    }
});

// Seleciona o versículo inicial ao carregar
window.addEventListener('load', function() {
    selectVerse(CONFIG.initialVerse);
});
