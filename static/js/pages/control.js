 document.addEventListener('DOMContentLoaded', function () {
    setupMenuToggle();
    setupPreventMenuClose();
    loadUrls();
    loadFolders();
    loadDisplayState(); // Carrega estado salvo ao iniciar
    fetch('/api/countdown/config')
        .then(function(r) { return r.json(); })
        .then(function(cfg) {
            if (cfg.label) document.getElementById('countdownLabel').value = cfg.label;
        })
        .catch(function() {});
    fetch('/api/ticker')
        .then(function(r) { return r.json(); })
        .then(function(d) {
            if (d.text) document.getElementById('tickerText').value = d.text;
        })
        .catch(function() {});
});

const socket = io.connect(`${window.location.protocol}//${window.location.host}`);

// Escuta eventos WebSocket para sincronizar iframes entre PCs
socket.on('display_image', function(data) {
    console.log('📡 Recebido display_image de outro PC:', data);
    
    // Se a URL é uma rota (começa com /), atualiza os iframes
    // Se é um caminho de imagem estática, NÃO atualiza (deixa /img receber via WebSocket)
    if (data.image_url.startsWith('/') && !data.image_url.startsWith('/static/')) {
        updateIframes(data.image_url, '');
    }
    // Se for imagem estática, o /img já vai receber via WebSocket e exibir
});

// Escuta o evento para mostrar/esconder letras
socket.on('lyrics_visibility_changed', function(data) {
    const visible = data.visible;
    console.log(`👁️ Home: Letras ${visible ? 'mostradas' : 'escondidas'}`);
    
    const iframe1 = document.getElementById('iframe1');
    const iframe2 = document.getElementById('iframe2');
    
    if (!iframe1 || !iframe2) {
        console.warn('⚠️ Home: Iframes não encontrados');
        return;
    }
    
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
});

// Função para abrir/fechar menu em mobile
function toggleMenu() {
    const menu = document.querySelector('.menu');
    const overlay = document.querySelector('.menu-overlay');
    
    menu.classList.toggle('active');
    overlay.classList.toggle('active');
}

function setupMenuToggle() {
    const menuItems = document.querySelectorAll('.menu > ul > li');
    menuItems.forEach(menuItem => {
        menuItem.addEventListener('click', function () {
            const isOpen = menuItem.classList.contains('open');
            menuItems.forEach(item => item.classList.remove('open'));
            if (!isOpen) menuItem.classList.add('open');
        });
    });
}

function setupPreventMenuClose() {
    document.querySelectorAll('input, textarea, button, form, img, select, span, hr, #imageGallery')
        .forEach(input => input.addEventListener('click', event => event.stopPropagation()));
}

function sendUrl(urlNumber) {
    const fixedRoutes = {
        4: "/lyrics/display",
        5: "/clock",
        6: "/img",
        7: "/bible/display",
        8: "/lyrics/display/public"
    };

    const urlInput = fixedRoutes[urlNumber] || document.getElementById(`url${urlNumber}`)?.value;
    if (!urlInput) return console.error("URL não definida ou vazia.");

    console.warn('⚠️ sendUrl: Mostrando apenas 1 URL. Se quiser manter 2 URLs (ex: Cifra + Relógio), use o botão "URL 1/2"');
    socket.emit('show_image', { image_url: urlInput, exclude_monitor: publicOnlyMode });
    updateIframes(urlInput, '');
}

function showTwoUrls(urlNum1, urlNum2) {
    const fixedRoutes = {
        4: "/lyrics/display",
        5: "/clock",
        6: "/img",
        7: "/bible/display",
        8: "/lyrics/display/public"
    };

    const url1 = fixedRoutes[urlNum1] || document.getElementById(`url${urlNum1}`)?.value;
    const url2 = fixedRoutes[urlNum2] || document.getElementById(`url${urlNum2}`)?.value;
    if (!url1 || !url2) return console.error("Uma ou ambas as URLs não foram definidas.");

    socket.emit('show_two_urls', { url1, url2, exclude_monitor: publicOnlyMode });
    updateIframes(url1, url2);
}

