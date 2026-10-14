// Injeta o token CSRF (Flask-WTF) automaticamente em toda chamada fetch()
// que não seja GET/HEAD/OPTIONS — evita ter que editar cada fetch() do
// projeto uma por uma. Lê o token de <meta name="csrf-token">, que cada
// página injeta via {{ csrf_token() }}. Sem esse meta tag, não faz nada
// (fetch original intocado) — é o caso de páginas sem nenhuma ação POST.
(function () {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (!meta) return;
    // Lido na hora de cada envio (não guardado): quem renova o token depois
    // de um novo login (ex.: Salvar do editor) só precisa trocar o meta.
    const token = () => meta.content;
    const safeMethods = new Set(['GET', 'HEAD', 'OPTIONS', 'TRACE']);
    const originalFetch = window.fetch;

    window.fetch = function (input, init) {
        init = init || {};
        const method = (init.method || (input instanceof Request ? input.method : 'GET') || 'GET').toUpperCase();
        if (!safeMethods.has(method)) {
            const headers = new Headers(init.headers || (input instanceof Request ? input.headers : undefined));
            if (!headers.has('X-CSRFToken')) {
                headers.set('X-CSRFToken', token());
            }
            init = Object.assign({}, init, { headers });
        }
        return originalFetch.call(this, input, init);
    };

    // Várias páginas ainda usam $.ajax()/$.post() do jQuery pra POST em vez
    // de fetch() (ex: edit_song.js, new_song.js, list_songs.js) — o patch
    // acima não pega isso, jQuery usa XMLHttpRequest por baixo, não
    // window.fetch. Achado só depois de um "não consigo salvar" real:
    // /edit_song/<id> vinha rejeitando com CSRF ausente. jQuery carrega
    // DEPOIS deste script (csrf.js fica cedo no <head> de propósito), então
    // a configuração espera o DOMContentLoaded, quando os <script src>
    // síncronos já rodaram.
    function setupJQuery() {
        if (!window.jQuery) return;
        window.jQuery.ajaxSetup({
            beforeSend: function (xhr, settings) {
                const method = (settings.type || settings.method || 'GET').toUpperCase();
                if (!safeMethods.has(method)) {
                    xhr.setRequestHeader('X-CSRFToken', token());
                }
            }
        });
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setupJQuery);
    } else {
        setupJQuery();
    }
})();
