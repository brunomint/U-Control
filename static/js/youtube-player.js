/**
 * YouTube Floating Player Component
 * Player flutuante para referência de vídeos durante edição/estudo de cifras
 */

class YouTubeFloatingPlayer {
    constructor(options = {}) {
        this.videoId = null;
        this.player = null;
        this.isMinimized = options.startMinimized !== undefined ? options.startMinimized : false;
        this.isDragging = false;
        this.dragOffset = { x: 0, y: 0 };
        this.position = { x: 20, y: window.innerHeight - 250 };
        this.playbackRate = 1;
        this.container = null;
        this.onVideoUrlChange = options.onVideoUrlChange || null;
        this.readOnly = options.readOnly || false;  // Modo somente leitura (sem botões de edição)
        this.startMinimized = options.startMinimized || false;  // Iniciar minimizado
        
        this.init();
    }
    
    init() {
        // Cria a interface do player (usa iframe direto, não precisa da API)
        this.createPlayerUI();
        console.log('🎬 Player de vídeo inicializado');
    }
    
    createPlayerUI() {
        // Container principal
        this.container = document.createElement('div');
        this.container.id = 'yt-floating-player';
        
        // Aplica classe minimized se startMinimized for true
        if (this.startMinimized) {
            this.container.classList.add('minimized');
        }
        
        this.container.innerHTML = `
            <div class="yt-player-header">
                <span class="yt-player-title">🎬 Vídeo de Referência</span>
                <div class="yt-player-controls">
                    <button class="yt-btn yt-btn-minimize" title="Minimizar">−</button>
                    <button class="yt-btn yt-btn-close" title="Fechar">×</button>
                </div>
            </div>
            <div class="yt-player-body">
                <div class="yt-player-empty" ${this.readOnly ? 'style="display:none;"' : ''}>
                    <p>📹 Nenhum vídeo carregado</p>
                    <button class="yt-btn-add-video">+ Adicionar Vídeo</button>
                </div>
                <div id="yt-player-frame" style="display: none;"></div>
            </div>
            <div class="yt-player-footer">
                <div class="yt-speed-control">
                    <span>Velocidade:</span>
                    <select class="yt-speed-select">
                        <option value="0.5">0.5x</option>
                        <option value="0.75">0.75x</option>
                        <option value="1" selected>1x</option>
                        <option value="1.25">1.25x</option>
                        <option value="1.5">1.5x</option>
                    </select>
                </div>
                <a class="yt-btn yt-btn-external" href="#" target="_blank" title="Abrir no YouTube" style="display:none;">↗️</a>
                ${this.readOnly ? '' : '<button class="yt-btn yt-btn-download" title="Baixar áudio" style="display:none;">⬇️</button>'}
                ${this.readOnly ? '' : '<button class="yt-btn yt-btn-change" title="Alterar vídeo">🔄</button>'}
            </div>
        `;
        
        // Estilos
        const styles = document.createElement('style');
        styles.textContent = `
            #yt-floating-player {
                position: fixed;
                bottom: 20px;
                right: 20px;
                width: 320px;
                background: #1a1a2e;
                border-radius: 12px;
                box-shadow: 0 8px 32px rgba(0,0,0,0.4);
                z-index: 9999;
                font-family: 'Segoe UI', sans-serif;
                overflow: hidden;
                transition: all 0.3s ease;
                border: 1px solid #333;
            }
            
            #yt-floating-player.minimized {
                width: 200px;
            }
            
            #yt-floating-player.minimized .yt-player-body,
            #yt-floating-player.minimized .yt-player-footer {
                display: none;
            }
            
            #yt-floating-player.hidden {
                display: none;
            }
            
            .yt-player-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 10px 12px;
                background: linear-gradient(135deg, #16213e 0%, #1a1a2e 100%);
                cursor: move;
                user-select: none;
            }
            
            .yt-player-title {
                color: #fff;
                font-size: 13px;
                font-weight: 600;
            }
            
            .yt-player-controls {
                display: flex;
                gap: 6px;
            }
            
            .yt-btn {
                background: rgba(255,255,255,0.1);
                border: none;
                color: #fff;
                width: 24px;
                height: 24px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: background 0.2s;
            }
            
            .yt-btn:hover {
                background: rgba(255,255,255,0.2);
            }
            
            .yt-btn-close:hover {
                background: #e74c3c;
            }
            
            .yt-player-body {
                background: #0f0f1a;
            }
            
            .yt-player-empty {
                padding: 30px 20px;
                text-align: center;
                color: #888;
            }
            
            .yt-player-empty p {
                margin: 0 0 15px 0;
                font-size: 14px;
            }
            
            .yt-btn-add-video {
                background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
                border: none;
                color: #fff;
                padding: 10px 20px;
                border-radius: 6px;
                cursor: pointer;
                font-size: 13px;
                font-weight: 600;
                transition: transform 0.2s, box-shadow 0.2s;
            }
            
            .yt-btn-add-video:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(231, 76, 60, 0.4);
            }
            
            #yt-player-frame {
                width: 100%;
                height: 180px;
            }
            
            #yt-player-frame iframe {
                width: 100%;
                height: 100%;
                border: none;
            }
            
            .yt-player-footer {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 8px 12px;
                background: #16213e;
                border-top: 1px solid #333;
            }
            
            .yt-speed-control {
                display: flex;
                align-items: center;
                gap: 8px;
                color: #aaa;
                font-size: 12px;
            }
            
            .yt-speed-select {
                background: #1a1a2e;
                border: 1px solid #444;
                color: #fff;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 12px;
                cursor: pointer;
            }
            
            .yt-speed-select:focus {
                outline: none;
                border-color: #e74c3c;
            }
            
            .yt-btn-change {
                font-size: 16px;
            }
            
            /* Animação de entrada */
            @keyframes slideIn {
                from {
                    opacity: 0;
                    transform: translateY(20px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
            
            #yt-floating-player {
                animation: slideIn 0.3s ease;
            }
        `;
        
        document.head.appendChild(styles);
        document.body.appendChild(this.container);
        
        // Event listeners
        this.setupEventListeners();
    }
    
