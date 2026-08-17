const socket = io();
const CONFIG = JSON.parse(document.getElementById('bible-chapter-data').textContent);
const bookName = CONFIG.bookName;
const chapter = CONFIG.chapter;
const bookAbbrev = CONFIG.bookAbbrev;
let selectedVerses = [];

function toggleVerse(element) {
    const verseNum = parseInt(element.dataset.verse);
    const index = selectedVerses.findIndex(v => v.num === verseNum);

    if (index > -1) {
        selectedVerses.splice(index, 1);
        element.classList.remove('selected');
    } else {
        const text = element.querySelector('.verse-text').textContent;
        selectedVerses.push({ num: verseNum, text: text });
        selectedVerses.sort((a, b) => a.num - b.num);
        element.classList.add('selected');
    }

    updateActionBar();
}

function updateActionBar() {
    const actionBar = document.getElementById('actionBar');
    const countSpan = document.getElementById('selectedCount');

    if (selectedVerses.length > 0) {
        actionBar.classList.add('active');
        countSpan.textContent = selectedVerses.length;
    } else {
        actionBar.classList.remove('active');
    }
}

function clearSelection() {
    selectedVerses = [];
    document.querySelectorAll('.verse.selected').forEach(el => {
        el.classList.remove('selected');
    });
    updateActionBar();
}

function getReference() {
    if (selectedVerses.length === 0) return '';

    const nums = selectedVerses.map(v => v.num);
    const min = Math.min(...nums);
    const max = Math.max(...nums);

    if (min === max) {
        return `${bookName} ${chapter}:${min}`;
    } else {
        return `${bookName} ${chapter}:${min}-${max}`;
    }
}

// "Preparar vs. liberar": stage_content em vez de update_bible direto —
// a mudança de verdade só acontece quando o /control liberar (ver
// blueprints/display.py: stage_content/release_staged_content).
function sendToDisplay() {
    if (selectedVerses.length === 0) return;

    const reference = getReference();
    const text = selectedVerses.map(v => `${v.num} ${v.text}`).join('\n');

    socket.emit('stage_content', {
        kind: 'bible',
        payload: {
            reference: reference,
            text: text,
            book: bookName,
            chapter: chapter,
            verses: selectedVerses,
            version: CONFIG.translationName
        },
        label: reference
    });

    showToast('Preparado — libere no /control pra ir ao ar!');
}

function sendSingleVerse(verseNum, text) {
    const reference = `${bookName} ${chapter}:${verseNum}`;

    socket.emit('stage_content', {
        kind: 'bible',
        payload: {
            reference: reference,
            text: `${verseNum} ${text}`,
            book: bookName,
            chapter: chapter,
            verses: [{ num: verseNum, text: text }],
            version: CONFIG.translationName
        },
        label: reference
    });

    showToast(`${reference} preparado — libere no /control!`);
}

function copyVerses() {
    if (selectedVerses.length === 0) return;

    const reference = getReference();
    const text = selectedVerses.map(v => `${v.num} ${v.text}`).join('\n');
    const fullText = `${reference}\n\n${text}`;

    navigator.clipboard.writeText(fullText).then(() => {
        showToast('Versículos copiados!');
    });
}

function showToast(message) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.classList.add('show');
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
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

    window.location.href = `/bible/${bookAbbrev}/${chapter}?translation=${translation}`;
}

function goToChapter() {
    const chapterNum = document.getElementById('chapterSelect').value;
    const translation = document.getElementById('translationSelect').value;
    window.location.href = `/bible/${bookAbbrev}/${chapterNum}?translation=${translation}`;
}

// Scroll para versículo se houver hash na URL
window.addEventListener('load', function() {
    const hash = window.location.hash;
    if (hash && hash.startsWith('#verse-')) {
        const element = document.querySelector(hash);
        if (element) {
            element.scrollIntoView({ behavior: 'smooth', block: 'center' });
            element.style.animation = 'highlight 2s';
        }
    }
});