function updateIframes(url1, url2) {
    const iframe1 = document.getElementById('iframe1');
    const iframe2 = document.getElementById('iframe2');
    // Arquivos estáticos (imagens, vídeos) são exibidos via /img,
    // que sabe carregar e tocar o conteúdo correto.
    if (url1 && url1.startsWith('/static/')) url1 = '/img';
    if (url2 && url2.startsWith('/static/')) url2 = '/img';
    iframe1.src = url1;
    iframe2.src = url2;
    iframe1.style.width = url2 ? '50%' : '100%';
    iframe2.style.width = url2 ? '50%' : '0';
}

function saveUrls() {
    const urls = {
        url1: document.getElementById('url1').value,
        url2: document.getElementById('url2').value,
        url3: document.getElementById('url3').value
    };
    fetch('/save_urls', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(urls)
    }).then(res => res.json())
      .then(data => data.status === 'success' && alert('URLs salvas com sucesso!'));
}

function loadUrls() {
    fetch('/load_urls')
        .then(res => res.json())
        .then(urls => {
            document.getElementById('url1').value = urls.url1;
            document.getElementById('url2').value = urls.url2;
            document.getElementById('url3').value = urls.url3;
        });
}

// Carrega o estado salvo do display ao iniciar
function loadDisplayState() {
    fetch('/get_display_state')
        .then(res => res.json())
        .then(state => {
            console.log('💾 Estado carregado do banco:', state);
            if (state.url1 || state.url2) {
                let url1 = state.url1;
                let url2 = state.url2;
                // Imagens estáticas são exibidas via /img (que carrega a última imagem salva)
                if (url1 && url1.startsWith('/static/')) url1 = '/img';
                if (url2 && url2.startsWith('/static/')) url2 = '/img';
                updateIframes(url1, url2);
            }
        })
        .catch(err => console.error('❌ Erro ao carregar estado:', err));
}

function getCurrentFolder() {
    return document.getElementById('folderSelect').value;
}

function loadFolders() {
    fetch('/api/image_folders')
        .then(res => res.json())
        .then(folders => {
            const select = document.getElementById('folderSelect');
            const saved = localStorage.getItem('controlFolder') || 'Geral';
            select.innerHTML = '';
            folders.forEach(f => {
                const opt = document.createElement('option');
                opt.value = f;
                opt.textContent = f;
                if (f === saved) opt.selected = true;
                select.appendChild(opt);
            });
            onFolderChange();
        });
}

function onFolderChange() {
    const folder = getCurrentFolder();
    localStorage.setItem('controlFolder', folder);
    document.getElementById('deleteFolderBtn').style.display = folder === 'Geral' ? 'none' : 'inline-block';
    if (selectMode) toggleSelectMode();
    loadImageGallery();
}

function promptNewFolder() {
    const name = prompt('Nome da nova pasta:');
    if (!name || !name.trim()) return;
    fetch('/api/image_folders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name.trim() })
    }).then(res => res.json())
      .then(data => {
          if (data.status === 'success') {
              loadFolders();
              setTimeout(() => {
                  document.getElementById('folderSelect').value = data.name;
                  onFolderChange();
              }, 300);
          } else {
              alert('Erro: ' + data.message);
          }
      });
}

function deleteCurrentFolder() {
    const folder = getCurrentFolder();
    if (folder === 'Geral') return;
    if (!confirm(`Excluir a pasta "${folder}" e todas as imagens dentro dela?`)) return;
    fetch(`/api/image_folders/${encodeURIComponent(folder)}`, { method: 'DELETE' })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'success') {
                alert('Pasta excluída!');
                document.getElementById('folderSelect').value = 'Geral';
                loadFolders();
            } else {
                alert('Erro: ' + data.message);
            }
        });
}

