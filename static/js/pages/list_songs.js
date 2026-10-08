// Variáveis globais para o modal
let selectedSongData = null;
let availableOrders = {};

// Carrega ordens disponíveis do servidor
async function loadAvailableOrders() {
    try {
        const response = await fetch('/api/orders');
        availableOrders = await response.json();

        const select = $('#orderDateSelect');
        select.empty();

        const dates = Object.keys(availableOrders).sort();

        if (dates.length === 0) {
            select.append('<option value="">Nenhuma ordem encontrada</option>');
        } else {
            // Filtra para mostrar apenas datas de hoje em diante
            const today = new Date().toISOString().split('T')[0];
            const futureDates = dates.filter(d => d >= today);
            const pastDates = dates.filter(d => d < today).reverse().slice(0, 3);

            if (futureDates.length > 0) {
                select.append('<optgroup label="📅 Próximas">');
                futureDates.forEach(date => {
                    const formatted = formatDate(date);
                    const itemCount = availableOrders[date]?.itens?.length || 0;
                    select.append(`<option value="${date}">${formatted} (${itemCount} itens)</option>`);
                });
                select.append('</optgroup>');
            }

            if (pastDates.length > 0) {
                select.append('<optgroup label="📜 Anteriores">');
                pastDates.forEach(date => {
                    const formatted = formatDate(date);
                    const itemCount = availableOrders[date]?.itens?.length || 0;
                    select.append(`<option value="${date}">${formatted} (${itemCount} itens)</option>`);
                });
                select.append('</optgroup>');
            }
        }

        // Define data padrão para nova ordem como próximo domingo
        const nextSunday = getNextSunday();
        $('#newOrderDate').val(nextSunday);

    } catch (error) {
        console.error('Erro ao carregar ordens:', error);
        $('#orderDateSelect').html('<option value="">Erro ao carregar</option>');
    }
}

// Formata data para exibição
function formatDate(dateStr) {
    const date = new Date(dateStr + 'T12:00:00');
    const options = { weekday: 'short', day: '2-digit', month: '2-digit', year: 'numeric' };
    return date.toLocaleDateString('pt-BR', options);
}

// Retorna próximo domingo
function getNextSunday() {
    const today = new Date();
    const dayOfWeek = today.getDay();
    const daysUntilSunday = dayOfWeek === 0 ? 7 : 7 - dayOfWeek;
    const nextSunday = new Date(today);
    nextSunday.setDate(today.getDate() + daysUntilSunday);
    return nextSunday.toISOString().split('T')[0];
}

// Cria nova ordem
async function createNewOrder() {
    const newDate = $('#newOrderDate').val();
    if (!newDate) {
        showNotification('Selecione uma data para a nova ordem!', 'error');
        return;
    }

    if (availableOrders[newDate]) {
        $('#orderDateSelect').val(newDate);
        showNotification('Ordem já existe! Selecionada automaticamente.');
        return;
    }

    try {
        await fetch(`/api/orders/${newDate}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ itens: [] })
        });

        showNotification(`Nova ordem criada para ${formatDate(newDate)}!`);
        await loadAvailableOrders();
        $('#orderDateSelect').val(newDate);

    } catch (error) {
        console.error('Erro ao criar ordem:', error);
        showNotification('Erro ao criar nova ordem!', 'error');
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
        showNotification('Selecione uma data!', 'error');
        return;
    }

    if (!selectedSongData) {
        showNotification('Erro: música não selecionada!', 'error');
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
            showNotification(`"${selectedSongData.songTitle}" já está na ordem de ${formatDate(selectedDate)}!`);
            closeOrderModal();
            return;
        }

        orderData.itens.push({
            url: selectedSongData.url,
            title: selectedSongData.title
        });

        await fetch(`/api/orders/${selectedDate}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(orderData)
        });

        button.html('<i class="fas fa-check"></i> Adicionada');
        button.removeClass('add-order').addClass('view');
        showNotification(`"${selectedSongData.songTitle}" adicionada à ordem de ${formatDate(selectedDate)}!`);

        setTimeout(() => {
            button.html(originalHtml);
            button.attr('class', originalClass);
        }, 2000);

        closeOrderModal();

    } catch (error) {
        console.error('Erro ao adicionar:', error);
        showNotification('Erro ao adicionar à ordem!', 'error');
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

            // Remove highlights anteriores
            $(this).find('.uc-highlight').each(function() {
                $(this).replaceWith($(this).text());
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

    // Função para destacar texto
    function highlightText(element, searchTerm) {
        const text = element.text();
        const regex = new RegExp(`(${searchTerm})`, 'gi');
        const highlightedText = text.replace(regex, '<span class="uc-highlight">$1</span>');
        element.html(highlightedText);
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
        if (confirm('Tem certeza que deseja remover esta música?')) {
            $.ajax({
                type: 'POST',
                url: '/delete_song/' + songId,
                success: function(response) {
                    alert(response.message);
                    location.reload();
                },
                error: function() {
                    alert('Erro ao remover a música.');
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
