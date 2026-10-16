        const iframeContainer = document.getElementById('iframeContainer');
        const iframe1 = document.getElementById('monitorIframe1');
        const iframe2 = document.getElementById('monitorIframe2');
        const displayImage = document.getElementById('displayImage');
        const displayVideo = document.getElementById('displayVideo');
        const socket = io.connect(window.location.protocol + '//' + window.location.host);

        displayVideo.addEventListener('ended', function() {
            socket.emit('video_ended', {});
        });

        // Se /monitor está dentro de iframe (ex: home/control.html), fica mudo para
        // evitar áudio duplicado. Como tela autônoma, toca com som.
        const isInsideIframe = (window.self !== window.top);

        socket.on('connect', function() {
            socket.emit('identify', { role: 'monitor' });
        });

        // Página do U-Control aberta DENTRO do monitor (tela dividida, URL,
        // letra/foto/Bíblia): vai com host=monitor pra ela se apresentar ao
        // servidor como monitor. Senão, em "Só público" o servidor deixava
        // de mandar pro /monitor, mas a /img ou a /lyrics/display de dentro
        // dele continuavam recebendo — e o monitor mudava junto com o público.
        function noMonitor(u) {
            if (!u || !u.startsWith('/') || u.startsWith('/static/') || /[?&]host=monitor\b/.test(u)) return u;
            return u + (u.includes('?') ? '&' : '?') + 'host=monitor';
        }

        // ── Tela dividida ────────────────────────────────────────────
        // Com o monitor dividido (ex.: foto + cifra), conteúdo novo de um
        // tipo que um dos lados já mostra vai pra ESSE lado e a divisão
        // continua: a seção da cifra muda no lado da cifra, a foto no lado
        // da galeria. Antes a foto (ou, em "Só monitor", a cifra) tomava o
        // monitor inteiro e o outro lado sumia.
        let splitOn = false;
        function paneKind(src) {
            let path = src || '';
            try { path = new URL(src, location.origin).pathname; } catch (e) { /* mantém */ }
            if (path === '/img') return 'gallery';
            if (path.startsWith('/lyrics/display')) return 'lyrics';
            if (path.startsWith('/bible/display')) return 'bible';
            if (path === '/clock') return 'clock';
            return null;
        }
        // Iframe do lado que mostra este tipo, ou null
        function splitPane(kind) {
            if (!splitOn) return null;
            return [iframe1, iframe2].find(f => paneKind(f.getAttribute('src')) === kind) || null;
        }
        function isMediaUrl(url) {
            return /^\/static\//.test(url || '') || isImageUrl(url) || isVideoUrl(url);
        }
        // Foto/vídeo no lado da galeria. Com o evento chegando também na
        // /img de dentro do monitor (mesmo socket), ela troca sozinha; em
        // "Só monitor" o evento vem só pra cá, então chama a /img direto.
        function mediaToPane(url, direto) {
            const pane = isMediaUrl(url) ? splitPane('gallery') : null;
            if (!pane) return false;
            if (direto) {
                try {
                    const w = pane.contentWindow;
                    if (isVideoUrl(url)) w.playVideo(url); else w.loadImage(url);
                } catch (e) { pane.src = noMonitor('/img'); }
            }
            return true;
        }

        // Verifica se a URL é de uma imagem com base na extensão
        function isImageUrl(url) {
            return /\.(jpeg|jpg|gif|png|bmp|webp)(\?.*)?$/i.test(url || '');
        }
        function isVideoUrl(url) {
            return /\.(mp4|webm|mov)(\?.*)?$/i.test(url || '');
        }

        // Função para mostrar a imagem em vez dos iframes
        function showImage(imageUrl) {
            if (isVideoUrl(imageUrl)) {
                // Sempre carrega pausado no primeiro frame.
                // Para tocar, o operador precisa apertar play no / ou /presenter.
                playVideo(imageUrl, { paused: true });
                // Sincroniza o estado do servidor com "pausado no início"
                socket.emit('toggle_video_pause', { paused: true });
                socket.emit('seek_video', { time: 0 });
            } else if (isImageUrl(imageUrl)) {
                // Mostra a imagem em tela cheia, escondendo iframes e vídeo
                splitOn = false;
                hideVideo();
                iframe1.style.display = 'none';
                iframe2.style.display = 'none';
                displayImage.src = imageUrl;
                displayImage.style.transform = '';
                displayImage.style.display = 'block';
            } else {
                // Se não for uma imagem, mostra o iframe padrão com uma URL de backup
                iframe1.src = noMonitor(imageUrl) || "about:blank";
                showSingleIframe();
            }
        }

        function playVideo(url, opts) {
            splitOn = false;
            opts = opts || {};
            const startAt = Number(opts.startAt) || 0;
            const startPaused = !!opts.paused;
            // Esconde iframes e imagem; mostra vídeo
            iframe1.style.display = 'none';
            iframe2.style.display = 'none';
            displayImage.style.display = 'none';
            displayVideo.style.display = 'block';
            displayVideo.src = url;
            displayVideo.muted = isInsideIframe;

            // Modo "carregar pausado": play+pause como warm-up para destravar autoplay
            if (startPaused) {
                displayVideo.preload = 'auto';
                displayVideo.addEventListener('loadedmetadata', () => {
                    try { displayVideo.currentTime = startAt || 0; } catch (_) {}
                    displayVideo.play().then(() => {
                        displayVideo.pause();
                        console.log('⏸️ Monitor: vídeo carregado pausado, autoplay destravado.');
                    }).catch(e => {
                        console.warn('Monitor: autoplay bloqueado no warm-up:', e && e.message);
                    });
                }, { once: true });
                displayVideo.load();
                return;
            }

            const seekAndPlay = () => {
                if (startAt > 0) {
                    try { displayVideo.currentTime = startAt; } catch (_) {}
                }
                displayVideo.play().then(() => {
                    console.log('🎬 Monitor: vídeo tocando @', startAt.toFixed(2) + 's:', url);
                }).catch(e => {
                    console.warn('Autoplay com som bloqueado, tentando mudo:', e);
                    displayVideo.muted = true;
                    displayVideo.play().catch(err => console.error('Falha total no autoplay:', err));
                });
            };
            if (startAt > 0) {
                displayVideo.addEventListener('loadedmetadata', seekAndPlay, { once: true });
                displayVideo.load();
            } else {
                displayVideo.load();
                seekAndPlay();
            }
        }

        function hideVideo() {
            displayVideo.pause();
            displayVideo.removeAttribute('src');
            displayVideo.load();
            displayVideo.style.display = 'none';
        }

        // Função para ajustar layout com um iframe
        function showSingleIframe() {
            splitOn = false;
            iframeContainer.className = 'iframe-container single-iframe';
            displayImage.style.display = 'none'; // Oculta a imagem se estiver visível
            iframe1.style.display = 'block';
            iframe2.style.display = 'none';
        }

        // Função para ajustar layout com dois iframes
        function showDoubleIframe() {
            splitOn = true;
            iframeContainer.className = 'iframe-container double-iframe';
            displayImage.style.display = 'none'; // Oculta a imagem se estiver visível
            iframe1.style.display = 'block';
            iframe2.style.display = 'block';
        }

        // Carrega o estado salvo do banco de dados ao iniciar
        function loadDisplayState() {
            fetch('/get_display_state')
                .then(res => res.json())
                .then(state => {
                    console.log('💾 Monitor: Estado do display carregado:', state);
                    
                    if (state.url1 && state.url2) {
                        // Duas URLs - tela dividida
                        iframe1.src = noMonitor(state.url1);
                        iframe2.src = noMonitor(state.url2);
                        showDoubleIframe();
                    } else if (state.url1) {
                        // Uma URL - tela cheia
                        console.log(`🎵 Monitor: Carregando URL do display: ${state.url1}`);
                        showImage(state.url1);
                    } else {
                        // Se não há estado do display, tenta carregar estado das letras
                        console.log('🔄 Monitor: Nenhuma URL no display, buscando estado das letras...');
                        loadLyricsState();
                    }
                })
                .catch(err => {
                    console.error('❌ Monitor: Erro ao carregar estado do display:', err);
                    loadLyricsState(); // Fallback para estado das letras
                });
        }

        // Carrega o estado das letras (música + seção) e exibe no monitor
        function loadLyricsState() {
            console.log('🔍 Monitor: Buscando estado das letras...');
            fetch('/get_lyrics_state')
                .then(res => {
                    console.log('📡 Monitor: Resposta recebida:', res.status);
                    return res.json();
                })
                .then(state => {
                    console.log('💾 Monitor: Estado das letras carregado:', state);
                    
                    if (state.song_id) {
                        // Monta URL para a música/seção específica — host=monitor
                        // faz essa página se identificar como 'monitor' no socket,
                        // pra Modo Público/Monitor conseguir excluir/direcionar
                        // ela junto com o /monitor (ver display.js).
                        const lyricsUrl = `/lyrics/display?song_id=${state.song_id}&section=${state.section_index || 0}&host=monitor`;
                        console.log(`🎵 Monitor: Carregando iframe com URL: ${lyricsUrl}`);
                        console.log(`🎵 Monitor: iframe1 atual:`, iframe1);
                        iframe1.src = lyricsUrl;
                        console.log(`✅ Monitor: iframe1.src definido para: ${iframe1.src}`);
                        showSingleIframe();
                        console.log('✅ Monitor: showSingleIframe() chamado');
                    } else {
                        console.warn('⚠️ Monitor: Nenhuma música salva no estado');
                    }
                })
                .catch(err => console.error('❌ Monitor: Erro ao carregar estado das letras:', err));
        }

        // Carrega estado ao iniciar
        loadDisplayState();

        // Pré-carrega a próxima foto do slideshow em cache do navegador,
        // antes da troca de verdade — ver preload_image em control.js/
        // blueprints/display.py.
        socket.on('preload_image', function(data) {
            if (data.url) { new Image().src = data.url; }
        });

        // Escuta o evento 'display_image' do servidor e exibe a imagem se for válida
        // Zoom do /presenter: translate(pan%) scale(zoom), origem no centro —
        // a mesma transformação que o modal de zoom aplica na prévia. Só vale
        // pra foto que está na tela: zoom de outra foto é ignorado (não troca
        // a foto, pra não furar o Preparar/Liberar).
        socket.on('display_image_zoom', function(data) {
            if (!data || displayImage.style.display === 'none' || displayImage.getAttribute('src') !== data.image_url) return;
            window.ucApplyZoom(displayImage, data);  // static/js/zoom_fit.js
        });

        socket.on('display_image', function(data) {
            const imageUrl = data.image_url;
            if (mediaToPane(imageUrl, false)) return;
            hideVideo();
            showImage(imageUrl); // Tenta mostrar a imagem, ou oculta se não for uma imagem
        });

        // Eventos de vídeo (controlados pelo / e /presenter)
        socket.on('display_video', function(data) {
            if (mediaToPane(data.video_url, false)) return;
            playVideo(data.video_url);
        });
        socket.on('video_pause', function(data) {
            if (!displayVideo.src) return;
            if (data.paused) {
                displayVideo.pause();
            } else {
                displayVideo.play().catch(e => {
                    console.warn('Erro ao retomar, tentando mudo:', e);
                    displayVideo.muted = true;
                    displayVideo.play().catch(err => console.error('Falha ao retomar mesmo mudo:', err));
                });
            }
        });
        socket.on('video_restart', function() {
            if (!displayVideo.src) return;
            displayVideo.currentTime = 0;
            displayVideo.play().catch(e => {
                console.warn('Erro ao reiniciar, tentando mudo:', e);
                displayVideo.muted = true;
                displayVideo.play().catch(err => console.error('Falha ao reiniciar mesmo mudo:', err));
            });
        });
        socket.on('video_seek', function(data) {
            if (!displayVideo.src) return;
            const t = Number(data.time) || 0;
            try { displayVideo.currentTime = t; } catch (_) {}
        });

        // Escuta o evento 'display_two_urls' do servidor e atualiza os dois iframes
        socket.on('display_two_urls', function(data) {
            // Arquivos estáticos (imagens, vídeos) são exibidos via /img
            let u1 = data.url1 || "about:blank";
            let u2 = data.url2 || "about:blank";
            if (u1.startsWith('/static/')) u1 = '/img';
            if (u2.startsWith('/static/')) u2 = '/img';
            hideVideo(); // Tela dividida usa iframes, não o player nativo de vídeo
            iframe1.src = noMonitor(u1);
            iframe2.src = noMonitor(u2);
            showDoubleIframe();
        });
        
        // Escuta o evento para mostrar/esconder letras
        socket.on('lyrics_visibility_changed', function(data) {
            const visible = data.visible;
            console.log(`👁️ Monitor: Letras ${visible ? 'mostradas' : 'escondidas'}`);
            
            // Verifica qual iframe tem letras (contém /lyrics/display)
            const iframe1HasLyrics = iframe1.src.includes('/lyrics/display');
            const iframe2HasLyrics = iframe2.src.includes('/lyrics/display');
            
            console.log(`  iframe1 tem letras: ${iframe1HasLyrics}`);
            console.log(`  iframe2 tem letras: ${iframe2HasLyrics}`);
            
            // Esconde/mostra apenas o iframe que tem letras
            // Usa visibility para manter o espaço e posição
            if (iframe1HasLyrics) {
                iframe1.style.visibility = visible ? 'visible' : 'hidden';
            }
            if (iframe2HasLyrics) {
                iframe2.style.visibility = visible ? 'visible' : 'hidden';
            }
            
            // Se nenhum iframe tem letras, esconde o container todo
            if (!iframe1HasLyrics && !iframe2HasLyrics) {
                const container = document.querySelector('.iframe-container');
                container.style.display = visible ? 'flex' : 'none';
            }
        });

        // Monitor sincronizado com a home via banco de dados + WebSocket

        // ── Modo Monitor de Palco ────────────────────────────────────
        // Exibe conteúdo enviado só ao monitor, sem afetar o público
        socket.on('display_monitor_content', function(data) {
            const url = data.url || '';
            if (mediaToPane(url, true)) return;
            hideVideo();
            if (isVideoUrl(url)) {
                playVideo(url);
            } else if (isImageUrl(url)) {
                showImage(url);
            } else {
                iframe1.src = noMonitor(url) || 'about:blank';
                showSingleIframe();
            }
        });

        socket.on('display_monitor_video', function(data) {
            if (mediaToPane(data.video_url, true)) return;
            playVideo(data.video_url);
        });

        // ── Ticker de avisos ─────────────────────────────────────────
        function updateTicker(text) {
            const bar = document.getElementById('ticker-bar');
            const span = document.getElementById('ticker-text');
            const box = document.getElementById('iframeContainer');
            if (!text) { bar.style.display = 'none'; box.style.height = ''; return; }
            span.textContent = text;
            span.style.animationDuration = Math.max(10, text.length * 0.3) + 's';
            bar.style.display = 'block';
            // A faixa é fixa embaixo: o conteúdo (cifra, foto) encolhe pra
            // acabar em cima dela, em vez de ficar escondido por baixo. A
            // cifra refaz o tamanho da letra sozinha (display.js, resize).
            box.style.height = `calc(100% - ${bar.offsetHeight}px)`;
        }
        socket.on('ticker_update', function(data) { updateTicker(data.text || ''); });
        fetch('/api/ticker').then(r => r.json()).then(d => { if (d.active) updateTicker(d.text || ''); });

        // ── Compartilhar Tela (WebRTC viewer) ───────────────────────────────
        let _screenPc = null;
        const _iceConfig = { iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] };

        socket.on('screen_share_start', function(data) {
            socket.emit('screen_share_request', { broadcaster_sid: data.from_sid });
        });

        socket.on('screen_share_offer', async function(data) {
            _screenPc = new RTCPeerConnection(_iceConfig);
            _screenPc.onicecandidate = e => {
                if (e.candidate) socket.emit('screen_share_ice', { target_sid: data.from_sid, candidate: e.candidate });
            };
            _screenPc.ontrack = e => {
                const vid = document.getElementById('screenShareVideo');
                vid.srcObject = e.streams[0];
                vid.style.display = 'block';
            };
            await _screenPc.setRemoteDescription(new RTCSessionDescription(data.sdp));
            const answer = await _screenPc.createAnswer();
            await _screenPc.setLocalDescription(answer);
            socket.emit('screen_share_answer', { target_sid: data.from_sid, sdp: answer });
        });

        socket.on('screen_share_ice', function(data) {
            if (_screenPc) _screenPc.addIceCandidate(new RTCIceCandidate(data.candidate)).catch(()=>{});
        });

        socket.on('screen_share_stop', function() {
            const vid = document.getElementById('screenShareVideo');
            vid.style.display = 'none';
            vid.srcObject = null;
            if (_screenPc) { _screenPc.close(); _screenPc = null; }
        });