    setupEventListeners() {
        const header = this.container.querySelector('.yt-player-header');
        const minimizeBtn = this.container.querySelector('.yt-btn-minimize');
        const closeBtn = this.container.querySelector('.yt-btn-close');
        const addVideoBtn = this.container.querySelector('.yt-btn-add-video');
        const changeBtn = this.container.querySelector('.yt-btn-change');
        const speedSelect = this.container.querySelector('.yt-speed-select');
        
        // Drag functionality
        header.addEventListener('mousedown', (e) => this.startDrag(e));
        document.addEventListener('mousemove', (e) => this.drag(e));
        document.addEventListener('mouseup', () => this.stopDrag());
        
        // Touch support
        header.addEventListener('touchstart', (e) => this.startDrag(e.touches[0]));
        document.addEventListener('touchmove', (e) => this.drag(e.touches[0]));
        document.addEventListener('touchend', () => this.stopDrag());
        
        // Buttons
        minimizeBtn.addEventListener('click', () => this.toggleMinimize());
        closeBtn.addEventListener('click', () => this.hide());
        
        // Botões de edição só existem quando não é readOnly
        if (addVideoBtn) {
            addVideoBtn.addEventListener('click', () => this.promptForVideo());
        }
        if (changeBtn) {
            changeBtn.addEventListener('click', () => this.promptForVideo());
        }
        
        // Download button
        const downloadBtn = this.container.querySelector('.yt-btn-download');
        if (downloadBtn) {
            downloadBtn.addEventListener('click', () => this.downloadAudio());
        }
        
        // Speed control
        speedSelect.addEventListener('change', (e) => {
            this.setPlaybackRate(parseFloat(e.target.value));
        });
    }
    
    startDrag(e) {
        this.isDragging = true;
        const rect = this.container.getBoundingClientRect();
        this.dragOffset.x = e.clientX - rect.left;
        this.dragOffset.y = e.clientY - rect.top;
        this.container.style.transition = 'none';
    }
    
    drag(e) {
        if (!this.isDragging) return;
        
        const x = e.clientX - this.dragOffset.x;
        const y = e.clientY - this.dragOffset.y;
        
        // Limita às bordas da tela
        const maxX = window.innerWidth - this.container.offsetWidth;
        const maxY = window.innerHeight - this.container.offsetHeight;
        
        this.container.style.left = Math.max(0, Math.min(x, maxX)) + 'px';
        this.container.style.top = Math.max(0, Math.min(y, maxY)) + 'px';
        this.container.style.right = 'auto';
        this.container.style.bottom = 'auto';
    }
    
    stopDrag() {
        this.isDragging = false;
        this.container.style.transition = 'all 0.3s ease';
    }
    
    toggleMinimize() {
        this.isMinimized = !this.isMinimized;
        this.container.classList.toggle('minimized', this.isMinimized);
        
        const btn = this.container.querySelector('.yt-btn-minimize');
        btn.textContent = this.isMinimized ? '+' : '−';
    }
    
    show() {
        this.container.classList.remove('hidden');
    }
    