function uploadImages() {
    const fileInput = document.getElementById('fileInput');
    if (!fileInput.files.length) return alert('Selecione arquivos primeiro.');
    const formData = new FormData();
    [...fileInput.files].forEach(file => formData.append('images', file));
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

function loadImageGallery() {
    const folder = getCurrentFolder();
    fetch(`/lista-fotos?folder=${encodeURIComponent(folder)}`)
        .then(res => res.json())
        .then(data => {
            const items = (data.fotos || []).slice()
                .sort((a, b) => a.url.localeCompare(b.url, undefined, { numeric: true, sensitivity: 'base' }));
            _galleryItems = items.map(i => ({ url: i.url, type: i.type }));
            stopSlideshow();
            const gallery = document.getElementById('imageGallery');
            gallery.innerHTML = '';
            items.forEach((item, index) => {
                const imgContainer = document.createElement('div');
                imgContainer.className = 'image-container';
                const url = item.url;
                const isVideo = item.type === 'video';
                const name = decodeURIComponent(url.split('/').pop());

                if (selectMode) {
                    const isSelected = selectedImages.has(name);
                    if (isSelected) imgContainer.classList.add('selected-for-delete');
                    if (isVideo) {
                        imgContainer.innerHTML = `
                            <div onclick="toggleImageSelection('${url}', this.closest('.image-container'))"
                                 style="position:relative; display:block; cursor:pointer; width:100%;">
                                <video src="${url}" preload="metadata" muted playsinline
                                    style="max-width:100%; height:auto; border-radius:6px; display:block; pointer-events:none;"></video>
                                <div style="position:absolute; inset:0; border-radius:6px;
                                            background:${isSelected ? 'rgba(229,57,53,0.25)' : 'rgba(0,0,0,0.05)'};
                                            display:flex; align-items:center; justify-content:center; font-size:32px;">
                                    ${isSelected ? '✔' : '🎬'}
                                </div>
                            </div>
                            <div style="text-align:center; font-size:0.8em; color:${isSelected ? '#e53935' : '#999'};">${isSelected ? '✔ Selecionado' : 'Toque para selecionar'}</div>
                        `;
                    } else {
                        imgContainer.innerHTML = `
                            <img src="${url}" alt="Imagem ${index + 1}" onclick="toggleImageSelection('${url}', this.parentElement)">
                            <div style="text-align:center; font-size:0.8em; color:${isSelected ? '#e53935' : '#999'};">${isSelected ? '✔ Selecionada' : 'Toque para selecionar'}</div>
                        `;
                    }
                } else {
                    if (isVideo) {
                        imgContainer.innerHTML = `
                            <div style="position:relative; display:inline-block; width:100%;">
                                <video src="${url}" preload="metadata" muted playsinline
                                    style="max-width:100%; height:auto; border-radius:6px; display:block; pointer-events:none;"></video>
                                <div onclick="showVideoInMonitor('${url}')" data-video-url="${url}"
                                     style="position:absolute; inset:0; cursor:pointer; border-radius:6px;
                                            display:flex; align-items:center; justify-content:center;
                                            background:rgba(0,0,0,0.2); transition:background 0.2s;"
                                     onmouseenter="this.style.background='rgba(0,0,0,0.45)'"
                                     onmouseleave="this.style.background='rgba(0,0,0,0.2)'">
                                    <div class="video-play-icon" style="background:rgba(0,0,0,0.6); border-radius:50%; width:44px; height:44px;
                                                display:flex; align-items:center; justify-content:center; font-size:22px;">▶️</div>
                                </div>
                                <button class="video-restart-btn" data-restart-url="${url}"
                                        onclick="event.stopPropagation(); restartVideoInMonitor('${url}')"
                                        title="Reiniciar vídeo"
                                        style="display:none; position:absolute; top:6px; right:6px;
                                               background:rgba(0,0,0,0.65); color:white; border:none;
                                               border-radius:50%; width:32px; height:32px; cursor:pointer;
                                               font-size:16px; align-items:center; justify-content:center; z-index:2;">⏮️</button>
                            </div>
                            <div class="video-progress-wrap" data-progress-url="${url}"
                                 style="display:none; margin-top:6px; width:100%;">
                                <div class="video-progress-bar"
                                     onclick="seekVideoFromBar(event, '${url}')"
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
                            <button onclick="deleteImage('${url}')">Excluir</button>
                        `;
                    } else {
                        imgContainer.innerHTML = `
                            <img src="${url}" alt="Imagem ${index + 1}" onclick="showImageInMonitor('${url}')">
                            <button onclick="deleteImage('${url}')">Excluir</button>
                        `;
                    }
                }
                gallery.appendChild(imgContainer);
            });
            if (typeof updateVideoOverlayIcons === 'function') updateVideoOverlayIcons();
        });
}

function deleteImage(imageUrl) {
    if (!confirm('Você tem certeza que deseja excluir esta imagem?')) return;
    fetch('/delete_image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_name: decodeURIComponent(imageUrl.split('?')[0].split('/').pop()), folder: getCurrentFolder() })
    }).then(res => res.json())
      .then(data => {
          if (data.status === 'success') {
              alert('Imagem excluída com sucesso!');
              loadImageGallery();
          } else {
              alert('Erro ao excluir imagem: ' + data.message);
          }
      }).catch(err => console.error('Erro ao excluir a imagem:', err));
}

