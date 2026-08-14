// Injeta o token CSRF (Flask-WTF) automaticamente em toda chamada fetch()
// que não seja GET/HEAD/OPTIONS — evita ter que editar cada fetch() do
// projeto uma por uma. Lê o token de <meta name="csrf-token">, que cada
// página injeta via {{ csrf_token() }}. Sem esse meta tag, não faz nada
// (fetch original intocado) — é o caso de páginas sem nenhuma ação POST.
(function () {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (!meta) return;
    const token = meta.content;
    const safeMethods = new Set(['GET', 'HEAD', 'OPTIONS', 'TRACE']);
    const originalFetch = window.fetch;

    window.fetch = function (input, init) {
        init = init || {};
        const method = (init.method || (input instanceof Request ? input.method : 'GET') || 'GET').toUpperCase();
        if (!safeMethods.has(method)) {
            const headers = new Headers(init.headers || (input instanceof Request ? input.headers : undefined));
            if (!headers.has('X-CSRFToken')) {
                headers.set('X-CSRFToken', token);
            }
            init = Object.assign({}, init, { headers });
        }
        return originalFetch.call(this, input, init);
    };
})();