    hide() {
        this.container.classList.add('hidden');
    }
    
    promptForVideo() {
        const input = prompt('🎬 Cole a URL do vídeo do YouTube:\n\nFormatos aceitos:\n• https://www.youtube.com/watch?v=XXXXX\n• https://youtu.be/XXXXX\n• Código de embed (iframe)\n• ID do vídeo (11 caracteres)');
        
        if (input && input.trim()) {
            const videoId = this.extractVideoId(input.trim());
            if (videoId) {
                this.loadVideo(videoId);
                
                // Callback para atualizar campo de formulário com URL limpa
                if (this.onVideoUrlChange) {
                    // Salva sempre como URL padrão do YouTube
                    const cleanUrl = `https://www.youtube.com/watch?v=${videoId}`;
                    this.onVideoUrlChange(cleanUrl);
                }
            } else {
                alert('❌ URL inválida!\n\nCertifique-se de que é uma URL válida do YouTube.\n\nFormatos aceitos:\n• https://www.youtube.com/watch?v=XXXXX\n• https://youtu.be/XXXXX\n• Código de embed (iframe)');
            }
        }
    }
    
    extractVideoId(url) {
        // Remove espaços e quebras de linha
        const cleanUrl = url.trim();
        
        // Padrões de URL do YouTube (incluindo código de embed iframe)
        const patterns = [
            // Código de embed iframe: src="https://www.youtube.com/embed/VIDEO_ID..."
            /src=["']https?:\/\/(?:www\.)?youtube\.com\/embed\/([a-zA-Z0-9_-]{11})/i,
            // URL padrão: https://www.youtube.com/watch?v=VIDEO_ID
            /(?:youtube\.com\/watch\?v=)([a-zA-Z0-9_-]{11})/,
            // URL curta: https://youtu.be/VIDEO_ID
            /(?:youtu\.be\/)([a-zA-Z0-9_-]{11})/,
            // URL de embed direta: https://www.youtube.com/embed/VIDEO_ID
            /(?:youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})/,
            // ID direto (11 caracteres)
            /^([a-zA-Z0-9_-]{11})$/
        ];
        
        for (const pattern of patterns) {
            const match = cleanUrl.match(pattern);
            if (match) {
                console.log('🎬 ID do vídeo extraído:', match[1]);
                return match[1];
            }
        }
        
        console.log('❌ Não foi possível extrair ID do vídeo de:', cleanUrl.substring(0, 100));
        return null;
    }
    
    loadVideo(videoId) {
        this.videoId = videoId;
        
        const emptyState = this.container.querySelector('.yt-player-empty');
        const playerFrame = this.container.querySelector('#yt-player-frame');
        
        emptyState.style.display = 'none';
        playerFrame.style.display = 'block';
        
        // Usa iframe direto ao invés da API (menos restrições)
        // Parâmetros: autoplay=0, rel=0 (não mostrar vídeos relacionados)
        playerFrame.innerHTML = `
            <iframe 
                width="100%" 
                height="180" 
                src="https://www.youtube.com/embed/${videoId}?rel=0&modestbranding=1&playsinline=1" 
                frameborder="0" 
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
                allowfullscreen
                style="border-radius: 0;">
            </iframe>
        `;
        
        // Mostra botão para abrir no YouTube
        const externalBtn = this.container.querySelector('.yt-btn-external');
        if (externalBtn) {
            externalBtn.href = `https://www.youtube.com/watch?v=${videoId}`;
            externalBtn.style.display = 'inline-flex';
        }
        
        // Mostra botão de download
        const downloadBtn = this.container.querySelector('.yt-btn-download');
        if (downloadBtn) {
            downloadBtn.style.display = 'inline-flex';
        }
        
        console.log('🎬 Player carregado via iframe direto');
        this.show();
    }
    