let blackoutActive = false;

function toggleBlackout() {
    blackoutActive = !blackoutActive;
    socket.emit('blackout', { active: blackoutActive });
    const btn = document.getElementById('blackoutBtn');
    btn.textContent = blackoutActive ? '☀️ Restaurar tela' : '🌙 Escurecer tela';
    btn.style.background = blackoutActive ? '#4caf50' : '#333';
}

let selectMode = false;
let selectedImages = new Set();
let _galleryItems = [];
let slideshowTimer = null;
let slideshowIndex = 0;
let _slideshowVideoWaiting = false;
let _lastVideoEndHandled = 0;

function toggleSelectMode() {
    selectMode = !selectMode;
    selectedImages.clear();
    const btn = document.getElementById('toggleSelectBtn');
    btn.textContent = selectMode ? '✖ Cancelar' : '☑ Selecionar';
    btn.style.background = selectMode ? '#757575' : '#ff9800';
    document.getElementById('deleteSelectedBtn').style.display = selectMode ? 'inline-block' : 'none';
    document.getElementById('selectAllBtn').style.display = selectMode ? 'inline-block' : 'none';
    updateSelectedCount();
    loadImageGallery();
}

function toggleImageSelection(imageUrl, container) {
    const name = decodeURIComponent(imageUrl.split('?')[0].split('/').pop());
    if (selectedImages.has(name)) {
        selectedImages.delete(name);
        container.classList.remove('selected-for-delete');
    } else {
        selectedImages.add(name);
        container.classList.add('selected-for-delete');
    }
    updateSelectedCount();
}

function selectAllImages() {
    const containers = document.querySelectorAll('#imageGallery .image-container');
    const allSelected = selectedImages.size === containers.length;
    selectedImages.clear();
    containers.forEach(c => {
        const media = c.querySelector('img, video');
        if (!media) return;
        const src = media.getAttribute('src') || media.src;
        const name = decodeURIComponent(src.split('?')[0].split('/').pop());
        if (!allSelected) {
            selectedImages.add(name);
            c.classList.add('selected-for-delete');
        } else {
            c.classList.remove('selected-for-delete');
        }
    });
    document.getElementById('selectAllBtn').textContent = allSelected ? 'Selecionar Todas' : 'Desmarcar Todas';
    updateSelectedCount();
}

function updateSelectedCount() {
    document.getElementById('selectedCount').textContent = selectedImages.size;
    document.getElementById('deleteSelectedBtn').style.display = selectMode ? 'inline-block' : 'none';
}

