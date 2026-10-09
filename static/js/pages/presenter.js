        function toggleMenu() {
            const menu = document.querySelector('.menu');
            menu.classList.toggle('open');
        }

        // Fecha o menu ao clicar fora dele
        document.addEventListener('click', function(event) {
            const menu = document.querySelector('.menu');
            const isClickInsideMenu = menu.contains(event.target);
            const isClickOnToggleButton = !!event.target.closest('button');

            // Se o menu estiver aberto e o clique não for dentro do menu ou no botão de toggle
            if (menu.classList.contains('open') && !isClickInsideMenu && !isClickOnToggleButton) {
                menu.classList.remove('open'); // Fecha o menu
            }
        });

        
        const socket = io();

        socket.emit('identify', { role: 'presenter' });

        let blackoutActive = false;
        function toggleBlackout() {
            blackoutActive = !blackoutActive;
            socket.emit('blackout', { active: blackoutActive });
            const btn = document.getElementById('blackoutBtn');
            btn.classList.toggle('active', blackoutActive);
            btn.innerHTML = blackoutActive
                ? '<i class="fas fa-sun"></i> Voltar a imagem'
                : '<i class="fas fa-moon"></i> Tela preta';
        }

        socket.on('atualizar_foto', function(data) {
            document.getElementById("foto-atual-iframe").src = data.foto_atual;
        });

        function getCurrentFolder() {
            return document.getElementById('folderSelect').value;
        }

        function loadFolders() {
            fetch('/api/image_folders')
                .then(res => res.json())
                .then(folders => {
                    const select = document.getElementById('folderSelect');
                    const saved = localStorage.getItem('presenterFolder') || 'Geral';
                    select.innerHTML = '';
                    folders.forEach(f => {
                        const opt = document.createElement('option');
                        opt.value = f;
                        opt.textContent = f;
                        if (f === saved) opt.selected = true;
                        select.appendChild(opt);
                    });
                    loadImageGallery();
                });
        }

        function onFolderChange() {
            localStorage.setItem('presenterFolder', getCurrentFolder());
            loadImageGallery();
        }

        function loadImageGallery() {
            const folder = getCurrentFolder();
            fetch(`/lista-fotos?folder=${encodeURIComponent(folder)}`)
                .then(response => response.json())
                .then(data => {
                    const gallery = document.getElementById('imageGallery');
                    gallery.innerHTML = '';
                    const items = data.fotos;
                    items.sort((a, b) => a.url.localeCompare(b.url, undefined, { numeric: true, sensitivity: 'base' }))
                        .forEach((item, index) => {
                            const imgContainer = document.createElement('div');
                            imgContainer.className = 'image-container';
                            if (item.type === 'video') {
                                imgContainer.innerHTML = `
                                    <div class="thumb-wrap">
                                        <video src="${item.url}" preload="metadata"
                                            style="width:100%; aspect-ratio:16/10; object-fit:cover; border-radius:8px; display:block; pointer-events:none;"
                                            muted playsinline></video>
                                        <div onclick="showVideoInMonitor('${item.url}')" data-video-url="${item.url}"
                                             style="position:absolute; inset:0; cursor:pointer; border-radius:10px;
                                                    display:flex; align-items:center; justify-content:center;
                                                    background:rgba(0,0,0,0.2); transition:background 0.2s;"
                                             onmouseenter="this.style.background='rgba(0,0,0,0.45)'"
                                             onmouseleave="this.style.background='rgba(0,0,0,0.2)'">
                                            <div class="video-play-icon" style="background:rgba(0,0,0,0.6); border-radius:50%; width:44px; height:44px;
                                                        display:flex; align-items:center; justify-content:center; font-size:22px;">▶️</div>
                                        </div>
                                        <button class="video-restart-btn" data-restart-url="${item.url}"
                                                onclick="event.stopPropagation(); restartVideoInMonitor('${item.url}')"
                                                title="Reiniciar vídeo"
                                                style="display:none; position:absolute; top:8px; right:8px;
                                                       background:rgba(0,0,0,0.65); color:white; border:none;
                                                       border-radius:50%; width:36px; height:36px; cursor:pointer;
                                                       font-size:18px; align-items:center; justify-content:center; z-index:2;">⏮️</button>
                                    </div>
                                    <div class="video-progress-wrap" data-progress-url="${item.url}"
                                         style="display:none; margin-top:6px; width:100%;">
                                        <div class="video-progress-bar"
                                             onclick="seekVideoFromBar(event, '${item.url}')"
                                             style="position:relative; height:14px; background:#555; border-radius:7px;
                                                    cursor:pointer; overflow:hidden; touch-action:none; user-select:none;">
                                            <div class="video-progress-fill"
                                                 style="height:100%; width:0%; background:#2c7be5; transition:width 0.2s linear;"></div>
                                        </div>
                                        <div class="video-progress-time"
                                             style="display:flex; justify-content:space-between; font-size:0.75em; color:#aaa; margin-top:3px;">
                                            <span class="vp-current">0:00</span>
                                            <span class="vp-duration">0:00</span>
                                        </div>
                                    </div>
                                `;
                            } else {
                                imgContainer.innerHTML = `
                                    <div class="thumb-wrap">
                                        <img src="${item.url}" alt="Imagem ${index + 1}" onclick="resetView('${item.url}')">
                                        <button type="button"
                                                class="zoom-btn"
                                                aria-label="Abrir zoom"
                                                onclick="openZoomModal('${item.url}')"><i class="fas fa-magnifying-glass-plus"></i></button>
                                    </div>
                                `;
                            }
                            gallery.appendChild(imgContainer);
                        });
                    markGallery();
                    if (typeof updateVideoOverlayIcons === 'function') updateVideoOverlayIcons();
                })
                .catch(error => console.error('Erro ao carregar as imagens:', error));
        }

        function uploadImages() {
            const fileInput = document.getElementById('fileInput');
            if (!fileInput.files.length) return alert('Selecione arquivos primeiro.');
            const formData = new FormData();
            for (let i = 0; i < fileInput.files.length; i++) {
                formData.append('images', fileInput.files[i]);
            }
            formData.append('folder', getCurrentFolder());

            const wrap = document.getElementById('uploadProgressWrap');
            const bar = document.getElementById('uploadProgressBar');
            const pctText = document.getElementById('uploadProgressText');
            const statusText = document.getElementById('uploadStatusText');
            const btn = document.getElementById('uploadBtn');

            wrap.style.display = 'block';
            bar.style.width = '0%';
            pctText.textContent = '0%';
            statusText.textContent = 'Enviando...';
            btn.disabled = true;
            btn.style.opacity = '0.5';

            const xhr = new XMLHttpRequest();
            xhr.open('POST', '/upload');

            xhr.upload.onprogress = function(e) {
                if (e.lengthComputable) {
                    const pct = Math.round((e.loaded / e.total) * 100);
                    bar.style.width = pct + '%';
                    pctText.textContent = pct + '%';
                    const mb = (e.loaded / 1048576).toFixed(1);
                    const totalMb = (e.total / 1048576).toFixed(1);
                    statusText.textContent = `${mb} MB / ${totalMb} MB`;
                }
            };

            xhr.onload = function() {
                btn.disabled = false;
                btn.style.opacity = '1';
                if (xhr.status === 200) {
                    const data = JSON.parse(xhr.responseText);
                    if (data.status === 'success') {
                        bar.style.width = '100%';
                        bar.style.background = 'linear-gradient(90deg,#4caf50,#81c784)';
                        pctText.textContent = '100%';
                        statusText.textContent = '✅ Enviado! Processando imagens...';
                        loadImageGallery();
                        fileInput.value = '';
                        setTimeout(() => { wrap.style.display = 'none'; }, 3000);
                    }
                } else {
                    bar.style.background = '#e53935';
                    statusText.textContent = '❌ Erro no envio.';
                }
            };

            xhr.onerror = function() {
                btn.disabled = false;
                btn.style.opacity = '1';
                bar.style.background = '#e53935';
                statusText.textContent = '❌ Erro de conexão.';
            };

            xhr.send(formData);
        }

        // Estado do vídeo atualmente no monitor (/img)
        let currentVideoUrl = null;
        let currentVideoPaused = false;

        function showVideoInMonitor(videoUrl) {
            if (currentVideoUrl === videoUrl) {
                // Mesmo vídeo: alterna pausa/retomada
                currentVideoPaused = !currentVideoPaused;
                console.log(currentVideoPaused ? '⏸️ Pausando vídeo:' : '▶️ Retomando vídeo:', videoUrl);
                socket.emit('toggle_video_pause', { paused: currentVideoPaused });
            } else {
                // Outro vídeo: troca para o novo e marca como tocando
                console.log('🎬 Enviando show_video:', videoUrl);
                currentVideoUrl = videoUrl;
                currentVideoPaused = false;
                socket.emit('show_video', { video_url: videoUrl });
            }
            updateVideoOverlayIcons();
            if (typeof ensureProgressPolling === 'function') ensureProgressPolling();
        }

        function updateVideoOverlayIcons() {
            document.querySelectorAll('[data-video-url]').forEach(el => {
                const url = el.getAttribute('data-video-url');
                const icon = el.querySelector('.video-play-icon');
                if (!icon) return;
                icon.textContent = (url === currentVideoUrl && !currentVideoPaused) ? '⏸️' : '▶️';
            });
            document.querySelectorAll('.video-restart-btn').forEach(btn => {
                const url = btn.getAttribute('data-restart-url');
                btn.style.display = (url === currentVideoUrl) ? 'flex' : 'none';
            });
            // Mostra barra de progresso apenas no vídeo atual
            document.querySelectorAll('.video-progress-wrap').forEach(wrap => {
                const url = wrap.getAttribute('data-progress-url');
                wrap.style.display = (url === currentVideoUrl) ? 'block' : 'none';
                if (url === currentVideoUrl) {
                    // Preenche duração a partir do <video> do thumbnail, se carregado
                    const container = wrap.parentElement;
                    const vidEl = container && container.querySelector('video');
                    if (vidEl) {
                        const setDur = () => {
                            const dur = vidEl.duration;
                            if (dur && isFinite(dur)) {
                                const durSpan = wrap.querySelector('.vp-duration');
                                if (durSpan) durSpan.textContent = formatTime(dur);
                                wrap.setAttribute('data-duration', dur);
                            }
                        };
                        if (vidEl.readyState >= 1) setDur();
                        else vidEl.addEventListener('loadedmetadata', setDur, { once: true });
                    }
                }
            });
        }

        function restartVideoInMonitor(videoUrl) {
            console.log('⏮️ Reiniciando vídeo:', videoUrl);
            currentVideoUrl = videoUrl;
            currentVideoPaused = false;
            updateVideoOverlayIcons();
            // Reset visual imediato da barra de progresso
            const wrap = document.querySelector(`.video-progress-wrap[data-progress-url="${videoUrl}"]`);
            if (wrap) _updateBarUI(wrap, 0, 0);
            socket.emit('restart_video', { video_url: videoUrl });
        }

        function formatTime(s) {
            if (!isFinite(s) || s < 0) s = 0;
            const m = Math.floor(s / 60);
            const sec = Math.floor(s % 60).toString().padStart(2, '0');
            return `${m}:${sec}`;
        }

        // Estado global de arrasto da barra (mouse ou toque)
        let _dragging = false;
        let _draggingUrl = null;

        function _computePctFromEvent(bar, event) {
            const rect = bar.getBoundingClientRect();
            const x = (event.clientX !== undefined) ? event.clientX
                    : (event.touches && event.touches[0] ? event.touches[0].clientX : 0);
            return Math.min(1, Math.max(0, (x - rect.left) / rect.width));
        }

        function _updateBarUI(wrap, pct, target) {
            const fill = wrap.querySelector('.video-progress-fill');
            if (fill) fill.style.width = (pct * 100) + '%';
            const cur = wrap.querySelector('.vp-current');
            if (cur) cur.textContent = formatTime(target);
        }

        // Click simples (sem arrasto): mantém compat com o onclick antigo
        function seekVideoFromBar(event, videoUrl) {
            if (_dragging) return; // se foi um drag, o pointerup já cuidou
            if (videoUrl !== currentVideoUrl) return;
            const wrap = document.querySelector(`.video-progress-wrap[data-progress-url="${videoUrl}"]`);
            if (!wrap) return;
            const duration = Number(wrap.getAttribute('data-duration')) || 0;
            if (!duration) return;
            const bar = wrap.querySelector('.video-progress-bar');
            const pct = _computePctFromEvent(bar, event);
            const target = pct * duration;
            _updateBarUI(wrap, pct, target);
            socket.emit('seek_video', { time: target });
        }

        // Arrasto: Pointer Events cobrem mouse + toque
        document.addEventListener('pointerdown', (e) => {
            const bar = e.target.closest('.video-progress-bar');
            if (!bar) return;
            const wrap = bar.closest('.video-progress-wrap');
            const url = wrap && wrap.getAttribute('data-progress-url');
            if (!url || url !== currentVideoUrl) return;
            _dragging = true;
            _draggingUrl = url;
            try { bar.setPointerCapture(e.pointerId); } catch (_) {}
            const duration = Number(wrap.getAttribute('data-duration')) || 0;
            if (duration) {
                const pct = _computePctFromEvent(bar, e);
                _updateBarUI(wrap, pct, pct * duration);
            }
        });
        document.addEventListener('pointermove', (e) => {
            if (!_dragging || !_draggingUrl) return;
            const wrap = document.querySelector(`.video-progress-wrap[data-progress-url="${_draggingUrl}"]`);
            if (!wrap) return;
            const duration = Number(wrap.getAttribute('data-duration')) || 0;
            if (!duration) return;
            const bar = wrap.querySelector('.video-progress-bar');
            const pct = _computePctFromEvent(bar, e);
            _updateBarUI(wrap, pct, pct * duration);
            e.preventDefault();
        }, { passive: false });
        const _finishDrag = (e) => {
            if (!_dragging || !_draggingUrl) return;
            const wrap = document.querySelector(`.video-progress-wrap[data-progress-url="${_draggingUrl}"]`);
            _dragging = false;
            const url = _draggingUrl;
            _draggingUrl = null;
            if (!wrap) return;
            const duration = Number(wrap.getAttribute('data-duration')) || 0;
            if (!duration) return;
            const bar = wrap.querySelector('.video-progress-bar');
            const pct = _computePctFromEvent(bar, e);
            const target = pct * duration;
            _updateBarUI(wrap, pct, target);
            console.log(`⏩ Drag-seek para ${target.toFixed(2)}s`);
            socket.emit('seek_video', { time: target });
        };
        document.addEventListener('pointerup', _finishDrag);
        document.addEventListener('pointercancel', _finishDrag);

        // Sincronização de estado via Socket.IO (sem polling).
        // O servidor emite estes eventos para todos os clientes; assim o presenter
        // se mantém atualizado mesmo quando outra rota controla o vídeo.
        socket.on('display_video', function(data) {
            currentVideoUrl = data.video_url;
            currentVideoPaused = false;
            updateVideoOverlayIcons();
            ensureProgressPolling();
        });
        socket.on('display_image', function(data) {
            currentVideoUrl = null;
            currentVideoPaused = false;
            updateVideoOverlayIcons();
            const url = (data && data.image_url) || '';
            if (isStaticMedia(url)) {
                liveImageUrl = url;
                if (stagedImageUrl === url) stagedImageUrl = null;
            } else if (url !== '/img') {
                liveImageUrl = null;  // telão foi pra letra, relógio etc.
            }
            markGallery();
        });
        socket.on('display_two_urls', function() {
            liveImageUrl = null;  // tela dividida no telão
            markGallery();
        });
        socket.on('content_discarded', function(data) {
            if (data && data.kind === 'image') {
                stagedImageUrl = null;
                markGallery();
            }
        });
        socket.on('video_pause', function(data) {
            currentVideoPaused = !!data.paused;
            updateVideoOverlayIcons();
        });
        socket.on('video_restart', function() {
            const wrap = currentVideoUrl
                ? document.querySelector(`.video-progress-wrap[data-progress-url="${currentVideoUrl}"]`)
                : null;
            if (wrap) _updateBarUI(wrap, 0, 0);
        });

        // Polling apenas para atualização suave da barra de progresso enquanto há
        // vídeo tocando. Para quando: não há vídeo, aba oculta, ou usuário arrasta.
        let _progressPollId = null;
        function ensureProgressPolling() {
            if (_progressPollId) return;
            if (!currentVideoUrl) return;
            if (document.hidden) return;
            _progressPollId = setInterval(() => {
                if (_dragging) return;
                if (!currentVideoUrl) { stopProgressPolling(); return; }
                fetch('/video_state').then(r => r.json()).then(state => {
                    if (!state.url) {
                        // Servidor não tem mais vídeo (algum cliente trocou para imagem)
                        currentVideoUrl = null;
                        currentVideoPaused = false;
                        updateVideoOverlayIcons();
                        stopProgressPolling();
                        return;
                    }
                    // Mantém estado sincronizado por segurança
                    currentVideoPaused = !!state.paused;
                    const wrap = document.querySelector(`.video-progress-wrap[data-progress-url="${state.url}"]`);
                    if (!wrap) return;
                    const duration = Number(wrap.getAttribute('data-duration')) || 0;
                    if (!duration) return;
                    const pct = Math.min(1, Math.max(0, state.position / duration));
                    _updateBarUI(wrap, pct, state.position);
                }).catch(() => {});
            }, 500);
        }
        function stopProgressPolling() {
            if (_progressPollId) {
                clearInterval(_progressPollId);
                _progressPollId = null;
            }
        }
        // Pausa polling quando aba não está visível (economia de bateria/rede)
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) stopProgressPolling();
            else ensureProgressPolling();
        });
        // Sincroniza uma vez ao carregar (caso vídeo já esteja tocando)
        fetch('/video_state').then(r => r.json()).then(state => {
            if (state.url) {
                currentVideoUrl = state.url;
                currentVideoPaused = !!state.paused;
                updateVideoOverlayIcons();
                ensureProgressPolling();
            }
        }).catch(() => {});

        // Extrai um nome legível da URL da foto pro card de "preparado" no
        // /control (ex: "/static/imagens/festa.jpg" -> "festa.jpg").
        function _photoLabel(imageUrl) {
            try {
                const decoded = decodeURIComponent(imageUrl);
                return decoded.split('/').pop() || decoded;
            } catch (e) {
                return imageUrl;
            }
        }

        // Na galeria: amarelo = preparada aqui (espera o /control liberar),
        // vermelho = no ar (igual ao /control). Antes adicionava a classe
        // 'selected', que não tinha estilo, e comparava img.src (absoluto,
        // com %20) com a URL relativa — nunca marcava nada.
        let liveImageUrl = null;
        let stagedImageUrl = null;

        function markGallery() {
            document.querySelectorAll('#imageGallery img').forEach(img => {
                const url = img.getAttribute('src');
                const live = !!liveImageUrl && url === liveImageUrl;
                img.classList.toggle('selecionada', live);
                img.closest('.thumb-wrap').classList.toggle('is-preparada', !live && url === stagedImageUrl);
            });
        }

        function isStaticMedia(url) {
            return !!url && (url.startsWith('/static/') || /\.(jpe?g|png|gif|bmp|webp)(\?.*)?$/i.test(url));
        }

        function showImageInMonitor(imageUrl) {
            stagedImageUrl = imageUrl;
            markGallery();
            // Vídeo deixou de estar no monitor: zera estado e atualiza ícones para ▶️
            currentVideoUrl = null;
            currentVideoPaused = false;
            updateVideoOverlayIcons();
            // Preparar, não mandar ao ar direto — a mudança de verdade só
            // acontece quando o /control liberar (ver blueprints/display.py:
            // stage_content/release_staged_content). Vídeo continua
            // instantâneo de propósito (showVideoInMonitor, sem alteração).
            socket.emit('stage_content', {
                kind: 'image',
                payload: { image_url: imageUrl },
                label: _photoLabel(imageUrl),
            });
        }

        function resetView(imageUrl) {
            // Seleciona a imagem (preparar) e zera zoom/pan só localmente
            // aqui no presenter. NÃO emite show_image_zoom aqui: o handler
            // display_image_zoom no /img troca a imagem exibida sozinho
            // quando a URL muda (loadImage()), o que ia ao ar a foto na
            // hora — exatamente o que preparar deveria evitar. Zoom/pan
            // via slider continua instantâneo (ver zoomSlider abaixo),
            // mas só faz sentido ajustar depois que a foto já estiver no
            // ar de verdade (liberada pelo /control).
            showImageInMonitor(imageUrl);
            panOffset = { x: 0, y: 0 };
            zoomOrigin = { x: 50, y: 50 };
            zoomSlider.value = 1;
            zoomValueLabel.textContent = '1.0x';
            applyLocalTransform(1, panOffset);
        }

        // ===== Modal de Zoom =====
        let zoomModal;
        let zoomImage;
        let zoomSlider;
        let zoomValueLabel;
        let zoomCurrentImageUrl = null;
        let zoomEmitTimeout = null;
        let zoomOrigin = { x: 50, y: 50 }; // porcentagem
        let panOffset = { x: 0, y: 0 }; // em %
        let isDragging = false;
        let dragStart = { x: 0, y: 0 };
        let panBase = { x: 0, y: 0 };
        const DRAG_MULTIPLIER = 1.0; // sensibilidade em porcentagem do tamanho da imagem

        // Suporte a pinch (multi-touch)
        const pointers = new Map();
        let pinchStartDistance = null;
        let pinchStartZoom = 1;
        let pinchCenter = null;

        function ensureZoomElements() {
            if (zoomModal) return;
            zoomModal = document.createElement('div');
            zoomModal.id = 'zoom-modal';
            zoomModal.innerHTML = `
                <div class="zoom-backdrop" onclick="closeZoomModal()"></div>
                <div class="zoom-content">
                    <button type="button" class="zoom-close" onclick="closeZoomModal()" aria-label="Fechar"><i class="fas fa-xmark"></i></button>
                    <div class="zoom-image-wrapper">
                        <img id="zoom-image" src="" alt="Zoom preview" title="Clique no ponto que deseja aproximar. Clique duplo ou toque duplo para reset.">
                    </div>
                    <div class="zoom-controls">
                        <label for="zoom-range">Zoom: <span id="zoom-value">1.0x</span></label>
                        <input type="range" id="zoom-range" min="1" max="3" step="0.1" value="1">
                        <button type="button" class="zoom-apply" onclick="closeZoomModal()">Sair do zoom</button>
                    </div>
                </div>
            `;
            document.body.appendChild(zoomModal);
            zoomImage = document.getElementById('zoom-image');
            zoomSlider = document.getElementById('zoom-range');
            zoomValueLabel = document.getElementById('zoom-value');
            zoomSlider.addEventListener('input', () => {
                const val = parseFloat(zoomSlider.value);
                zoomValueLabel.textContent = `${val.toFixed(1)}x`;
                applyLocalTransform(val, panOffset);
                // Emite em tempo real com debounce curto
                if (zoomEmitTimeout) clearTimeout(zoomEmitTimeout);
                zoomEmitTimeout = setTimeout(() => {
                    if (zoomCurrentImageUrl) {
                        socket.emit('show_image_zoom', { image_url: zoomCurrentImageUrl, zoom: val, origin: zoomOrigin, pan: panOffset });
                    }
                }, 80);
            });

            // Define origem do zoom ao clicar na imagem
            // Clique único: define origem
            zoomImage.addEventListener('click', (ev) => {
                const rect = zoomImage.getBoundingClientRect();
                const x = ((ev.clientX - rect.left) / rect.width) * 100;
                const y = ((ev.clientY - rect.top) / rect.height) * 100;
                zoomOrigin = { x, y };
                applyLocalTransform(parseFloat(zoomSlider.value), panOffset);
                if (zoomCurrentImageUrl) {
                    socket.emit('show_image_zoom', { image_url: zoomCurrentImageUrl, zoom: parseFloat(zoomSlider.value), origin: zoomOrigin, pan: panOffset });
                }
            });

            // Duplo clique/toque para resetar zoom/pan e refletir no /img
            zoomImage.addEventListener('dblclick', () => {
                resetZoomPan();
            });
            zoomImage.addEventListener('touchend', (ev) => {
                if (ev.detail === 2) {
                    resetZoomPan();
                }
            });

            // Toque/mouse move segurado para origem dinâmica (experiência mobile)
            zoomImage.addEventListener('pointerdown', (ev) => {
                isDragging = true;
                dragStart = { x: ev.clientX, y: ev.clientY };
                panBase = { ...panOffset };
                zoomImage.setPointerCapture(ev.pointerId || 0);
                zoomImage.style.cursor = 'grabbing';

                // Armazena pointer para pinch
                pointers.set(ev.pointerId, { x: ev.clientX, y: ev.clientY });
                if (pointers.size === 2) {
                    const pts = Array.from(pointers.values());
                    pinchStartDistance = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y);
                    pinchStartZoom = parseFloat(zoomSlider.value) || 1;
                    pinchCenter = {
                        x: (pts[0].x + pts[1].x) / 2,
                        y: (pts[0].y + pts[1].y) / 2
                    };
                }
            });
            zoomImage.addEventListener('pointerup', (ev) => {
                isDragging = false;
                zoomImage.releasePointerCapture(ev.pointerId || 0);
                zoomImage.style.cursor = 'grab';
                pointers.delete(ev.pointerId);
                if (pointers.size < 2) {
                    pinchStartDistance = null;
                }
            });
            zoomImage.addEventListener('pointerleave', () => {
                isDragging = false;
                zoomImage.style.cursor = 'grab';
            });
            zoomImage.addEventListener('pointermove', (ev) => {
                // Atualiza pointer
                pointers.set(ev.pointerId, { x: ev.clientX, y: ev.clientY });

                // Pinch (dois dedos)
                if (pointers.size >= 2 && pinchStartDistance) {
                    ev.preventDefault();
                    const pts = Array.from(pointers.values());
                    const dist = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y);
                    if (dist > 0) {
                        const scale = dist / pinchStartDistance;
                        const newZoom = Math.min(3, Math.max(1, pinchStartZoom * scale));
                        zoomSlider.value = newZoom;
                        zoomValueLabel.textContent = `${newZoom.toFixed(1)}x`;
                        // Centro do pinch vira origem
                        const rect = zoomImage.getBoundingClientRect();
                        const centerX = ((pts[0].x + pts[1].x) / 2 - rect.left) / rect.width * 100;
                        const centerY = ((pts[0].y + pts[1].y) / 2 - rect.top) / rect.height * 100;
                        zoomOrigin = { x: centerX, y: centerY };
                        applyLocalTransform(newZoom, panOffset);
                        if (zoomCurrentImageUrl) {
                            socket.emit('show_image_zoom', { image_url: zoomCurrentImageUrl, zoom: newZoom, origin: zoomOrigin, pan: panOffset });
                        }
                    }
                    return;
                }

                // Pan (1 dedo)
                if (!isDragging) return;
                ev.preventDefault();
                const rect = zoomImage.getBoundingClientRect();
                const dx = ((ev.clientX - dragStart.x) / rect.width) * 100 * DRAG_MULTIPLIER;
                const dy = ((ev.clientY - dragStart.y) / rect.height) * 100 * DRAG_MULTIPLIER;
                panOffset = { x: panBase.x + dx, y: panBase.y + dy };
                // Limita para evitar perder a imagem (%)
                panOffset.x = Math.max(-150, Math.min(150, panOffset.x));
                panOffset.y = Math.max(-150, Math.min(150, panOffset.y));
                applyLocalTransform(parseFloat(zoomSlider.value), panOffset);
                if (zoomCurrentImageUrl) {
                    socket.emit('show_image_zoom', { image_url: zoomCurrentImageUrl, zoom: parseFloat(zoomSlider.value), origin: zoomOrigin, pan: panOffset });
                }
                console.log('drag pan', panOffset);
            });
        }

        function openZoomModal(imageUrl) {
            ensureZoomElements();
            zoomCurrentImageUrl = imageUrl;
            zoomImage.src = imageUrl;
            zoomSlider.value = 1;
            zoomValueLabel.textContent = '1.0x';
            zoomOrigin = { x: 50, y: 50 };
            panOffset = { x: 0, y: 0 };
            applyLocalTransform(1, panOffset);
            zoomModal.classList.add('open');
        }

        function closeZoomModal() {
            if (!zoomModal) return;
            zoomModal.classList.remove('open');
            zoomCurrentImageUrl = null;
        }

        function applyZoom() {
            if (!zoomCurrentImageUrl) return;
            const zoom = parseFloat(zoomSlider.value) || 1;
            // Emite evento dedicado de zoom com origem
            socket.emit('show_image_zoom', { image_url: zoomCurrentImageUrl, zoom, origin: zoomOrigin, pan: panOffset });
            closeZoomModal();
        }

        function resetZoomPan() {
            panOffset = { x: 0, y: 0 };
            zoomSlider.value = 1;
            zoomValueLabel.textContent = '1.0x';
            applyLocalTransform(1, panOffset);
            if (zoomCurrentImageUrl) {
                socket.emit('show_image_zoom', { image_url: zoomCurrentImageUrl, zoom: 1, origin: { x: 50, y: 50 }, pan: { x: 0, y: 0 } });
            }
        }

        function applyLocalTransform(val, pan) {
            zoomImage.style.transformOrigin = `${zoomOrigin.x}% ${zoomOrigin.y}%`;
            zoomImage.style.transform = `translate(${pan.x}%, ${pan.y}%) scale(${val})`;
        }

        window.onload = () => {
            // Foto que já está no ar ao abrir a página
            fetch('/api/current-display')
                .then(r => r.json())
                .then(d => {
                    if (d.mode === 'image' && d.is_static) { liveImageUrl = d.image_url; markGallery(); }
                })
                .catch(() => {});
            loadFolders();
        };
