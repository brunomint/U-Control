const socket = io();
const CONFIG = JSON.parse(document.getElementById('bible-chapter-data').textContent);
const bookName = CONFIG.bookName;
const chapter = CONFIG.chapter;
const bookAbbrev = CONFIG.bookAbbrev;
let selectedVerses = [];

// Toque num versículo exibe ele (como as setas). Pra vários juntos (ex.:
// 16 a 18), o botão "Vários versículos" troca o toque por escolher, e a
// barra de baixo aparece com "Exibir juntos"/"Copiar".
let modoVarios = false;

function onVerseTap(element) {
    if (modoVarios) toggleVerse(element);
    else sendSingleVerse(parseInt(element.dataset.verse, 10), undefined, true);
}

function toggleModoVarios() {
    modoVarios = !modoVarios;
    const btn = document.getElementById('multiBtn');
    btn.setAttribute('aria-pressed', String(modoVarios));
    btn.classList.toggle('active', modoVarios);
    document.querySelector('.verses-container').classList.toggle('modo-varios', modoVarios);
    if (!modoVarios) clearSelection();
}

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
        // Versículo clicado vira o ponto de partida das setas: ↓ manda o
        // seguinte a ele (ver passarVerso)
        versoAtual = verseNum;
        avisoBorda = null;
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

    showToast('Preparado. Se o telão pedir, toque em “Liberar”.');
    toggleModoVarios();   // volta pro toque = exibir
}

function sendSingleVerse(verseNum, text, silencioso) {
    // O texto vem da página: passado inline no onclick, um apóstrofo no
    // versículo quebrava a string JS.
    if (text === undefined) {
        const el = document.getElementById(`verse-${verseNum}`);
        text = el ? el.querySelector('.verse-text').textContent : '';
    }
    const reference = `${bookName} ${chapter}:${verseNum}`;
    marcarAtual(verseNum);

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

    // Pelas setas não avisa: com "Bíblia entra direto" já foi ao ar, e
    // senão a barra do telão já mostra "Preparado · Liberar"
    if (!silencioso) showToast(`${reference} preparado. Toque em “Liberar no telão” para exibir.`);
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
    window.ucToast(message);
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

// ── Setas do teclado (e pedal) passam os versículos ───────────────────
// ↓ → PageDown: próximo versículo · ↑ ← PageUp: anterior. Cada um vai pro
// telão como o botão ▶ do versículo (preparar, ou direto se "Bíblia entra
// direto" estiver ligado). No fim do capítulo, apertar de novo abre o
// próximo capítulo já no versículo 1 (e no começo, o anterior no último).
const totalVersos = document.querySelectorAll('.verse[data-verse]').length;
let versoAtual = null;
let avisoBorda = null;   // 'fim' | 'inicio' depois do 1º aperto na borda

function marcarAtual(n) {
    versoAtual = n;
    avisoBorda = null;
    document.querySelectorAll('.verse.atual').forEach(el => el.classList.remove('atual'));
    const el = document.getElementById(`verse-${n}`);
    if (el) {
        el.classList.add('atual');
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
}

function irCapitulo(cap, verso) {
    window.location.href = `/bible/${bookAbbrev}/${cap}?translation=${CONFIG.translation}&verso=${verso}`;
}

function passarVerso(passo) {
    if (!totalVersos) return;
    if (versoAtual === null) return sendSingleVerse(passo > 0 ? 1 : totalVersos, undefined, true);
    const alvo = versoAtual + passo;
    if (alvo >= 1 && alvo <= totalVersos) return sendSingleVerse(alvo, undefined, true);
    const borda = passo > 0 ? 'fim' : 'inicio';
    const cap = passo > 0 ? CONFIG.nextChapter : CONFIG.prevChapter;
    if (!cap) return showToast(passo > 0 ? `Fim de ${bookName}.` : `Início de ${bookName}.`);
    if (avisoBorda === borda) return irCapitulo(cap, passo > 0 ? 1 : 'fim');
    avisoBorda = borda;
    showToast(passo > 0 ? `Fim do capítulo ${chapter}. Aperte de novo para ir ao ${cap}.`
                        : `Início do capítulo. Aperte de novo para voltar ao ${cap}.`);
}

document.addEventListener('keydown', e => {
    if (e.target.closest('input, textarea, select, [contenteditable="true"]')) return;
    if (['ArrowDown', 'ArrowRight', 'PageDown'].includes(e.key)) {
        e.preventDefault();
        passarVerso(1);
    } else if (['ArrowUp', 'ArrowLeft', 'PageUp'].includes(e.key)) {
        e.preventDefault();
        passarVerso(-1);
    }
});

// Veio das setas de outro capítulo (?verso=1 ou ?verso=fim): já manda
window.addEventListener('load', () => {
    const verso = new URLSearchParams(location.search).get('verso');
    if (verso && totalVersos) sendSingleVerse(verso === 'fim' ? totalVersos : Math.min(parseInt(verso, 10) || 1, totalVersos), undefined, true);
});