function deleteSelectedImages() {
    if (selectedImages.size === 0) return alert('Nenhuma imagem selecionada.');
    if (!confirm(`Excluir ${selectedImages.size} imagem(ns)?`)) return;
    fetch('/delete_images', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_names: Array.from(selectedImages), folder: getCurrentFolder() })
    }).then(res => res.json())
      .then(data => {
          if (data.status === 'success') {
              alert(`${data.deleted.length} imagem(ns) excluída(s)!`);
              selectedImages.clear();
              updateSelectedCount();
              loadImageGallery();
          } else {
              alert('Erro: ' + data.message);
          }
      }).catch(err => console.error('Erro ao excluir imagens:', err));
}

function showImageInMonitor(imageUrl) {
    stopSlideshow();
    document.querySelectorAll('.submenu img').forEach(img => img.classList.remove('selecionada'));
    const matchEl = document.querySelector(`img[src="${imageUrl}"]`);
    if (matchEl) matchEl.classList.add('selecionada');

    // Vídeo deixou de estar no monitor: zera estado e atualiza ícones para ▶️
    currentVideoUrl = null;
    currentVideoPaused = false;
    updateVideoOverlayIcons();

    // Envia a imagem via WebSocket (para /img receber)
    socket.emit('show_image', { image_url: imageUrl, exclude_monitor: publicOnlyMode });

    // Salva o caminho da imagem em JSON
    saveImagePath(imageUrl);
}

// ===== Slideshow automático =====
function _slideshowEmit(item) {
    if (item.type === 'video') {
        socket.emit('show_video', { video_url: item.url });
    } else {
        socket.emit('show_image', { image_url: item.url });
    }
}

function _slideshowScheduleNext() {
    const item = _galleryItems[slideshowIndex];
    _slideshowEmit(item);
    if (item.type === 'video') {
        // Aguarda video_ended; fallback de 5 min caso o evento não chegue
        _slideshowVideoWaiting = true;
        slideshowTimer = setTimeout(function() {
            _slideshowVideoWaiting = false;
            _slideshowNext();
        }, 5 * 60 * 1000);
    } else {
        _slideshowVideoWaiting = false;
        const secs = parseInt(document.getElementById('slideshowInterval').value) || 5;
        slideshowTimer = setTimeout(_slideshowNext, secs * 1000);
    }
}

function _slideshowNext() {
    slideshowIndex = (slideshowIndex + 1) % _galleryItems.length;
    _slideshowScheduleNext();
}

function startSlideshow() {
    if (_galleryItems.length === 0) return;
    slideshowIndex = 0;
    _slideshowVideoWaiting = false;
    const btn = document.getElementById('btnSlideshow');
    if (btn) btn.textContent = '⏹ Parar Slideshow';
    _slideshowScheduleNext();
}

function stopSlideshow() {
    if (!slideshowTimer && !_slideshowVideoWaiting) return;
    if (slideshowTimer) { clearTimeout(slideshowTimer); slideshowTimer = null; }
    _slideshowVideoWaiting = false;
    const btn = document.getElementById('btnSlideshow');
    if (btn) btn.textContent = '▶ Slideshow';
}

function toggleSlideshow() {
    if (slideshowTimer || _slideshowVideoWaiting) stopSlideshow();
    else startSlideshow();
}

// ===== Controles de vídeo na galeria =====
let currentVideoUrl = null;
let currentVideoPaused = false;

