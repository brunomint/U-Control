const CONFIG = JSON.parse(document.getElementById('view-song-order-data').textContent);

// Função para carregar conteúdo via AJAX
function loadContent(url) {
    $.ajax({
        url: url,
        method: 'GET',
        success: function(response) {
            $('#content').html(response);  // Atualiza o conteúdo da página
        },
        error: function() {
            $('#content').html('<p>Erro ao carregar o conteúdo.</p>');
        }
    });
}

// Função para gerar URL de controle bíblico a partir de referência
function generateBibleUrl(reference) {
    const bookMap = {
        'gênesis': 'gn', 'genesis': 'gn', 'gn': 'gn',
        'êxodo': 'ex', 'exodo': 'ex', 'ex': 'ex',
        'salmos': 'sl', 'salmo': 'sl', 'sl': 'sl',
        'provérbios': 'pv', 'proverbios': 'pv', 'pv': 'pv',
        'isaías': 'is', 'isaias': 'is', 'is': 'is',
        'mateus': 'mt', 'mt': 'mt',
        'marcos': 'mc', 'mc': 'mc',
        'lucas': 'lc', 'lc': 'lc',
        'joão': 'jo', 'joao': 'jo', 'jo': 'jo',
        'atos': 'at', 'at': 'at',
        'romanos': 'rm', 'rm': 'rm',
        '1 coríntios': '1co', '1 corintios': '1co', '1co': '1co',
        '2 coríntios': '2co', '2 corintios': '2co', '2co': '2co',
        'gálatas': 'gl', 'galatas': 'gl', 'gl': 'gl',
        'efésios': 'ef', 'efesios': 'ef', 'ef': 'ef',
        'filipenses': 'fp', 'fp': 'fp',
        'colossenses': 'cl', 'cl': 'cl',
        'hebreus': 'hb', 'hb': 'hb',
        'tiago': 'tg', 'tg': 'tg',
        '1 pedro': '1pe', '1pe': '1pe',
        '2 pedro': '2pe', '2pe': '2pe',
        '1 joão': '1jo', '1 joao': '1jo', '1jo': '1jo',
        'apocalipse': 'ap', 'ap': 'ap'
    };

    const regex = /^(.+?)\s*(\d+)(?:\s*:\s*(\d+)(?:\s*-\s*(\d+))?)?$/i;
    const match = reference.match(regex);

    if (!match) return `/bible?search=${encodeURIComponent(reference)}`;

    const bookName = match[1].trim().toLowerCase();
    const chapter = match[2];
    const verseStart = match[3];
    const verseEnd = match[4];

    const bookAbbrev = bookMap[bookName];
    if (!bookAbbrev) return `/bible?search=${encodeURIComponent(reference)}`;

    let url = `/bible/control/${bookAbbrev}/${chapter}`;
    if (verseStart) {
        if (verseEnd && verseEnd !== verseStart) {
            url += `/${verseStart}-${verseEnd}`;
        } else {
            url += `/${verseStart}`;
        }
    }
    return url;
}

