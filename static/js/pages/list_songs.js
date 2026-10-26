// Variáveis globais para o modal
let selectedSongData = null;
let availableOrders = {};

// Data local YYYY-MM-DD (toISOString é UTC: depois das 21h em Fortaleza
// já seria "amanhã" e o culto da noite ia parar em "Anteriores")
function localISO(d) {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

// Ordem de exibição: por data e, no mesmo dia, pelo horário do culto
// (chaves YYYY-MM-DD / YYYY-MM-DD-N, ver static/js/agenda_cultos.js)
function orderSortKey(key) {
    const o = availableOrders[key] || {};
    return `${key.slice(0, 10)} ${o.horario_culto || o.horario || '99:99'} ${key}`;
}

const hasCulto = key => {
    const o = availableOrders[key] || {};
    return !!((o.tipo && o.tipo !== 'Nenhum') || (o.itens && o.itens.length));
};

// Carrega ordens disponíveis do servidor
async function loadAvailableOrders() {
    try {
        const response = await fetch('/api/orders');
        availableOrders = await response.json();

        const select = $('#orderDateSelect');
        select.empty();

        const keys = Object.keys(availableOrders).sort((a, b) => orderSortKey(a).localeCompare(orderSortKey(b)));

        if (keys.length === 0) {
            select.append($('<option value="">').text(_t('Nenhuma ordem encontrada')));
        } else {
            // Próximas (de hoje em diante) e as 3 últimas anteriores
            const today = localISO(new Date());
            const futureKeys = keys.filter(k => k.slice(0, 10) >= today);
            const pastKeys = keys.filter(k => k.slice(0, 10) < today).reverse().slice(0, 3);
            const group = (label, list) => {
                const g = $('<optgroup>').attr('label', label);
                list.forEach(key => {
                    const itemCount = availableOrders[key]?.itens?.length || 0;
                    g.append($('<option>').val(key).text(`${orderLabel(key)} (${_t('{n} itens', { n: itemCount })})`));
                });
                select.append(g);
            };
            if (futureKeys.length) group('📅 ' + _t('Próximas'), futureKeys);
            if (pastKeys.length) group('📜 ' + _t('Anteriores'), pastKeys);
            // Já vem marcado o próximo culto (pula datas só com eventos)
            const first = futureKeys.find(hasCulto) || futureKeys[0] || pastKeys[0];
            if (first) select.val(first);
        }

        // Define data padrão para nova ordem como próximo domingo
        const nextSunday = getNextSunday();
        $('#newOrderDate').val(nextSunday);

    } catch (error) {
        console.error('Erro ao carregar ordens:', error);
        $('#orderDateSelect').empty().append($('<option value="">').text(_t('Erro ao carregar')));
    }
}

// Formata data para exibição (aceita a chave de culto YYYY-MM-DD-N)
function formatDate(dateStr) {
    const date = new Date(dateStr.slice(0, 10) + 'T12:00:00');
    const options = { weekday: 'short', day: '2-digit', month: '2-digit', year: 'numeric' };
    return date.toLocaleDateString(ucLocale(), options);
}

// Data + qual culto (num dia pode haver mais de um)
function orderLabel(key) {
    const o = availableOrders[key] || {};
    const culto = [o.tipo !== 'Nenhum' && o.tipo, o.horario_culto].filter(Boolean).join(' ');
    if (culto) return `${formatDate(key)} · ${culto}`;
    return hasCulto(key) ? formatDate(key) : `${formatDate(key)} · ${_t('sem culto cadastrado')}`;
}

// Retorna próximo domingo
function getNextSunday() {
    const today = new Date();
    const dayOfWeek = today.getDay();
    const daysUntilSunday = dayOfWeek === 0 ? 7 : 7 - dayOfWeek;
    const nextSunday = new Date(today);
    nextSunday.setDate(today.getDate() + daysUntilSunday);
    return localISO(nextSunday);
}

// Cria nova ordem
async function createNewOrder() {
    const newDate = $('#newOrderDate').val();
    if (!newDate) {
        showNotification(_t('Selecione uma data para a nova ordem!'), 'error');
        return;
    }

    if (availableOrders[newDate]) {
        $('#orderDateSelect').val(newDate);
        showNotification(_t('Ordem já existe! Selecionada automaticamente.'));
        return;
    }

    try {
        await fetch(`/api/orders/${newDate}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ itens: [] })
        });

        showNotification(_t('Nova ordem criada para {data}!', { data: formatDate(newDate) }));
        await loadAvailableOrders();
        $('#orderDateSelect').val(newDate);

    } catch (error) {
        console.error('Erro ao criar ordem:', error);
        showNotification(_t('Erro ao criar nova ordem!'), 'error');
    }
}

// Fecha modal
function closeOrderModal() {
    $('#orderModal').fadeOut(200);
    selectedSongData = null;
}

// Confirma adição à ordem
async function confirmAddToOrder() {
    const selectedDate = $('#orderDateSelect').val();

    if (!selectedDate) {
        showNotification(_t('Selecione uma data!'), 'error');
        return;
    }

    if (!selectedSongData) {
        showNotification(_t('Erro: música não selecionada!'), 'error');
        return;
    }

    const button = selectedSongData.button;
    const originalHtml = button.html();
    const originalClass = button.attr('class');

    try {
        const response = await fetch(`/api/orders/${selectedDate}`);
        let orderData = await response.json();

        if (!orderData.itens) {
            orderData.itens = [];
        }

        const exists = orderData.itens.some(item =>
            item.url === selectedSongData.url ||
            (item.title && item.title.includes(selectedSongData.songTitle))
        );

        if (exists) {
            showNotification(_t('"{musica}" já está na ordem de {ordem}!', { musica: selectedSongData.songTitle, ordem: orderLabel(selectedDate) }));
            closeOrderModal();
            return;
        }

        orderData.itens.push({
            url: selectedSongData.url,
            title: selectedSongData.title
        });

        const saved = await fetch(`/api/orders/${selectedDate}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(orderData)
        });
        if (!saved.ok) throw new Error(`HTTP ${saved.status}`);

        button.html('<i class="fas fa-check"></i> ').append(document.createTextNode(_t('Adicionada')));
        button.removeClass('add-order').addClass('view');
        showNotification(_t('"{musica}" adicionada à ordem de {ordem}!', { musica: selectedSongData.songTitle, ordem: orderLabel(selectedDate) }));

        setTimeout(() => {
            button.html(originalHtml);
            button.attr('class', originalClass);
        }, 2000);

        closeOrderModal();

    } catch (error) {
        console.error('Erro ao adicionar:', error);
        showNotification(_t('Erro ao adicionar à ordem!'), 'error');
    }
}