function showVideoInMonitor(videoUrl) {
    if (currentVideoUrl === videoUrl) {
        // Mesmo vídeo: alterna pausa/retomada
        currentVideoPaused = !currentVideoPaused;
        console.log(currentVideoPaused ? '⏸️ Pausando vídeo:' : '▶️ Retomando vídeo:', videoUrl);
        socket.emit('toggle_video_pause', { paused: currentVideoPaused, exclude_monitor: publicOnlyMode });
    } else {
        // Novo vídeo: troca e marca como tocando
        console.log('🎬 Enviando show_video:', videoUrl);
        currentVideoUrl = videoUrl;
        currentVideoPaused = false;
        socket.emit('show_video', { video_url: videoUrl, exclude_monitor: publicOnlyMode });
        updateIframes('/img', ''); // mostra preview do vídeo no iframe
    }
    updateVideoOverlayIcons();
    if (typeof ensureProgressPolling === 'function') ensureProgressPolling();
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
    // Barra de progresso só no vídeo atual
    document.querySelectorAll('.video-progress-wrap').forEach(wrap => {
        const url = wrap.getAttribute('data-progress-url');
        wrap.style.display = (url === currentVideoUrl) ? 'block' : 'none';
        if (url === currentVideoUrl) {
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

function seekVideoFromBar(event, videoUrl) {
    if (_dragging) return; // drag já cuidou
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

// Sincronização via Socket.IO (sem polling)
socket.on('display_video', function(data) {
    currentVideoUrl = data.video_url;
    currentVideoPaused = false;
    updateVideoOverlayIcons();
    ensureProgressPolling();
    updateIframes('/img', ''); // sincroniza preview quando outro dispositivo inicia vídeo
});
socket.on('display_image', function() {
    currentVideoUrl = null;
    currentVideoPaused = false;
    updateVideoOverlayIcons();
    stopProgressPolling();
});
socket.on('display_two_urls', function(data) {
    console.log('📡 Recebido display_two_urls de outro PC:', data);
    updateIframes(data.url1, data.url2);
    currentVideoUrl = null;
    currentVideoPaused = false;
    updateVideoOverlayIcons();
    stopProgressPolling();
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

// Polling otimizado: só roda quando há vídeo e aba está visível
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
                currentVideoUrl = null;
                currentVideoPaused = false;
                updateVideoOverlayIcons();
                stopProgressPolling();
                return;
            }
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
document.addEventListener('visibilitychange', () => {
    if (document.hidden) stopProgressPolling();
    else ensureProgressPolling();
});
// Sincronização inicial (caso já haja vídeo tocando)
fetch('/video_state').then(r => r.json()).then(state => {
    if (state.url) {
        currentVideoUrl = state.url;
        currentVideoPaused = !!state.paused;
        updateVideoOverlayIcons();
        ensureProgressPolling();
    }
}).catch(() => {});

function saveImagePath(imageUrl) {
    fetch('/save_image_path', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_path: imageUrl })
    }).then(res => res.json())
      .then(data => {
          if (data.status === 'success') {
              console.log('Caminho da imagem salvo com sucesso!');
          }
      });
}

// Funções do Ticker
function sendTicker(target) {
    const text = document.getElementById('tickerText').value.trim();
    if (!text) return;
    if (target === 'public') socket.emit('stop_ticker', { target: 'monitor' });
    else if (target === 'monitor') socket.emit('stop_ticker', { target: 'public' });
    socket.emit('set_ticker', { text: text, target: target || 'all' });
}
function stopTicker(target) {
    socket.emit('stop_ticker', { target: target || 'all' });
}
function clearTicker() {
    document.getElementById('tickerText').value = '';
    socket.emit('set_ticker', { text: '', target: 'all' });
}

// ── Compartilhar Tela (WebRTC) ───────────────────────────────────────────────
let _screenStream = null;
let _screenPeers = {};
const _iceConfig = { iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] };

async function startScreenShare(target) {
    try {
        _screenStream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: true });
    } catch(e) {
        document.getElementById('screenShareStatus').textContent = 'Cancelado.';
        return;
    }
    _screenStream.getVideoTracks()[0].onended = stopScreenShare;
    socket.emit('screen_share_start', { target: target || 'all' });
    document.getElementById('screenShareStatus').textContent = '● Compartilhando...';
}

function stopScreenShare() {
    if (_screenStream) { _screenStream.getTracks().forEach(t => t.stop()); _screenStream = null; }
    Object.values(_screenPeers).forEach(pc => pc.close());
    _screenPeers = {};
    socket.emit('screen_share_stop', {});
    const el = document.getElementById('screenShareStatus');
    if (el) el.textContent = '';
}