// Função para carregar a lista de músicas
async function loadList() {
    try {
        // Usa a data passada pelo backend ou busca da URL
        let orderDate = CONFIG.orderDate;
        if (!orderDate) {
            const urlParams = new URLSearchParams(window.location.search);
            orderDate = urlParams.get('order');
        }

        let data = [];

        if (orderDate) {
            // Carrega ordem específica por data
            const response = await fetch(`/load?date=${orderDate}`);
            data = await response.json();
        } else {
            // Busca a ordem mais próxima (hoje ou futura)
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

        const menu = document.getElementById("menu");

        // Adiciona a lista de músicas diretamente no menu
        data.forEach(item => {
            if (item.isBible) {
                // Item de Bíblia - usa URL de controle gerada pelo backend
                const url = generateBibleUrl(item.reference);
                menu.innerHTML += `<a href="${url}" class="song-link" style="color: #b39ddb;">📖 ${item.reference}</a>`;
            } else if (item.url && item.title) {
                let modifiedUrl = item.url.replace("/lyrics/", "/view/");
                // Se for /order, mostra como texto
                if (modifiedUrl.includes("/order")) {
                    menu.innerHTML += `<a href="#" class="song-link" style="color: #ffb74d;">${item.title}</a>`;
                } else {
                    // Adiciona o parâmetro order para manter a lista correta no menu
                    const urlWithOrder = orderDate ? `${modifiedUrl}?order=${orderDate}` : modifiedUrl;
                    menu.innerHTML += `<a href="${urlWithOrder}" class="song-link">${item.title}</a>`;
                }
            } else if (item.anyText) {
                menu.innerHTML += `<a href="#" class="song-link" style="color: #ffb74d;">${item.anyText}</a>`;
            }
        });
    } catch (error) {
        console.error("Erro ao carregar a lista:", error);
        alert("Erro ao carregar a lista de músicas.");
    }
}

loadList();

// Função para alternar a visibilidade do menu (mobile)
function toggleMenu() {
    const menu = document.querySelector('.menu');
    menu.classList.toggle('visible');
}

document.addEventListener('click', function(event) {
    const menu = document.querySelector('.menu');
    const toggleButton = document.querySelector('#toggle-menu');
    const isClickInsideMenu = menu.contains(event.target);
    const isClickOnToggleButton = event.target.matches('#toggle-menu');

    // Em mobile, fecha o menu ao clicar fora
    if (window.innerWidth <= 768 && menu.classList.contains('visible') && !isClickInsideMenu && !isClickOnToggleButton) {
        menu.classList.remove('visible');
    }
});

// Busca de música na página de boas-vindas — mesma API pública e o
// mesmo botão+popover de view_song.html (main.py:/api/songs/search),
// sem login, busca por título/autor/trecho da letra. Pedido explícito
// do usuário, 2026-09-22.
window.toggleSearchSong = function() {
    const popover = document.getElementById('searchSongPopover');
    if (!popover) return;
    const abrindo = getComputedStyle(popover).display === 'none';
    popover.style.display = abrindo ? 'block' : 'none';
    if (abrindo) {
        document.getElementById('searchSongInput').focus();
    }
};

let buscaSongTimeout = null;
const searchSongInput = document.getElementById('searchSongInput');
if (searchSongInput) {
    searchSongInput.addEventListener('input', (e) => {
        const query = e.target.value.trim();
        clearTimeout(buscaSongTimeout);
        const resultsEl = document.getElementById('searchSongResults');
        if (!query) {
            resultsEl.innerHTML = '';
            return;
        }
        buscaSongTimeout = setTimeout(async () => {
            try {
                const resp = await fetch(`/api/songs/search?q=${encodeURIComponent(query)}`);
                const songs = await resp.json();
                resultsEl.innerHTML = '';
                if (songs.length === 0) {
                    const vazio = document.createElement('div');
                    vazio.className = 'search-song-item';
                    vazio.textContent = 'Nenhuma música encontrada';
                    resultsEl.appendChild(vazio);
                    return;
                }
                songs.forEach(song => {
                    const item = document.createElement('div');
                    item.className = 'search-song-item';
                    // textContent + span separado (não innerHTML com o
                    // título interpolado) — vem do banco, pode ter sido
                    // digitado por qualquer admin, e essa busca é
                    // pública, sem login.
                    item.appendChild(document.createTextNode(song.title + ' '));
                    const autorSpan = document.createElement('span');
                    autorSpan.className = 'autor';
                    autorSpan.textContent = '— ' + song.author;
                    item.appendChild(autorSpan);
                    item.onclick = () => {
                        window.location.href = `/view/${song.id}`;
                    };
                    resultsEl.appendChild(item);
                });
            } catch (err) {
                console.error('Erro ao buscar músicas:', err);
            }
        }, 300);
    });

    document.addEventListener('click', function(e) {
        const widget = document.querySelector('.search-song-widget');
        const popover = document.getElementById('searchSongPopover');
        if (!widget || !popover) return;
        if (getComputedStyle(popover).display === 'none') return;
        if (!widget.contains(e.target)) {
            popover.style.display = 'none';
        }
    });
}
