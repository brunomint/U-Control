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
                updateSongList({ title: `📖 ${item.reference}`, url: bibleUrl, isBible: true, orderDate });
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

// Fechar a lista de autocomplete ao clicar fora
document.addEventListener("click", (event) => {
    if (!event.target.closest(".search-box")) {
        document.getElementById("autocompleteList").innerHTML = "";
    }
});