socket.on('screen_share_request', async function(data) {
    if (!_screenStream) return;
    const pc = new RTCPeerConnection(_iceConfig);
    _screenPeers[data.from_sid] = pc;
    _screenStream.getTracks().forEach(t => pc.addTrack(t, _screenStream));
    pc.onicecandidate = e => {
        if (e.candidate) socket.emit('screen_share_ice', { target_sid: data.from_sid, candidate: e.candidate });
    };
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    socket.emit('screen_share_offer', { target_sid: data.from_sid, sdp: offer });
});

socket.on('screen_share_answer', async function(data) {
    const pc = _screenPeers[data.from_sid];
    if (pc) await pc.setRemoteDescription(new RTCSessionDescription(data.sdp));
});

socket.on('screen_share_ice', function(data) {
    const pc = _screenPeers[data.from_sid];
    if (pc) pc.addIceCandidate(new RTCIceCandidate(data.candidate)).catch(()=>{});
});

// Funções do Cronômetro
let _countdownPaused = false;

function showCountdownOnMonitor() {
    socket.emit('show_image', { image_url: '/countdown' });
}

function startCountdown() {
    const min = parseInt(document.getElementById('countdownMin').value) || 0;
    const sec = parseInt(document.getElementById('countdownSec').value) || 0;
    const total = min * 60 + sec;
    if (total <= 0) return;
    const label = document.getElementById('countdownLabel').value.trim();
    _countdownPaused = false;
    document.getElementById('btnCountdownPause').textContent = '⏸ Pausar';
    socket.emit('start_countdown', { duration_seconds: total, label: label });
}

function pauseResumeCountdown() {
    if (_countdownPaused) {
        socket.emit('resume_countdown', {});
        _countdownPaused = false;
        document.getElementById('btnCountdownPause').textContent = '⏸ Pausar';
    } else {
        socket.emit('pause_countdown', {});
        _countdownPaused = true;
        document.getElementById('btnCountdownPause').textContent = '▶ Retomar';
    }
}

function resetCountdown() {
    _countdownPaused = false;
    document.getElementById('btnCountdownPause').textContent = '⏸ Pausar';
    socket.emit('reset_countdown', {});
}

// Avança o slideshow quando o vídeo termina em qualquer tela de exibição
socket.on('video_ended', function() {
    if (!_slideshowVideoWaiting) return;
    const now = Date.now();
    if (now - _lastVideoEndHandled < 1000) return; // debounce: ignora duplicatas
    _lastVideoEndHandled = now;
    if (slideshowTimer) { clearTimeout(slideshowTimer); slideshowTimer = null; }
    _slideshowVideoWaiting = false;
    _slideshowNext();
});

// Funções para Bíblia
function showBibleInIframe() {
    const iframe1 = document.getElementById('iframe1');
    const iframe2 = document.getElementById('iframe2');
    iframe1.src = '/bible';
    iframe2.src = 'about:blank';
    console.log('📖 Bíblia carregada no iframe');
}

function showBibleDisplay() {
    const iframe1 = document.getElementById('iframe1');
    const iframe2 = document.getElementById('iframe2');
    iframe1.src = '/bible';
    iframe2.src = '/bible/display';
    console.log('📖 Bíblia + Display carregados');
    
    // Emite evento para sincronizar com outros dispositivos
    socket.emit('display_two_urls', {
        url1: '/bible',
        url2: '/bible/display'
    });
}

// ── Modo Monitor de Palco ─────────────────────────────────────────────────
let monitorOnlyMode = false;
let publicOnlyMode = false;

function toggleMonitorMode() {
    monitorOnlyMode = !monitorOnlyMode;
    if (monitorOnlyMode && publicOnlyMode) togglePublicMode();
    const btn = document.getElementById('monitor-mode-btn');
    const indicator = document.getElementById('monitor-mode-indicator');
    if (monitorOnlyMode) {
        btn.style.background = '#b71c1c';
        btn.style.borderColor = '#ef5350';
        btn.innerHTML = '<i class="fas fa-tv"></i> Modo Monitor ATIVO';
        indicator.style.display = 'flex';
    } else {
        btn.style.background = '#333';
        btn.style.borderColor = '#555';
        btn.innerHTML = '<i class="fas fa-tv"></i> Modo Monitor';
        indicator.style.display = 'none';
    }
}

