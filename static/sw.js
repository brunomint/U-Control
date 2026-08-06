const CACHE = 'ucontrol-v1';
const STATIC = [
  '/',
  '/songs',
  '/order',
  '/static/U-Control-ico.ico'
];

self.addEventListener('install', e => {
    e.waitUntil(
        caches.open(CACHE).then(c =>
            Promise.allSettled(STATIC.map(url => c.add(url).catch(() => {})))
        )
    );
    self.skipWaiting();
});

self.addEventListener('activate', e => {
    e.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
        )
    );
    self.clients.claim();
});

self.addEventListener('fetch', e => {
    // Só interceptar GET do mesmo origin
    if (e.request.method !== 'GET') return;
    if (!e.request.url.startsWith(self.location.origin)) return;

    const url = new URL(e.request.url);

    // Ignorar SocketIO e buscas externas
    if (url.pathname.startsWith('/socket.io/') ||
        url.pathname.includes('/api/busca_vagalume') ||
        url.pathname.includes('/api/importar_vagalume')) {
        return;
    }

    // Navegação (carregamento de páginas): network-first, cacheia para uso offline
    if (e.request.mode === 'navigate') {
        e.respondWith((async () => {
            try {
                const res = await fetch(e.request);
                if (res.ok) {
                    const clone = res.clone();
                    caches.open(CACHE).then(c => c.put(e.request, clone));
                }
                return res;
            } catch {
                const cached = await caches.match(e.request)
                            || await caches.match(e.request, { ignoreSearch: true });
                if (cached) return cached;
                return new Response(
                    `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
                    <meta name="viewport" content="width=device-width,initial-scale=1">
                    <title>Sem conexão</title>
                    <style>body{margin:0;background:#0a0a0a;color:#e2e8f0;font-family:sans-serif;
                    display:flex;flex-direction:column;align-items:center;justify-content:center;
                    height:100vh;gap:12px;text-align:center;padding:20px;box-sizing:border-box}
                    .icon{font-size:56px}.msg{color:#94a3b8;font-size:14px}
                    .hint{color:#4ade80;font-size:13px;margin-top:4px}</style></head>
                    <body><div class="icon">📶</div>
                    <p>Sem conexão com o servidor</p>
                    <p class="msg">Abra uma música enquanto online<br>para ela ficar disponível aqui.</p>
                    <p class="hint">A rede voltou? <a href="" style="color:#4ade80">Recarregar</a></p>
                    </body></html>`,
                    { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' } }
                );
            }
        })());
        return;
    }

    // Network-first para letras e API dinâmica (offline fallback)
    if (url.pathname.startsWith('/lyrics/') || url.pathname.startsWith('/api/')) {
        e.respondWith(
            fetch(e.request)
                .then(res => {
                    if (res.ok) {
                        const clone = res.clone();
                        caches.open(CACHE).then(c => c.put(e.request, clone));
                    }
                    return res;
                })
                .catch(() => caches.match(e.request))
        );
        return;
    }

    // Cache-first para assets estáticos (JS, CSS, imagens)
    e.respondWith(
        caches.match(e.request).then(r => r || fetch(e.request).then(res => {
            if (res.ok) {
                const clone = res.clone();
                caches.open(CACHE).then(c => c.put(e.request, clone));
            }
            return res;
        }).catch(() => new Response('', {status: 503})))
    );
});