    async downloadAudio() {
        if (!this.videoId) {
            alert('❌ Nenhum vídeo carregado');
            return;
        }
        
        const downloadBtn = this.container.querySelector('.yt-btn-download');
        const originalText = downloadBtn.textContent;
        
        try {
            // Mostra loading
            downloadBtn.textContent = '⏳';
            downloadBtn.disabled = true;
            
            const videoUrl = `https://www.youtube.com/watch?v=${this.videoId}`;
            
            // Pega o song_id do campo oculto se existir
            const songIdField = document.getElementById('song_id') || document.querySelector('input[name="song_id"]');
            const songId = songIdField ? songIdField.value : null;
            
            // Pega o áudio antigo para deletar
            const audioField = document.getElementById('audio_url');
            const oldAudioUrl = audioField ? audioField.value : null;
            
            console.log('🎵 Baixando áudio...', videoUrl);
            if (oldAudioUrl) {
                console.log('🗑️ Áudio antigo será substituído:', oldAudioUrl);
            }
            
            const response = await fetch('/download_audio', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    url: videoUrl,
                    song_id: songId,
                    old_audio_url: oldAudioUrl
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                console.log('✅ Áudio baixado:', data.audio_url);
                
                // Salva a URL do áudio no campo oculto
                const audioField = document.getElementById('audio_url');
                if (audioField) {
                    audioField.value = data.audio_url;
                    console.log('🎵 URL do áudio salva no formulário');
                }
                
                // Substitui o iframe pelo player de áudio
                this.loadLocalAudio(data.audio_url);
                
                alert('✅ Áudio baixado com sucesso!\n\nClique em Salvar para vincular à música.');
            } else {
                throw new Error(data.error || 'Erro desconhecido');
            }
        } catch (error) {
            console.error('❌ Erro ao baixar:', error);
            alert(`❌ Erro ao baixar áudio:\n${error.message}`);
        } finally {
            downloadBtn.textContent = originalText;
            downloadBtn.disabled = false;
        }
    }
    
    loadLocalAudio(audioUrl, songTitle = null, songAuthor = null) {
        const emptyState = this.container.querySelector('.yt-player-empty');
        const playerFrame = this.container.querySelector('#yt-player-frame');
        
        console.log('🎵 loadLocalAudio chamado:', audioUrl);
        console.log('🔍 emptyState:', emptyState);
        console.log('🔍 playerFrame:', playerFrame);
        
        // Esconde estado vazio e mostra o player
        if (emptyState) {
            emptyState.style.display = 'none';
        }
        playerFrame.style.display = 'block';
        
        // Tenta pegar título e autor dos campos do formulário se não fornecidos
        if (!songTitle) {
            const titleField = document.getElementById('title');
            songTitle = titleField?.value || 'Música';
        }
        if (!songAuthor) {
            const authorField = document.getElementById('author');
            songAuthor = authorField?.value || '';
        }
        
        // Substitui iframe por player de áudio HTML5 estilizado
        playerFrame.innerHTML = `
            <div class="audio-player-container">
                <div class="audio-player-info">
                    <div class="audio-player-icon">🎵</div>
                    <div class="audio-player-details">
                        <div class="audio-player-title">${songTitle}</div>
                        ${songAuthor ? `<div class="audio-player-author">${songAuthor}</div>` : ''}
                    </div>
                </div>
                <div class="audio-player-visualizer">
                    <span></span><span></span><span></span><span></span><span></span>
                </div>
                <audio controls class="local-audio-player">
                    <source src="${audioUrl}" type="audio/mpeg">
                </audio>
                ${this.readOnly ? '' : `<div class="audio-player-actions">
                    <button class="audio-change-btn" onclick="window.ytPlayer.promptForVideo()">🔄 Trocar Áudio</button>
                </div>`}
                <div class="audio-player-badge">
                    <span>💾 Salvo localmente</span>
                </div>
            </div>
        `;
        
        // Adiciona estilos do player de áudio se ainda não existirem
        if (!document.getElementById('audio-player-styles')) {
            const audioStyles = document.createElement('style');
            audioStyles.id = 'audio-player-styles';
            audioStyles.textContent = `
                .audio-player-container {
                    padding: 15px;
                    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                    text-align: center;
                }
                .audio-player-info {
                    display: flex;
                    align-items: center;
                    gap: 12px;
                    margin-bottom: 12px;
                }
                .audio-player-icon {
                    font-size: 32px;
                    background: linear-gradient(135deg, #4ade80, #22c55e);
                    width: 50px;
                    height: 50px;
                    border-radius: 10px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    box-shadow: 0 4px 15px rgba(74, 222, 128, 0.3);
                }
                .audio-player-details {
                    text-align: left;
                    flex: 1;
                    overflow: hidden;
                }
                .audio-player-title {
                    color: #fff;
                    font-size: 14px;
                    font-weight: 600;
                    white-space: nowrap;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    max-width: 200px;
                }
                .audio-player-author {
                    color: #a0aec0;
                    font-size: 12px;
                    margin-top: 2px;
                    white-space: nowrap;
                    overflow: hidden;
                    text-overflow: ellipsis;
                }
                .audio-player-visualizer {
                    display: flex;
                    justify-content: center;
                    gap: 3px;
                    height: 20px;
                    margin-bottom: 10px;
                }
                .audio-player-visualizer span {
                    width: 4px;
                    background: linear-gradient(to top, #4ade80, #22c55e);
                    border-radius: 2px;
                    animation: audioWave 0.5s ease-in-out infinite alternate;
                }
                .audio-player-visualizer span:nth-child(1) { animation-delay: 0s; height: 8px; }
                .audio-player-visualizer span:nth-child(2) { animation-delay: 0.1s; height: 15px; }
                .audio-player-visualizer span:nth-child(3) { animation-delay: 0.2s; height: 10px; }
                .audio-player-visualizer span:nth-child(4) { animation-delay: 0.3s; height: 18px; }
                .audio-player-visualizer span:nth-child(5) { animation-delay: 0.4s; height: 6px; }
                @keyframes audioWave {
                    0% { transform: scaleY(0.5); opacity: 0.5; }
                    100% { transform: scaleY(1); opacity: 1; }
                }
                .local-audio-player {
                    width: 100%;
                    height: 40px;
                    border-radius: 20px;
                    outline: none;
                }
                .local-audio-player::-webkit-media-controls-panel {
                    background: rgba(255,255,255,0.1);
                }
                .audio-player-badge {
                    margin-top: 8px;
                    font-size: 10px;
                    color: #4ade80;
                    opacity: 0.8;
                }
                .audio-player-actions {
                    margin-top: 10px;
                }
                .audio-change-btn {
                    background: rgba(255,255,255,0.1);
                    border: 1px solid rgba(255,255,255,0.2);
                    color: #fff;
                    padding: 6px 12px;
                    border-radius: 15px;
                    font-size: 11px;
                    cursor: pointer;
                    transition: all 0.2s ease;
                }
                .audio-change-btn:hover {
                    background: rgba(255,255,255,0.2);
                    border-color: #4ade80;
                    color: #4ade80;
                }
            `;
            document.head.appendChild(audioStyles);
        }
        
        // Configura controle de velocidade para o áudio local
        const audioElement = playerFrame.querySelector('audio');
        if (audioElement) {
            audioElement.playbackRate = this.playbackRate;
            
            // Atualiza velocidade quando mudar no select
            const speedSelect = this.container.querySelector('.yt-speed-select');
            if (speedSelect) {
                speedSelect.addEventListener('change', (e) => {
                    audioElement.playbackRate = parseFloat(e.target.value);
                });
            }
        }
        
        // Esconde botão de download (já baixou)
        const downloadBtn = this.container.querySelector('.yt-btn-download');
        if (downloadBtn) {
            downloadBtn.style.display = 'none';
        }
        
        console.log('🎵 Player de áudio local carregado');
    }
    