// ── Modo Público ────────────────────────────────────────────────────────
// Inverso do Modo Monitor: ações afetam só o público, o monitor de palco
// fica congelado no que já estava exibindo.
function togglePublicMode() {
    publicOnlyMode = !publicOnlyMode;
    if (publicOnlyMode && monitorOnlyMode) toggleMonitorMode();
    const btn = document.getElementById('public-mode-btn');
    const indicator = document.getElementById('public-mode-indicator');
    if (publicOnlyMode) {
        btn.style.background = '#1b5e20';
        btn.style.borderColor = '#66bb6a';
        btn.innerHTML = '<i class="fas fa-users"></i> Modo Público ATIVO';
        indicator.style.display = 'flex';
    } else {
        btn.style.background = '#333';
        btn.style.borderColor = '#555';
        btn.innerHTML = '<i class="fas fa-users"></i> Modo Público';
        indicator.style.display = 'none';
    }
}

function syncMonitor() {
    fetch('/api/monitor/sync', { method: 'POST' })
        .then(() => console.log('✅ Monitor sincronizado com estado público'))
        .catch(e => console.error('Erro ao sincronizar monitor:', e));
}

// Intercepta show_image: em modo monitor, envia só ao /monitor
const _origShowImageInMonitor = showImageInMonitor;
showImageInMonitor = function(imageUrl) {
    if (monitorOnlyMode) {
        socket.emit('show_monitor_content', { url: imageUrl });
        updateIframes(imageUrl.startsWith('/static/') ? '/img' : imageUrl, '');
        return;
    }
    _origShowImageInMonitor(imageUrl);
};

// Intercepta show_video: em modo monitor, envia só ao /monitor
const _origShowVideoInMonitor = showVideoInMonitor;
showVideoInMonitor = function(videoUrl) {
    if (monitorOnlyMode) {
        if (currentVideoUrl === videoUrl) {
            currentVideoPaused = !currentVideoPaused;
            socket.emit('show_monitor_pause', { paused: currentVideoPaused });
        } else {
            currentVideoUrl = videoUrl;
            currentVideoPaused = false;
            socket.emit('show_monitor_video', { video_url: videoUrl });
            updateIframes('/img', '');
        }
        updateVideoOverlayIcons();
        return;
    }
    _origShowVideoInMonitor(videoUrl);
};

// Intercepta sendUrl: em modo monitor, envia só ao /monitor
const _origSendUrl = sendUrl;
sendUrl = function(urlNumber) {
    if (monitorOnlyMode) {
        const fixedRoutes = { 4:'/lyrics/display', 5:'/clock', 6:'/img', 7:'/bible/display', 8:'/lyrics/display/public' };
        const url = fixedRoutes[urlNumber] || document.getElementById(`url${urlNumber}`)?.value;
        if (!url) return;
        socket.emit('show_monitor_content', { url });
        updateIframes(url, '');
        return;
    }
    _origSendUrl(urlNumber);
};

// Intercepta showTwoUrls: em modo monitor, envia tela dividida só ao /monitor
const _origShowTwoUrls = showTwoUrls;
showTwoUrls = function(urlNum1, urlNum2) {
    if (monitorOnlyMode) {
        const fixedRoutes = { 4:'/lyrics/display', 5:'/clock', 6:'/img', 7:'/bible/display', 8:'/lyrics/display/public' };
        const url1 = fixedRoutes[urlNum1] || document.getElementById(`url${urlNum1}`)?.value;
        const url2 = fixedRoutes[urlNum2] || document.getElementById(`url${urlNum2}`)?.value;
        if (!url1 || !url2) return;
        socket.emit('show_monitor_two_urls', { url1, url2 });
        updateIframes(url1, url2);
        return;
    }
    _origShowTwoUrls(urlNum1, urlNum2);
};
