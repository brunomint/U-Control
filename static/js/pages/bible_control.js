const socket = io();
const CONFIG = JSON.parse(document.getElementById('bible-control-data').textContent);
const bookName = CONFIG.bookName;
const bookAbbrev = CONFIG.bookAbbrev;
const chapter = CONFIG.chapter;
const totalVerses = CONFIG.verses.length;
let currentVerse = 1;
// Estado real (LyricsState.visible), não mais assumido true a cada
// carregamento — mesma fonte única de verdade que /lyrics/<id> usa,
// já que as duas páginas mandam pro mesmo lugar (tela pública).
let isVisible = CONFIG.lyricsVisible !== false;

// Dados dos versículos
const versesData = CONFIG.verses.map((text, i) => ({ num: i + 1, text: text }));

// silent=true: só atualiza a visualização LOCAL (verso ativo destacado,
// scroll) sem preparar nada — usado só pelo restauro do verso inicial ao
// carregar a página (window.addEventListener('load', ...) mais abaixo).
// Antes disso mandava update_bible direto toda vez que a página abria,
// mesmo sem clique nenhum (mesma classe de bug já corrigida em
// lyrics_2.js/loadLyricsState — 2026-08-16): abrir a página sozinha
// (ex: adiantando a leitura da semana seguinte) sobrescrevia
// silenciosamente o que outro operador tivesse preparado em outra tela.
function selectVerse(verseNum, silent = false) {
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

    if (!silent) sendToDisplay();
}

// "Preparar vs. liberar": stage_content em vez de update_bible direto —
// a mudança de verdade só acontece quando o /control liberar (ver
// blueprints/display.py: stage_content/release_staged_content).
function sendToDisplay() {
    const verse = versesData[currentVerse - 1];
    const reference = `${bookName} ${chapter}:${currentVerse}`;

    socket.emit('stage_content', {
        kind: 'bible',
        payload: {
            reference: reference,
            text: `${verse.num} ${verse.text}`,
            book: bookName,
            chapter: chapter,
            verses: [verse],
            version: CONFIG.translationName
        },
        label: reference
    });

    console.log(`📖 Preparado: ${reference}`);
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

// Usa o mesmo evento toggle_lyrics_visibility que /lyrics/<id> usa (ver
// lyrics_2.js/toggleLyricsVisibility) — antes esta função "escondia"
// mandando update_bible com texto vazio, um mecanismo próprio e
// desconectado do resto do app: não persistia nada (recarregar a página
// sempre assumia visível de novo, mesmo bug já corrigido em /lyrics), e
// não sabia nada sobre o botão da outra página — cada um podia mostrar
// um estado diferente do que a tela pública realmente tinha. Escondida,
// o conteúdo continua ali por baixo (só a exibição CSS muda no
// display_public.js), não precisa reenviar nada ao mostrar de novo.
function toggleVisibility() {
    isVisible = !isVisible;
    socket.emit('toggle_lyrics_visibility', { visible: isVisible });
    aplicarBotaoVisibilidade();
}

// Escondido/mostrado por outra página (música), ou mostrado de novo
// sozinho quando algo novo foi ao ar — o botão acompanha
socket.on('lyrics_visibility_changed', (data) => {
    isVisible = data.visible !== false;
    aplicarBotaoVisibilidade();
});

function aplicarBotaoVisibilidade() {
    const btn = document.getElementById('toggle-bible');
    const text = document.getElementById('toggle-text');
    const icon = btn.querySelector('i');

    if (isVisible) {
        btn.classList.remove('show-mode');
        text.textContent = _t('Esconder');
        icon.className = 'fas fa-eye';
    } else {
        btn.classList.add('show-mode');
        text.textContent = _t('Mostrar');
        icon.className = 'fas fa-eye-slash';
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
        alert(_t('Digite uma referência bíblica'));
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
            alert(data.error || _t('Erro ao adicionar passagem'));
        }
    } catch (error) {
        console.error('Erro:', error);
        alert(_t('Erro ao adicionar passagem'));
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
    if (!confirm(_t('Remover "{ref}"?', { ref: reference }))) {
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
            alert(data.error || _t('Erro ao remover'));
        }
    } catch (error) {
        console.error('Erro:', error);
        alert(_t('Erro ao remover'));
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

// Seleciona o versículo inicial ao carregar — silent=true, só restaura a
// visualização local, não prepara/manda nada (ver comentário em selectVerse).
window.addEventListener('load', function() {
    selectVerse(CONFIG.initialVerse, true);
});