    showExternalLink(videoId) {
        // Mostra link externo quando embed não é permitido
        const emptyState = this.container.querySelector('.yt-player-empty');
        const playerFrame = this.container.querySelector('#yt-player-frame');
        
        // Esconde o player com erro
        playerFrame.style.display = 'none';
        playerFrame.innerHTML = '';
        
        // Mostra mensagem com link externo
        emptyState.style.display = 'block';
        emptyState.innerHTML = `
            <p style="margin-bottom: 10px;">⚠️ Este vídeo não permite<br>reprodução em outros sites</p>
            <a href="https://www.youtube.com/watch?v=${videoId}" 
               target="_blank" 
               class="yt-btn-add-video"
               style="text-decoration: none; display: inline-block;">
                🎬 Abrir no YouTube
            </a>
            <p style="margin-top: 15px; font-size: 12px; color: #666;">
                O vídeo abrirá em uma nova aba
            </p>
        `;
        
        this.show();
    }
    
    loadVideoFromUrl(url) {
        const videoId = this.extractVideoId(url);
        if (videoId) {
            this.loadVideo(videoId);
            return true;
        }
        return false;
    }
    
    setPlaybackRate(rate) {
        this.playbackRate = rate;
        if (this.player && this.player.setPlaybackRate) {
            this.player.setPlaybackRate(rate);
        }
    }
    
    play() {
        if (this.player && this.player.playVideo) {
            this.player.playVideo();
        }
    }
    
    pause() {
        if (this.player && this.player.pauseVideo) {
            this.player.pauseVideo();
        }
    }
    
    getCurrentTime() {
        if (this.player && this.player.getCurrentTime) {
            return this.player.getCurrentTime();
        }
        return 0;
    }
    
    seekTo(seconds) {
        if (this.player && this.player.seekTo) {
            this.player.seekTo(seconds, true);
        }
    }
}

// Exporta para uso global
window.YouTubeFloatingPlayer = YouTubeFloatingPlayer;
