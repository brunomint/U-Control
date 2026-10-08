const socket = io();

// Busca ao pressionar Enter
document.getElementById('searchInput').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        searchBible();
    }
});

// Processa parâmetro search da URL ao carregar
window.addEventListener('load', function() {
    const urlParams = new URLSearchParams(window.location.search);
    const searchQuery = urlParams.get('search');
    if (searchQuery) {
        document.getElementById('searchInput').value = searchQuery;
        searchBible();
    }
});

// Atualiza links ao mudar tradução
document.getElementById('translationSelect').addEventListener('change', function() {
    const translation = this.value;
    // Atualiza todos os links de livros
    document.querySelectorAll('.book-card').forEach(link => {
        const href = link.getAttribute('href');
        const newHref = href.replace(/translation=\w+/, 'translation=' + translation);
        link.setAttribute('href', newHref);
    });
    // Atualiza links rápidos
    document.querySelectorAll('.quick-link').forEach(link => {
        const href = link.getAttribute('href');
        const newHref = href.replace(/translation=\w+/, 'translation=' + translation);
        link.setAttribute('href', newHref);
    });
});

function searchBible() {
    const query = document.getElementById('searchInput').value.trim();
    const translation = document.getElementById('translationSelect').value;

    if (query.length < 3) {
        alert('Digite pelo menos 3 caracteres para buscar');
        return;
    }

    fetch(`/api/bible/search?q=${encodeURIComponent(query)}&translation=${translation}`)
        .then(response => response.json())
        .then(data => {
            displayResults(data);
        })
        .catch(error => {
            console.error('Erro na busca:', error);
            alert('Erro ao buscar. Tente novamente.');
        });
}

function displayResults(data) {
    const container = document.getElementById('resultsContainer');
    const resultsDiv = document.getElementById('searchResults');

    if (data.results && data.results.length > 0) {
        let html = '';
        data.results.forEach(result => {
            html += `
                <div class="result-item" onclick="goToVerse('${result.book_abbrev}', ${result.chapter}, ${result.verse})">
                    <div class="result-reference">${result.reference}</div>
                    <div class="result-text">${result.text}</div>
                </div>
            `;
        });
        container.innerHTML = html;
        resultsDiv.classList.add('active');
    } else {
        container.innerHTML = '<div class="uc-empty">Nenhum resultado encontrado.</div>';
        resultsDiv.classList.add('active');
    }
}

function goToVerse(bookAbbrev, chapter, verse) {
    const translation = document.getElementById('translationSelect').value;
    // Redireciona para a página de controle
    window.location.href = `/bible/control/${bookAbbrev}/${chapter}?translation=${translation}`;
}

// Enviar versículo para o display
function sendToDisplay(reference, text) {
    socket.emit('update_bible', {
        reference: reference,
        text: text
    });
}
