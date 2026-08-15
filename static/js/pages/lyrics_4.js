            let draggedElement = null; // Variável para armazenar o elemento arrastado

// Função de busca de músicas
async function searchSongs(query) {
    if (!query) {
        document.getElementById("autocompleteList").innerHTML = ""; // Limpa a lista
        return;
    }

    try {
        const response = await fetch(`/search?q=${encodeURIComponent(query)}`);
        const songs = await response.json();

        const list = document.getElementById("autocompleteList");
        list.innerHTML = ""; // Limpa resultados anteriores

        if (songs.length === 0) {
            const noResult = document.createElement("div");
            noResult.className = "autocomplete-item";
            noResult.textContent = "Nenhum resultado encontrado";
            list.appendChild(noResult);
            return;
        }

        songs.forEach(song => {
            const item = document.createElement("div");
            item.className = "autocomplete-item";
            item.textContent = `${song.title} | ${song.author}`;
            item.onclick = () => {
                console.log("Dentro do updateSongList:", JSON.stringify(song));
                selectSong(song);
                updateSongList(song);
            };
            list.appendChild(item);
        });
    } catch (error) {
        console.error("Erro ao buscar músicas:", error);
    }
}

// Função para selecionar uma música
function selectSong(song) {
    document.getElementById("searchInput").value = "";
    document.getElementById("autocompleteList").innerHTML = "";
}

// Função para adicionar música na lista
function updateSongList(song) {
    console.log("Dentro do updateSongList:", song);
    const songList = document.getElementById("songList");

    const songItem = document.createElement("div");
    songItem.className = "song-item";
    songItem.setAttribute("draggable", "true");
    songItem.id = `song-${Date.now()}`; // Atribui um ID único ao item

    const displayText = song.author ? `${song.title} | ${song.author}` : song.title;

    // Verifica se a música tem URL ou usa fallback
    const songLink = document.createElement("a");
    const baseHref = song.url || (song.id ? `/lyrics/${song.id}` : "#");
    // Propaga a data da ordem na URL para manter a lista consistente entre páginas
    if (song.orderDate && baseHref !== '#' && baseHref.startsWith('/lyrics/')) {
        songLink.href = `${baseHref}?order=${song.orderDate}`;
    } else {
        songLink.href = baseHref;
    }
    songLink.textContent = song.author ? `${song.title} | ${song.author}` : song.title || "Título Desconhecido";

    // Item bíblico: clicar manda ao vivo (sendBibleListItem) em vez de
    // navegar pra /bible/control/... — busca e edição continuam por lá,
    // mas usar a passagem durante o culto acontece sem sair do /lyrics.
    if (song.isBible) {
        const reference = song.bibleReference || song.title.replace(/^📖\s*/, '');
        songLink.onclick = (event) => {
            event.preventDefault();
            sendBibleListItem(reference, songItem);
        };
    }

   
   
   
   
   
   
   
    // songLink.target = "_blank"; // Abre o link em uma nova aba
   // songLink.style.textDecoration = "none";//
   // songLink.style.color = "";//
   songLink.classList.add("song-link");








    // Marca a música atual na lista
    const currentPath = `/lyrics/${songId}`;
    const linkPath = new URL(songLink.href, window.location.origin).pathname;
    if (linkPath === currentPath) {
        songItem.classList.add('current-song');
    }

    // Adiciona o link ao item da música
    songItem.appendChild(songLink);

    // Botão para remover a música
    const removeButton = document.createElement("button");
    removeButton.className = "remove-btn";
    removeButton.textContent = "🗑️";
    removeButton.onclick = () => songList.removeChild(songItem);

    // Adiciona o botão ao item da música
    songItem.appendChild(removeButton);

    // Função de arrastar
    songItem.ondragstart = (event) => {
        draggedElement = songItem; // Atualiza a variável com o elemento arrastado
        event.dataTransfer.effectAllowed = "move";
    };

    // Adiciona o item à lista de músicas
    songList.appendChild(songItem);
}

// Função para permitir o drop
function allowDrop(ev) {
    ev.preventDefault();
}

// Função para lidar com o drop
function drop(ev) {
    ev.preventDefault();
    if (ev.target.className === "song-item" && draggedElement) {
        const target = ev.target;
        const songList = document.getElementById("songList");
        const allItems = Array.from(songList.children);
        const draggedIndex = allItems.indexOf(draggedElement);
        const targetIndex = allItems.indexOf(target);

        if (draggedIndex < targetIndex) {
            songList.insertBefore(draggedElement, target.nextSibling);
        } else {
            songList.insertBefore(draggedElement, target);
        }
    }
}