// Função para mostrar notificações (global)
function showNotification(message, type = 'success') {
    window.ucToast(message, type);
}

$(document).ready(function() {
    // Funcionalidade de pesquisa
    $('#searchInput').on('keyup', function() {
        const searchTerm = $(this).val().toLowerCase().trim();
        let visibleCount = 0;

        $('tbody tr').each(function() {
            const title = $(this).find('.song-title').text().toLowerCase();
            const author = $(this).find('.song-author').text().toLowerCase();

            // Remove highlights anteriores (volta ao texto original)
            $(this).find('.song-title, .song-author').each(function() {
                const original = $(this).data('original-text');
                if (original !== undefined) $(this).text(original);
            });

            if (searchTerm === '' || title.includes(searchTerm) || author.includes(searchTerm)) {
                $(this).show();
                visibleCount++;

                // Adiciona highlight se há termo de busca
                if (searchTerm !== '') {
                    highlightText($(this).find('.song-title'), searchTerm);
                    highlightText($(this).find('.song-author'), searchTerm);
                }
            } else {
                $(this).hide();
            }
        });

        // Atualiza contador e mostra/esconde mensagem de "sem resultados"
        $('#totalSongs').text(visibleCount);

        if (visibleCount === 0 && searchTerm !== '') {
            $('#noResults').show();
            $('.table-container').hide();
        } else {
            $('#noResults').hide();
            $('.table-container').show();
        }
    });

    // Função para destacar texto — um elemento por vez: cada linha tem
    // DOIS .song-author (ao lado do título no celular e a coluna Autor);
    // antes o texto dos dois era juntado e escrito nos dois, dobrando o
    // autor a cada tecla. Termo e texto escapados (busca com "(" quebrava;
    // título com "<" virava HTML).
    const escapeHtml = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    const escapeRegex = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    function highlightText(elements, searchTerm) {
        const regex = new RegExp(`(${escapeRegex(searchTerm)})`, 'gi');
        elements.each(function() {
            const el = $(this);
            if (el.data('original-text') === undefined) el.data('original-text', el.text());
            const text = el.data('original-text');
            el.html(text.split(regex).map((part, i) =>
                i % 2 ? `<span class="uc-highlight">${escapeHtml(part)}</span>` : escapeHtml(part)
            ).join(''));
        });
    }

    // Funcionalidade de adicionar à ordem do culto - abre modal
    $('.add-to-order').click(function() {
        const songId = $(this).data('id');
        const songTitle = $(this).data('title');
        const songAuthor = $(this).data('author');

        // Armazena dados da música selecionada
        selectedSongData = {
            url: `/lyrics/${songId}`,
            title: songAuthor ? `${songTitle} | ${songAuthor}` : songTitle,
            songTitle: songTitle,
            button: $(this)
        };

        // Atualiza título no modal
        $('#modalSongTitle').text(`🎵 ${songTitle}${songAuthor ? ' - ' + songAuthor : ''}`);

        // Carrega ordens disponíveis
        loadAvailableOrders();

        // Mostra modal
        $('#orderModal').fadeIn(200);
    });

    // Fecha modal ao clicar fora
    $('#orderModal').click(function(e) {
        if (e.target === this) {
            closeOrderModal();
        }
    });

    // Fecha modal com ESC
    $(document).keydown(function(e) {
        if (e.key === 'Escape' && $('#orderModal').is(':visible')) {
            closeOrderModal();
        }
    });

    // Funcionalidade de remoção de música
    $('.delete-song').click(function() {
        const songId = $(this).data('id');
        if (confirm(_t('Tem certeza que deseja remover esta música?'))) {
            $.ajax({
                type: 'POST',
                url: '/delete_song/' + songId,
                success: function(response) {
                    alert(response.message);
                    location.reload();
                },
                error: function() {
                    alert(_t('Erro ao remover a música.'));
                }
            });
        }
    });

    // Adicionando comportamento às abas
    $('.tab').click(function() {
        $('.tab').removeClass('active');
        $(this).addClass('active');
    });
});
