        const socket = io();
        // Dentro do /monitor (host=monitor, tela dividida "Letra"): é o
        // monitor — recebe o que vai só pro palco e fica parada em "Só
        // público", igual à cifra e à galeria (display.js, img.js)
        socket.on('connect', () => socket.emit('identify', {
            role: new URLSearchParams(location.search).get('host') === 'monitor' ? 'monitor' : 'public' }));
    
        const updateLyricsDisplay = (title, text, songId) => {
            $('#section-title').text(title);
            $('#section-text').html(formatLyrics(text));
            saveToLocalStorage(title, text, songId);
            // Referência/versão são só de Bíblia — some ao voltar pra música.
            document.getElementById('bible-reference').style.display = 'none';
            document.getElementById('bible-version').style.display = 'none';
            adjustFontSize();
        };
    
        // Elimina linha de cifra inteira (ChordLines.stripChordLines,
        // static/js/chord_lines.js) — tela pública não deve mostrar
        // cifra nenhuma, só a letra. Antes disso era ~65 linhas de regex
        // tentando limpar cifra palavra-por-palavra dentro do texto
        // (comentário original já admitia a fragilidade: "removemos a
        // limpeza agressiva de A/Em/etc. para não sumir com 'Em' de
        // frases"); o gate de linha inteira resolve isso de raiz.
        const formatLyrics = (text) => {
            if (!text) return '';
            const withoutChords = ChordLines.stripChordLines(text);
            return withoutChords.split('\n')
                .filter(line => !line.trim().startsWith('//')) // remove notas privadas de palco
                // Remove "____" usado pra alinhar a letra embaixo do acorde
                // (ex: "____Junto ao poço estava eu") — só faz sentido com a
                // linha de cifra visível, que a tela pública já removeu
                // acima; sem isso, sobrava o underscore cru na tela (mesmo
                // fix que display_obs.js já tinha, faltava aqui).
                .map(line => line.replace(/_+/g, ''))
                .filter(line => line.trim() !== '')
                .join('<br>');
        };

        const saveToLocalStorage = (title, text, songId) => {
            localStorage.setItem('currentTitle', title);
            localStorage.setItem('currentText', text);
            localStorage.setItem('currentSongId', songId);
        };
    
        function adjustFontSize() {
    // Usa requestAnimationFrame para garantir que o browser reflowou o layout
    // antes de ler clientHeight/scrollHeight (evita leitura com display:none ou layout antigo)
    requestAnimationFrame(() => {
        const container = document.getElementById('lyrics');
        const content = document.getElementById('section-text');
        let fontSize = 15;
        content.style.fontSize = `${fontSize}vw`;
        const containerHeight = container.clientHeight;
        while (content.scrollHeight > containerHeight * 0.90 && fontSize > 2) {
            fontSize -= 0.1;
            content.style.fontSize = `${fontSize}vw`;
        }
        console.log(`📐 Fonte ajustada para: ${fontSize}vw (altura: ${content.scrollHeight}px / ${containerHeight}px)`);
    });
}




    
        const loadInitialLyrics = (songId) => {
            $.ajax({
                url: `/lyrics_data/${songId}`,
                method: 'GET',
                success: (data) => {
                    if (data.error) {
                        console.error(data.error);
                    } else {
                        updateLyricsDisplay(data.title, data.text, songId);
                    }
                },
                error: (err) => console.error('Erro ao carregar os dados iniciais:', err),
            });
        };
    
        const initializeApp = () => {
            // Sempre consulta o servidor primeiro — localStorage só como fallback offline
            fetch('/api/current-display')
                .then(r => r.json())
                .then(data => {
                    if (data && data.mode === 'lyrics' && data.title) {
                        updateLyricsDisplay(data.title, data.text || '', data.id || null);
                    } else if (data && data.mode === 'image' && data.image_url) {
                        if (data.is_static) { showImage(data.image_url, data.zoom); }
                        // Rota da letra/cifra: mostra a letra aqui mesmo (abrir
                        // a própria página num iframe deixava a tela em branco)
                        else if (data.image_url.includes('/lyrics/display')) { showLyricsView(); }
                        else { showRoute(data.image_url); }
                    } else if (data && data.mode === 'video' && data.video_url) {
                        showVideo(data.video_url);
                    } else {
                        // Servidor sem estado: tenta localStorage
                        const savedSongId = localStorage.getItem('currentSongId');
                        const savedTitle  = localStorage.getItem('currentTitle');
                        const savedText   = localStorage.getItem('currentText');
                        if (savedSongId && savedTitle && savedText) {
                            updateLyricsDisplay(savedTitle, savedText, savedSongId);
                        } else if (savedSongId) {
                            loadInitialLyrics(savedSongId);
                        }
                    }
                    adjustFontSize();
                })
                .catch(() => {
                    // Sem rede: fallback para localStorage
                    const savedSongId = localStorage.getItem('currentSongId');
                    const savedTitle  = localStorage.getItem('currentTitle');
                    const savedText   = localStorage.getItem('currentText');
                    if (savedSongId && savedTitle && savedText) {
                        updateLyricsDisplay(savedTitle, savedText, savedSongId);
                    } else if (savedSongId) {
                        loadInitialLyrics(savedSongId);
                    }
                    adjustFontSize();
                });
        };
    
        const clearLyricsDisplay = () => {
            console.log('Clearing lyrics display');
            $('#section-text').empty();
            $('#section-title').empty();
            localStorage.removeItem('currentTitle');
            localStorage.removeItem('currentText');
            localStorage.removeItem('currentSongId');
        };
    
        $('#clear-lyrics').click(() => {
            console.log('Clear button clicked');
            clearLyricsDisplay();
            socket.emit('clear_lyrics');
        });
    
        // ── IMAGEM / VÍDEO ──────────────────────────────────────────
        const mediaImg   = document.getElementById('media-img');
        const mediaVideo = document.getElementById('media-video');

        const lyricsLayer = document.getElementById('lyrics');
        const routeLayer  = document.getElementById('route-layer');

        // Estado do botão "Esconder" (toggle-lyrics em /lyrics/<id>) — sem
        // isso, showLyricsView() (chamado por update_lyrics/update_bible
        // toda vez que chega letra/versículo novo) forçava a tela de volta
        // pra visível mesmo com o operador tendo escondido, ignorando o
        // toggle. Mesmo padrão já usado em display_obs.js (lyricsHidden).
        let lyricsHidden = false;
        // Ao abrir e a cada reconexão (servidor reiniciado, rede caiu),
        // confere com o servidor se o texto está escondido ou não — senão
        // a tela podia ficar presa no estado de antes
        function sincronizarEscondido() {
            fetch('/api/lyrics/visible').then(r => r.json()).then(d => {
                const antes = lyricsHidden;
                lyricsHidden = d.visible === false;
                if (lyricsHidden) lyricsLayer.style.display = 'none';
                else if (antes) { lyricsLayer.style.display = 'flex'; adjustFontSize(); }  // igual a lyrics_visibility_changed
            }).catch(() => {});
        }
        sincronizarEscondido();
        socket.on('connect', sincronizarEscondido);

        function showImage(url, zoom) {
            mediaVideo.pause();
            mediaVideo.removeAttribute('src');
            mediaVideo.load();
            mediaVideo.style.display = 'none';
            routeLayer.src = 'about:blank';
            routeLayer.style.display = 'none';
            lyricsLayer.style.display = 'none';
            mediaImg.src = url;
            mediaImg.style.transform = '';
            mediaImg.classList.add('photo');
            mediaImg.style.display = 'block';
            if (window.ucZoomOnShow) window.ucZoomOnShow(mediaImg, zoom);
        }

        function showLyricsView() {
            mediaVideo.pause();
            mediaVideo.removeAttribute('src');
            mediaVideo.load();
            mediaVideo.style.display = 'none';
            mediaImg.style.display = 'none';
            mediaImg.style.transform = '';
            routeLayer.src = 'about:blank';
            routeLayer.style.display = 'none';
            lyricsLayer.style.display = lyricsHidden ? 'none' : 'flex';
        }

        function showVideo(url) {
            routeLayer.src = 'about:blank';
            routeLayer.style.display = 'none';
            mediaImg.style.display = 'none';
            mediaVideo.classList.add('photo');
            mediaVideo.loop = false;   // o vídeo de fundo do tema deixa loop ligado
            mediaVideo.src = url;
            mediaVideo.style.display = 'block';
            lyricsLayer.style.display = 'none';
            mediaVideo.load();
            mediaVideo.play().catch(() => {
                mediaVideo.muted = true;
                mediaVideo.play().catch(() => {});
            });
        }

        function showRoute(url) {
            mediaVideo.pause();
            mediaVideo.removeAttribute('src');
            mediaVideo.load();
            mediaVideo.style.display = 'none';
            lyricsLayer.style.display = 'none';
            routeLayer.src = url;
            routeLayer.style.display = 'block';
        }

        // Vídeo terminou naturalmente → volta para letras e notifica slideshow
        mediaVideo.addEventListener('ended', function() {
            showLyricsView();
            socket.emit('video_ended', {});
        });

        // Baixa a próxima foto do slideshow em segundo plano, antes da troca
        // de verdade acontecer — new Image() só põe no cache do navegador,
        // não mostra nada na tela. Quando o display_image real chegar com
        // essa mesma URL, o navegador já tem o arquivo, sem esperar rede.
        socket.on('preload_image', (data) => {
            if (data.url) { new Image().src = data.url; }
        });

        socket.on('display_image', (data) => {
            const url = data.image_url || '';
            const isStaticFile = url.startsWith('/static/') || /\.(jpe?g|png|gif|bmp|webp)(\?.*)?$/i.test(url);
            if (isStaticFile) {
                showImage(url, data.zoom);
                return;
            }
            // Rotas de letras/cifra → mantém letras limpas
            if (url.includes('/lyrics/display')) {
                showLyricsView();
                return;
            }
            // Outras rotas (relógio, bíblia, imagem, URLs custom) → mostra em iframe
            showRoute(url);
        });

        socket.on('display_video', (data) => {
            showVideo(data.video_url);
        });

        socket.on('video_pause', (data) => {
            if (!mediaVideo.src) return;
            if (data.paused) mediaVideo.pause();
            else mediaVideo.play().catch(() => {});
        });

        socket.on('video_seek', (data) => {
            if (!mediaVideo.src) return;
            try { mediaVideo.currentTime = Number(data.time) || 0; } catch (_) {}
        });

        socket.on('video_restart', () => {
            if (!mediaVideo.src) return;
            mediaVideo.currentTime = 0;
            mediaVideo.play().catch(() => {});
        });

        // Zoom do /presenter: translate(pan%) scale(zoom), origem no centro —
        // a mesma transformação que o modal de zoom aplica na prévia. Só vale
        // pra foto que está na tela: zoom de outra foto é ignorado (não troca
        // a foto, pra não furar o Preparar/Liberar).
        socket.on('display_image_zoom', (data) => {
            if (!data || mediaImg.style.display === 'none' || mediaImg.getAttribute('src') !== data.image_url) return;
            window.ucApplyZoom(mediaImg, data);  // static/js/zoom_fit.js
        });

        // Antes só escurecia foto/vídeo: com letra, Bíblia ou relógio no
        // telão o botão "Tela preta" não fazia nada
        // Tela preta/branca/logo (static/js/camada_neutra.js). Aberta como
        // monitor (host=monitor), segue a do palco
        ucCamadaNeutra(socket, new URLSearchParams(location.search).get('host') === 'monitor' ? 'monitor' : 'public');

        // ────────────────────────────────────────────────────────────

        socket.on('update_lyrics', (data) => {
            showLyricsView();
            updateLyricsDisplay(data.title, data.text, data.id);
            const creditos = document.getElementById('song-credits');
            creditos.textContent = data.creditos || '';
            creditos.hidden = !data.creditos;
            // Aplica tema visual da música
            const theme = data.theme;
            const mediaImg   = document.getElementById('media-img');
            const mediaVideo = document.getElementById('media-video');
            if (theme && theme.type === 'image' && theme.url) {
                mediaVideo.pause();
                mediaVideo.style.display = 'none';
                mediaImg.src = theme.url;
                mediaImg.classList.remove('photo');
                mediaImg.style.display = 'block';
                document.getElementById('media-layer').style.background = '';
            } else if (theme && theme.type === 'video' && theme.url) {
                mediaImg.style.display = 'none';
                mediaVideo.classList.remove('photo');
                mediaVideo.src = theme.url;
                mediaVideo.style.display = 'block';
                mediaVideo.loop = true;
                mediaVideo.play().catch(() => {});
                document.getElementById('media-layer').style.background = '';
            } else if (theme && theme.type === 'color' && theme.color) {
                mediaImg.style.display = 'none';
                mediaVideo.pause();
                mediaVideo.style.display = 'none';
                document.getElementById('media-layer').style.background = theme.color;
            } else if (theme && theme.type === 'gradient' && theme.css) {
                mediaImg.style.display = 'none';
                mediaVideo.pause();
                mediaVideo.style.display = 'none';
                document.getElementById('media-layer').style.background = theme.css;
            } else if (theme === null || theme === undefined) {
                mediaImg.style.display = 'none';
                mediaVideo.pause();
                mediaVideo.style.display = 'none';
                document.getElementById('media-layer').style.background = '#000';
            }
        });
        
        // Escuta eventos de versículos da Bíblia
        socket.on('update_bible', (data) => {
            document.getElementById('song-credits').hidden = true;
            // Letra dentro do monitor (tela dividida): a Bíblia só aparece
            // no palco na página dela, liberada pra ele
            if (new URLSearchParams(location.search).get('host') === 'monitor') return;
            // Bíblia sempre na página dela (/bible/display: letra serifada,
            // transição) — antes, com o telão já nessa página, o versículo
            // novo trocava pro modo texto desta tela e o visual mudava a
            // cada toque. Já aberta, ela mesma recebe o versículo; senão
            // abre e pega o atual (/api/bible/current).
            console.log('📖 Public: Recebeu update_bible:', data && data.reference);
            const naBiblia = routeLayer.style.display !== 'none' &&
                (routeLayer.getAttribute('src') || '').startsWith('/bible/display');
            if (!naBiblia) showRoute('/bible/display');
        });

        // Escuta o evento para mostrar/esconder letras
        socket.on('lyrics_visibility_changed', (data) => {
            const visible = data.visible;
            console.log(`👁️ Public: Letras ${visible ? 'mostradas' : 'escondidas'}`);

            lyricsHidden = !visible;
            lyricsLayer.style.display = lyricsHidden ? 'none' : 'flex';

            // Se algum conteúdo foi mandado ENQUANTO escondido, adjustFontSize()
            // rodou com o container em display:none — clientHeight/scrollHeight
            // são sempre 0 nesse estado, então o loop de encolher a fonte nunca
            // executa e ela fica travada no tamanho inicial (15vw, enorme).
            // Recalcula agora que o container tem altura de verdade de novo.
            if (visible) adjustFontSize();
        });
    
        window.addEventListener('load', adjustFontSize); // Corrigido: Removido espaço
        window.addEventListener('resize ', adjustFontSize);

        $(document).ready(initializeApp);

        // ── Ticker de avisos ─────────────────────────────────────────
        function updateTicker(text) {
            const bar = document.getElementById('ticker-bar');
            const span = document.getElementById('ticker-text');
            if (!text) { bar.style.display = 'none'; return; }
            span.textContent = text;
            span.style.animationDuration = Math.max(10, text.length * 0.3) + 's';
            bar.style.display = 'block';
        }
        socket.on('ticker_update', function(data) { updateTicker(data.text || ''); });
        const _tickerRole = new URLSearchParams(location.search).get('host') === 'monitor' ? 'monitor' : 'public';
        fetch('/api/ticker').then(r => r.json()).then(d => { updateTicker((d.by_target || {})[_tickerRole] || ''); });

        // ── Tela do PC (WebRTC, static/js/screen_share_viewer.js) ─────────
        ucScreenShareViewer(socket, document.getElementById('screenShareVideo'), { role: new URLSearchParams(location.search).get('host') === 'monitor' ? 'monitor' : 'public' });