// Função para adicionar texto à lista
function addToList() {
    const freeTextInput = document.getElementById("freeTextInput");
    const textValue = freeTextInput.value.trim(); // Obtém o texto digitado, sem espaços extras

    if (textValue === "") {
        alert("Por favor, digite algum texto.");
        return;
    }

    // Criar um objeto "música" com o texto inserido (sem autor e preço)
    const song = {
        title: textValue, // Apenas o título será adicionado
    };

    // Atualizar a lista de músicas com o novo item
    updateSongList(song);

    // Limpar o campo de texto
    freeTextInput.value = "";
}


async function saveList() {
    const songList = document.getElementById("songList");
    const items = Array.from(songList.children);

    const data = items.map(item => {
        const link = item.querySelector("a");
        const title = link ? link.textContent : null;
        let url = link ? link.href : null;

        // Extrai apenas o caminho final da URL
        if (url) {
            const urlObject = new URL(url, window.location.origin);
            url = urlObject.pathname; // Obtém somente o caminho (exemplo: /lyrics/18)
        }

        return url ? { url, title } : { anyText: title };
    });

    try {
        // Verifica se há data na URL para salvar na ordem correta
        let orderDate = CONFIG.orderDate;
        if (!orderDate) {
            const urlParams = new URLSearchParams(window.location.search);
            orderDate = urlParams.get('order');
        }
        
        if (orderDate) {
            // Salva na ordem específica por data
            await fetch(`/api/orders/${orderDate}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ itens: data }),
            });
        } else {
            // Fallback para sistema antigo
            await fetch('/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });
        }
        alert("Lista salva com sucesso!");
    } catch (error) {
        console.error("Erro ao salvar a lista:", error);
        alert("Erro ao salvar a lista.");
    }
}

// ── Busca rápida de Bíblia — busca e envia pro display sem sair da página,
// reusando a mesma API (/api/bible/search) e o mesmo evento socket
// (update_bible) que a página /bible já usa pra mandar versículo. ──
let bibleSearchTimeout = null;

async function searchBibleQuick(query) {
    const list = document.getElementById("bibleAutocompleteList");
    if (!query || query.trim().length < 3) {
        list.innerHTML = "";
        return;
    }

    try {
        const response = await fetch(`/api/bible/search?q=${encodeURIComponent(query)}`);
        const data = await response.json();
        list.innerHTML = "";

        if (data.error || !data.results || data.results.length === 0) {
            const noResult = document.createElement("div");
            noResult.className = "autocomplete-item";
            noResult.textContent = data.error || "Nenhum resultado encontrado";
            list.appendChild(noResult);
            return;
        }

        // Busca reconhecida como referência (intervalo tipo "Salmos 2:1-7"
        // ou capítulo inteiro) com mais de um verso — oferece adicionar
        // tudo de uma vez como UM item na lista, em vez de obrigar a
        // clicar verso por verso (cada clique fechava a lista de
        // resultados, tinha que buscar de novo pra pegar o próximo).
        if (data.type === 'reference' && data.results.length > 1) {
            const first = data.results[0], last = data.results[data.results.length - 1];
            const addAll = document.createElement("div");
            addAll.className = "autocomplete-item autocomplete-item-range";
            addAll.textContent = `➕ Adicionar ${first.book_name} ${first.chapter}:${first.verse}-${last.verse} inteiro (${data.results.length} versos)`;
            addAll.onclick = () => addBibleRangeToList(data.results);
            list.appendChild(addAll);
        }

        data.results.forEach(verse => {
            const item = document.createElement("div");
            item.className = "autocomplete-item";
            item.textContent = `${verse.reference} — ${verse.text}`;
            item.onclick = () => addBibleVerseToList(verse);
            list.appendChild(item);
        });
    } catch (error) {
        console.error("Erro ao buscar na Bíblia:", error);
    }
}

// Busca só ADICIONA à Ordem do Culto — não manda ao vivo ainda. Ir ao ar
// acontece depois, clicando no item já na lista (sendBibleListItem), igual
// música: buscar prepara, clicar no item da lista é que "usa" de fato.
function addBibleVerseToList(verse) {
    const bibleUrl = `/bible/control/${verse.book_abbrev}/${verse.chapter}/${verse.verse}`;
    updateSongList({ title: `📖 ${verse.reference}`, url: bibleUrl, isBible: true, bibleReference: verse.reference });

    const input = document.getElementById("bibleSearchInput");
    input.value = "";
    document.getElementById("bibleAutocompleteList").innerHTML = "";

    // Feedback rápido de que adicionou — some sozinho depois de 1.5s
    const originalPlaceholder = input.placeholder;
    input.placeholder = `✅ ${verse.reference} adicionado à lista!`;
    setTimeout(() => { input.placeholder = originalPlaceholder; }, 1500);
}

// Adiciona TODOS os versos de uma referência de uma vez, como um item
// único na lista — pedido do usuário: buscar "Salmos 2:1-7" e só
// conseguir adicionar um verso por vez (o clique fechava a lista de
// resultados, tinha que buscar de novo pra pegar o próximo). Ao clicar
// nesse item depois, sendBibleListItem já sabe abrir o modal de leitura
// verso-a-verso normalmente — mesmo caminho de sempre, só a entrada na
// lista que passa a ser uma só.
function addBibleRangeToList(results) {
    if (!results || !results.length) return;
    const first = results[0];
    const last = results[results.length - 1];
    const reference = results.length === 1
        ? `${first.book_name} ${first.chapter}:${first.verse}`
        : `${first.book_name} ${first.chapter}:${first.verse}-${last.verse}`;
    const bibleUrl = `/bible/control/${first.book_abbrev}/${first.chapter}/${first.verse}-${last.verse}`;
    updateSongList({ title: `📖 ${reference}`, url: bibleUrl, isBible: true, bibleReference: reference });

    const input = document.getElementById("bibleSearchInput");
    input.value = "";
    document.getElementById("bibleAutocompleteList").innerHTML = "";

    const originalPlaceholder = input.placeholder;
    input.placeholder = `✅ ${reference} adicionado à lista!`;
    setTimeout(() => { input.placeholder = originalPlaceholder; }, 1500);
}

// Versos da passagem bíblica atualmente aberta no painel de leitura — cada
// um vira uma linha clicável (ver renderBibleReadAlong/sendSingleBibleVerse),
// pra mandar um verso de cada vez ao telão em vez de todos juntos.
let currentBibleVerses = [];
let currentBibleReference = '';
let currentBibleVersion = '';

// Manda um item bíblico da Ordem do Culto ao vivo. Busca o texto de novo em
// vez de guardar no momento de adicionar (um item pode ter vindo de uma
// ordem salva de outro dia — loadList() só reconstrói a referência, não o
// texto) — os dois casos passam pelo mesmo caminho, sem duplicar lógica.
//
// Reusa /api/bible/search (a mesma API da busca) em vez de tentar recompor
// a URL /bible/control/<livro>/<cap>/<verso>: essa URL depende de
// generateBibleUrl() no cliente, que só reconhece um punhado de livros e
// não sabe montar link pra referência sem verso específico (ex: "Salmo 93",
// um capítulo inteiro) — /api/bible/search já faz esse parse direito.
async function sendBibleListItem(reference, songItemEl) {
    if (!reference) {
        console.error("Item bíblico sem referência pra buscar.");
        return;
    }
    try {
        const response = await fetch(`/api/bible/search?q=${encodeURIComponent(reference)}`);
        const data = await response.json();
        if (data.error || !data.results || data.results.length === 0) {
            console.error("Erro ao buscar versículo:", data.error || "sem resultados");
            return;
        }

        currentBibleVerses = data.results;
        currentBibleReference = reference;
        currentBibleVersion = data.translation_name || '';
        renderBibleReadAlong();

        document.querySelectorAll('#songList .current-live').forEach(el => el.classList.remove('current-live'));
        if (songItemEl) songItemEl.classList.add('current-live');

        // Manda o primeiro verso ao vivo — nunca junta vários versos na
        // mesma tela; os demais ficam disponíveis pra clicar no painel.
        sendSingleBibleVerse(0);
    } catch (error) {
        console.error("Erro ao mandar versículo ao vivo:", error);
    }
}

// Desenha o modal de leitura com um verso por linha, cada um clicável —
// clicar manda só aquele verso ao telão (sendSingleBibleVerse). Modal (não
// caixinha na barra lateral) pra ter espaço de sobra pra ler o texto.
function renderBibleReadAlong() {
    document.getElementById('bibleReadAlongRef').textContent = `📖 ${currentBibleReference}`;

    const textEl = document.getElementById('bibleReadAlongText');
    textEl.innerHTML = '';
    currentBibleVerses.forEach((v, index) => {
        const line = document.createElement('div');
        line.className = 'bible-read-along-verse';
        line.dataset.index = index;
        line.textContent = `${v.verse} ${v.text}`;
        line.onclick = () => sendSingleBibleVerse(index);
        textEl.appendChild(line);
    });

    document.getElementById('bibleReadAlongModal').style.display = 'flex';
}

function closeBibleReadAlong() {
    document.getElementById('bibleReadAlongModal').style.display = 'none';
}

// Manda só UM verso (por índice em currentBibleVerses) ao vivo, e destaca
// qual está no ar dentro do próprio painel de leitura.
function sendSingleBibleVerse(index) {
    const v = currentBibleVerses[index];
    if (!v) return;

    const reference = `${v.book_name} ${v.chapter}:${v.verse}`;
    socket.emit('update_bible', {
        reference: reference,
        text: `${v.verse} ${v.text}`,
        book: v.book_name,
        chapter: v.chapter,
        verses: [{ num: v.verse, text: v.text }],
        version: currentBibleVersion
    });

    document.querySelectorAll('#bibleReadAlongText .bible-read-along-verse.active').forEach(el => el.classList.remove('active'));
    const lineEl = document.querySelector(`#bibleReadAlongText .bible-read-along-verse[data-index="${index}"]`);
    if (lineEl) lineEl.classList.add('active');
}

// Função para gerar URL de controle bíblico
function generateBibleUrl(reference) {
    const bookMap = {
        'gênesis': 'gn', 'genesis': 'gn', 'salmos': 'sl', 'salmo': 'sl',
        'joão': 'jo', 'joao': 'jo', 'romanos': 'rm', 'mateus': 'mt',
        'marcos': 'mc', 'lucas': 'lc', 'atos': 'at', 'hebreus': 'hb', 'apocalipse': 'ap'
    };
    const regex = /^(.+?)\s*(\d+)(?:\s*:\s*(\d+)(?:\s*-\s*(\d+))?)?$/i;
    const match = reference.match(regex);
    if (!match) return `/bible?search=${encodeURIComponent(reference)}`;
    const bookName = match[1].trim().toLowerCase();
    const chapter = match[2], verseStart = match[3], verseEnd = match[4];
    const bookAbbrev = bookMap[bookName];
    if (!bookAbbrev) return `/bible?search=${encodeURIComponent(reference)}`;
    let url = `/bible/control/${bookAbbrev}/${chapter}`;
    if (verseStart) url += verseEnd && verseEnd !== verseStart ? `/${verseStart}-${verseEnd}` : `/${verseStart}`;
    return url;
}

// Função para carregar a lista
async function loadList() {
    try {
        // 1. Prioridade: URL param → backend → sessionStorage → auto-detect
        //    URL param sempre vence: garante que navegar por links da lista não troque a ordem
        const urlParams = new URLSearchParams(window.location.search);
        let orderDate = urlParams.get('order')
            || CONFIG.orderDate
            || sessionStorage.getItem('uc_order_date')
            || '';

        let data = [];

        if (orderDate) {
            // Carrega ordem específica por data
            const response = await fetch(`/load?date=${orderDate}`);
            data = await response.json();
        } else {
            // Auto-detect: ordem mais próxima (hoje ou futura)
            const ordersResponse = await fetch('/api/orders');
            const orders = await ordersResponse.json();
            const dates = Object.keys(orders).sort();

            if (dates.length > 0) {
                const today = new Date().toISOString().split('T')[0];
                orderDate = dates.find(d => d >= today) || dates[dates.length - 1];
                data = orders[orderDate]?.itens || [];
            } else {
                // Fallback para sistema antigo
                const response = await fetch('/load');
                data = await response.json();
            }
        }

        // 2. Persiste a data resolvida para as próximas páginas da sessão
        if (orderDate) sessionStorage.setItem('uc_order_date', orderDate);

        data.forEach(item => {
            if (item.isBible) {
                const bibleUrl = generateBibleUrl(item.reference);
                updateSongList({ title: `📖 ${item.reference}`, url: bibleUrl, isBible: true, orderDate, bibleReference: item.reference });
            } else if (item.url && item.title) {
                updateSongList({ title: item.title, url: item.url, orderDate });
            } else if (item.anyText) {
                updateSongList({ title: item.anyText });
            }
        });
    } catch (error) {
        console.error("Erro ao carregar a lista:", error);
    }
}

// Chamar loadList no carregamento da página
document.addEventListener("DOMContentLoaded", loadList);

// Adicionar evento de input para busca de músicas
document.getElementById("searchInput").addEventListener("input", (event) => {
    searchSongs(event.target.value);
});

// Busca de Bíblia com debounce — busca por texto varre a tradução inteira
// no servidor a cada chamada, não faz sentido disparar a cada tecla.
document.getElementById("bibleSearchInput").addEventListener("input", (event) => {
    clearTimeout(bibleSearchTimeout);
    const query = event.target.value;
    bibleSearchTimeout = setTimeout(() => searchBibleQuick(query), 300);
});

// Fechar a lista de autocomplete ao clicar fora
document.addEventListener("click", (event) => {
    if (!event.target.closest(".search-box")) {
        document.getElementById("autocompleteList").innerHTML = "";
    }
});
