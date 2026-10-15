/**
 * YouTube Floating Player Component
 * Player flutuante para referência de vídeos durante edição/estudo de cifras
 * (editor de música e /view/<id>). Usa as cores do tema (tokens.css) com
 * fallback, e os ícones do Font Awesome que as três páginas já carregam.
 *
 * Só um botão no cabeçalho: recolher/abrir. Antes havia também um "×" que
 * escondia o player sem nenhum jeito de trazer de volta (só recarregando).
 */

class YouTubeFloatingPlayer {
    constructor(options = {}) {
        this.videoId = null;
        this.isMinimized = !!options.startMinimized;
        this.isDragging = false;
        this.dragMoved = false;
        this.dragOffset = { x: 0, y: 0 };
        this.playbackRate = 1;
        this.container = null;
        this.onVideoUrlChange = options.onVideoUrlChange || null;
        this.readOnly = options.readOnly || false;  // Modo somente leitura (sem botões de edição)

        this.init();
    }

    init() {
        this.createPlayerUI();
    }

    createPlayerUI() {
        this.container = document.createElement('div');
        this.container.id = 'yt-floating-player';
        this.container.classList.toggle('minimized', this.isMinimized);

        this.container.innerHTML = `
            <div class="yt-player-header" title="Arraste para mover">
                <span class="yt-player-icon"><i class="fab fa-youtube"></i></span>
                <span class="yt-player-title">Vídeo de referência</span>
                <button type="button" class="yt-icon-btn yt-btn-minimize"></button>
            </div>
            <div class="yt-player-body">
                <div class="yt-player-empty" ${this.readOnly ? 'style="display:none;"' : ''}>
                    <i class="fab fa-youtube yt-empty-icon"></i>
                    <p>Nenhum vídeo ainda</p>
                    <button type="button" class="yt-btn-add-video"><i class="fas fa-plus"></i> Adicionar vídeo do YouTube</button>
                </div>
                <div id="yt-player-frame" style="display: none;"></div>
            </div>
            <div class="yt-player-footer">
                <label class="yt-speed-control" title="Velocidade">
                    <i class="fas fa-gauge-high"></i>
                    <select class="yt-speed-select" aria-label="Velocidade">
                        <option value="0.5">0.5×</option>
                        <option value="0.75">0.75×</option>
                        <option value="1" selected>1×</option>
                        <option value="1.25">1.25×</option>
                        <option value="1.5">1.5×</option>
                    </select>
                </label>
                <div class="yt-footer-actions">
                    <a class="yt-action yt-btn-external" href="#" target="_blank" rel="noopener" title="Abrir no YouTube" style="display:none;"><i class="fas fa-arrow-up-right-from-square"></i> <span class="yt-label">YouTube</span></a>
                    ${this.readOnly ? '' : '<button type="button" class="yt-action yt-btn-download" title="Baixar o áudio e guardar no U-Control" style="display:none;"><i class="fas fa-download"></i> <span class="yt-label">Baixar áudio</span></button>'}
                    ${this.readOnly ? '' : '<button type="button" class="yt-action yt-btn-change" title="Trocar por outro vídeo do YouTube" style="display:none;"><i class="fas fa-arrow-right-arrow-left"></i> <span class="yt-label">Trocar</span></button>'}
                </div>
            </div>
        `;

        if (!document.getElementById('yt-player-styles')) {
            const styles = document.createElement('style');
            styles.id = 'yt-player-styles';
            styles.textContent = `
            #yt-floating-player {
                position: fixed;
                bottom: 20px;
                right: 20px;
                width: min(340px, calc(100vw - 24px));
                background: var(--uc-surface, #161a2b);
                color: var(--uc-text, #e9ebf4);
                border: 1px solid var(--uc-line, #2a3050);
                border-radius: var(--uc-r-lg, 14px);
                box-shadow: 0 16px 40px rgba(0, 0, 0, .5);
                z-index: 9999;
                font-family: var(--uc-font, 'Segoe UI', system-ui, sans-serif);
                overflow: hidden;
                transition: width .2s ease;
                animation: ytSlideIn .25s ease;
            }
            #yt-floating-player.minimized { width: min(240px, calc(100vw - 24px)); }
            #yt-floating-player.minimized .yt-player-body,
            #yt-floating-player.minimized .yt-player-footer { display: none; }
            #yt-floating-player.hidden { display: none; }
            @keyframes ytSlideIn { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: none; } }

            .yt-player-header {
                display: flex;
                align-items: center;
                gap: 10px;
                padding: 8px 8px 8px 12px;
                cursor: move;
                user-select: none;
                touch-action: none;
            }
            #yt-floating-player.minimized .yt-player-header { cursor: pointer; }
            .yt-player-icon { color: #ff3d3d; font-size: 16px; width: 18px; text-align: center; flex: none; }
            .yt-player-icon .fa-music { color: var(--uc-accent-text, #b9a8ff); font-size: 14px; }
            .yt-player-title {
                flex: 1;
                min-width: 0;
                font-size: 13px;
                font-weight: 700;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }
            .yt-icon-btn {
                width: 32px;
                height: 32px;
                flex: none;
                display: grid;
                place-items: center;
                border: 1px solid var(--uc-line, #2a3050);
                border-radius: var(--uc-r-sm, 6px);
                background: var(--uc-surface-2, #1d2236);
                color: var(--uc-text, #e9ebf4);
                font-size: 13px;
                cursor: pointer;
            }
            .yt-icon-btn:hover { border-color: var(--uc-faint, #636a87); }

            .yt-player-body { background: #000; }
            .yt-player-empty {
                padding: 26px 18px;
                text-align: center;
                background: var(--uc-surface, #161a2b);
                border-top: 1px solid var(--uc-line, #2a3050);
            }
            .yt-empty-icon { font-size: 28px; color: var(--uc-faint, #636a87); }
            .yt-player-empty p { margin: 8px 0 14px; font-size: 13.5px; color: var(--uc-muted, #9198b3); }
            .yt-btn-add-video {
                display: inline-flex;
                align-items: center;
                gap: 8px;
                padding: 9px 16px;
                border: 0;
                border-radius: var(--uc-r, 10px);
                background: var(--uc-accent, #8b6cf6);
                color: #fff;
                font: inherit;
                font-size: 13px;
                font-weight: 700;
                text-decoration: none;
                cursor: pointer;
            }
            .yt-btn-add-video:hover { background: var(--uc-accent-strong, #7350ea); }
            .yt-empty-tip { margin: 14px 0 0 !important; font-size: 12.5px !important; line-height: 1.45; }
            .yt-empty-tip b { color: var(--uc-text, #e9ebf4); }

            #yt-player-frame { width: 100%; }
            #yt-player-frame iframe { display: block; width: 100%; aspect-ratio: 16 / 9; height: auto; border: 0; }

            .yt-player-footer {
                display: flex;
                flex-wrap: wrap;
                align-items: center;
                justify-content: space-between;
                gap: 8px;
                padding: 8px 10px;
                border-top: 1px solid var(--uc-line, #2a3050);
            }
            .yt-speed-control {
                display: inline-flex;
                align-items: center;
                gap: 6px;
                color: var(--uc-muted, #9198b3);
                font-size: 12px;
            }
            .yt-speed-select {
                background: var(--uc-surface-2, #1d2236);
                border: 1px solid var(--uc-line, #2a3050);
                color: var(--uc-text, #e9ebf4);
                padding: 5px 6px;
                border-radius: var(--uc-r-sm, 6px);
                font: inherit;
                font-size: 12.5px;
                font-weight: 700;
                cursor: pointer;
            }
            .yt-footer-actions { display: flex; flex-wrap: wrap; gap: 6px; margin-left: auto; }
            .yt-action {
                display: inline-flex;
                align-items: center;
                gap: 6px;
                padding: 6px 10px;
                border: 1px solid var(--uc-line, #2a3050);
                border-radius: var(--uc-r-sm, 6px);
                background: transparent;
                color: var(--uc-text, #e9ebf4);
                font: inherit;
                font-size: 12px;
                font-weight: 700;
                text-decoration: none;
                cursor: pointer;
                white-space: nowrap;
            }
            .yt-action i { color: var(--uc-muted, #9198b3); }
            .yt-action:hover { border-color: var(--uc-faint, #636a87); }
            .yt-action:disabled { opacity: .6; cursor: wait; }

            /* Áudio baixado (guardado no U-Control) */
            .audio-player-container { padding: 14px; background: var(--uc-surface, #161a2b); border-top: 1px solid var(--uc-line, #2a3050); }
            .audio-player-info { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
            .audio-player-art {
                width: 44px;
                height: 44px;
                flex: none;
                display: grid;
                place-items: center;
                border-radius: var(--uc-r, 10px);
                background: var(--uc-accent-soft, rgba(139, 108, 246, .15));
                color: var(--uc-accent-text, #b9a8ff);
                font-size: 18px;
            }
            .audio-player-details { min-width: 0; }
            .audio-player-title { font-size: 14px; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
            .audio-player-author { margin-top: 2px; font-size: 12px; color: var(--uc-muted, #9198b3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
            .local-audio-player { display: block; width: 100%; height: 40px; }
            .audio-player-badge { margin-top: 8px; font-size: 11px; color: var(--uc-ok, #3fcf8e); }

            /* Celular: player menor em todas as telas (aberto 240px, recolhido
               190px), botões do rodapé só com ícone (nome no title) */
            @media (max-width: 600px) {
                #yt-floating-player { width: min(240px, calc(100vw - 24px)); bottom: 12px; right: 12px; border-radius: 12px; }
                #yt-floating-player.minimized { width: min(190px, calc(100vw - 24px)); }
                .yt-player-header { padding: 5px 5px 5px 10px; gap: 8px; }
                .yt-player-header .yt-icon-btn { width: 28px; height: 28px; }
                .yt-player-footer { padding: 5px 6px; gap: 6px; }
                .yt-action { gap: 0; padding: 0; width: 34px; height: 32px; justify-content: center; }
                .yt-action .yt-label { display: none; }
                .yt-action i { font-size: 13px; }
                .yt-footer-actions { flex-wrap: nowrap; gap: 4px; }
                .yt-speed-select { padding: 4px 4px; font-size: 12px; }
                .yt-player-empty { padding: 14px 12px; }
                .yt-empty-icon { font-size: 22px; }
                .yt-player-empty p { margin: 6px 0 10px; font-size: 12px; }
                .yt-btn-add-video { padding: 7px 12px; font-size: 12px; }
                .yt-empty-tip { font-size: 11.5px !important; margin-top: 10px !important; }
                .audio-player-container { padding: 10px; }
            }
            `;
            document.head.appendChild(styles);
        }
        document.body.appendChild(this.container);

        this.renderMinimizeButton();
        this.setupEventListeners();
        this.reserveSpace();
    }

    // O player fica fixo no canto de baixo: sem isto ele cobria o fim da
    // página — os botões Salvar do editor e as últimas linhas da cifra —
    // mesmo rolando até o fim. Reserva a altura dele embaixo da página
    // (acompanha abrir/recolher/trocar de conteúdo).
    reserveSpace() {
        const base = parseFloat(getComputedStyle(document.body).paddingBottom) || 0;
        const apply = () => {
            const hidden = this.container.classList.contains('hidden');
            const h = hidden ? 0 : this.container.offsetHeight + 28;
            document.body.style.paddingBottom = (base + h) + 'px';
        };
        apply();
        if (window.ResizeObserver) new ResizeObserver(apply).observe(this.container);
        this._reapplySpace = apply;
    }

    setupEventListeners() {
        const header = this.container.querySelector('.yt-player-header');
        const minimizeBtn = this.container.querySelector('.yt-btn-minimize');
        const addVideoBtn = this.container.querySelector('.yt-btn-add-video');
        const changeBtn = this.container.querySelector('.yt-btn-change');
        const downloadBtn = this.container.querySelector('.yt-btn-download');
        const speedSelect = this.container.querySelector('.yt-speed-select');

        // Arrastar pelo cabeçalho (o botão não conta)
        const start = (e, point) => { if (!e.target.closest('button')) this.startDrag(point); };
        header.addEventListener('mousedown', (e) => start(e, e));
        header.addEventListener('touchstart', (e) => start(e, e.touches[0]), { passive: true });
        document.addEventListener('mousemove', (e) => this.drag(e));
        document.addEventListener('touchmove', (e) => this.drag(e.touches[0]), { passive: true });
        document.addEventListener('mouseup', () => this.stopDrag());
        document.addEventListener('touchend', () => this.stopDrag());

        // stopPropagation: senão o mesmo clique chega na barra e (já
        // recolhido) abre de novo na hora
        minimizeBtn.addEventListener('click', (e) => { e.stopPropagation(); this.toggleMinimize(); });
        // Recolhido: tocar na barra (sem arrastar) abre de novo
        header.addEventListener('click', (e) => {
            if (this.isMinimized && !this.dragMoved && !e.target.closest('button')) this.toggleMinimize();
        });

        if (addVideoBtn) addVideoBtn.addEventListener('click', () => this.promptForVideo());
        if (changeBtn) changeBtn.addEventListener('click', () => this.promptForVideo());
        if (downloadBtn) downloadBtn.addEventListener('click', () => this.downloadAudio());

        speedSelect.addEventListener('change', (e) => this.setPlaybackRate(parseFloat(e.target.value)));
    }

    startDrag(e) {
        this.isDragging = true;
        this.dragMoved = false;
        const rect = this.container.getBoundingClientRect();
        this.dragOffset.x = e.clientX - rect.left;
        this.dragOffset.y = e.clientY - rect.top;
        this.dragStart = { x: e.clientX, y: e.clientY };
        this.container.style.transition = 'none';
    }

    drag(e) {
        if (!this.isDragging || !e) return;
        if (Math.abs(e.clientX - this.dragStart.x) + Math.abs(e.clientY - this.dragStart.y) > 4) this.dragMoved = true;
        if (!this.dragMoved) return;

        const x = e.clientX - this.dragOffset.x;
        const y = e.clientY - this.dragOffset.y;
        const maxX = window.innerWidth - this.container.offsetWidth;
        const maxY = window.innerHeight - this.container.offsetHeight;

        this.container.style.left = Math.max(0, Math.min(x, maxX)) + 'px';
        this.container.style.top = Math.max(0, Math.min(y, maxY)) + 'px';
        this.container.style.right = 'auto';
        this.container.style.bottom = 'auto';
    }

    stopDrag() {
        if (!this.isDragging) return;
        this.isDragging = false;
        this.container.style.transition = '';
        // o click que vem logo depois do mouseup ainda vê dragMoved
        setTimeout(() => { this.dragMoved = false; }, 0);
    }

    renderMinimizeButton() {
        const btn = this.container.querySelector('.yt-btn-minimize');
        const label = this.isMinimized ? 'Abrir player' : 'Recolher player';
        if (!btn.firstElementChild) btn.innerHTML = '<i></i>';
        btn.firstElementChild.className = `fas fa-chevron-${this.isMinimized ? 'up' : 'down'}`;
        btn.title = label;
        btn.setAttribute('aria-label', label);
        btn.setAttribute('aria-expanded', String(!this.isMinimized));
    }

    toggleMinimize() {
        this.isMinimized = !this.isMinimized;
        this.container.classList.toggle('minimized', this.isMinimized);
        this.renderMinimizeButton();
        // Recolhido perto da borda de baixo: ao abrir, não deixa sair da tela
        if (!this.isMinimized && this.container.style.top) {
            const maxY = window.innerHeight - this.container.offsetHeight;
            this.container.style.top = Math.max(0, Math.min(parseFloat(this.container.style.top), maxY)) + 'px';
        }
    }

    show() {
        this.container.classList.remove('hidden');
        if (this._reapplySpace) this._reapplySpace();
    }

    hide() {
        this.container.classList.add('hidden');
        if (this._reapplySpace) this._reapplySpace();
    }

    setHeader(kind, title) {
        this.container.querySelector('.yt-player-icon').innerHTML =
            kind === 'audio' ? '<i class="fas fa-music"></i>' : '<i class="fab fa-youtube"></i>';
        this.container.querySelector('.yt-player-title').textContent = title;
    }

    setFooterActions({ external = false, download = false, change = false } = {}) {
        const show = (sel, on) => {
            const el = this.container.querySelector(sel);
            if (el) el.style.display = on ? 'inline-flex' : 'none';
        };
        show('.yt-btn-external', external);
        show('.yt-btn-download', download);
        show('.yt-btn-change', change);
    }

    // Velocidade só faz sentido com algo tocando aqui (vídeo ou áudio)
    setSpeedVisible(on) {
        this.container.querySelector('.yt-speed-control').style.display = on ? '' : 'none';
    }

    promptForVideo() {
        const input = prompt('Cole o link do vídeo do YouTube:\n\nServe youtube.com/watch?v=…, youtu.be/…, código de incorporação (iframe) ou o ID do vídeo (11 caracteres).');

        if (input && input.trim()) {
            const videoId = this.extractVideoId(input.trim());
            if (videoId) {
                this.loadVideo(videoId);

                // Callback para atualizar campo de formulário com URL limpa
                if (this.onVideoUrlChange) {
                    this.onVideoUrlChange(`https://www.youtube.com/watch?v=${videoId}`);
                }
            } else {
                alert('Não reconheci esse link do YouTube.\n\nServe youtube.com/watch?v=…, youtu.be/… ou o código de incorporação (iframe).');
            }
        }
    }

    extractVideoId(url) {
        const cleanUrl = url.trim();

        // Padrões de URL do YouTube (incluindo código de embed iframe)
        const patterns = [
            /src=["']https?:\/\/(?:www\.)?youtube\.com\/embed\/([a-zA-Z0-9_-]{11})/i,
            /(?:youtube\.com\/watch\?v=)([a-zA-Z0-9_-]{11})/,
            /(?:youtu\.be\/)([a-zA-Z0-9_-]{11})/,
            /(?:youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})/,
            /^([a-zA-Z0-9_-]{11})$/
        ];

        for (const pattern of patterns) {
            const match = cleanUrl.match(pattern);
            if (match) return match[1];
        }
        return null;
    }

    loadVideo(videoId) {
        this.videoId = videoId;

        const emptyState = this.container.querySelector('.yt-player-empty');
        const playerFrame = this.container.querySelector('#yt-player-frame');

        emptyState.style.display = 'none';
        playerFrame.style.display = 'block';

        // iframe direto; enablejsapi=1 deixa a velocidade (postMessage)
        // funcionar no vídeo — antes o seletor só valia pro áudio baixado
        const origin = encodeURIComponent(location.origin);
        playerFrame.innerHTML = `
            <iframe
                src="https://www.youtube.com/embed/${videoId}?rel=0&modestbranding=1&playsinline=1&enablejsapi=1&origin=${origin}"
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                allowfullscreen
                title="Vídeo de referência"></iframe>
        `;

        // Pede ao player do YouTube os eventos (onError): vídeo com
        // incorporação bloqueada pelo dono mostrava só "Este vídeo não está
        // disponível", parecendo defeito do U-Control
        const iframe = playerFrame.querySelector('iframe');
        iframe.addEventListener('load', () => {
            iframe.contentWindow.postMessage(JSON.stringify({ event: 'listening', id: 'uc-yt', channel: 'widget' }), 'https://www.youtube.com');
        });
        this.listenYoutubeErrors();

        this.container.querySelector('.yt-btn-external').href = `https://www.youtube.com/watch?v=${videoId}`;
        this.setHeader('video', 'Vídeo de referência');
        this.setFooterActions({ external: true, download: true, change: true });
        this.setSpeedVisible(true);
        this.show();
    }

    async downloadAudio() {
        if (!this.videoId) {
            alert('Nenhum vídeo carregado.');
            return;
        }

        const downloadBtn = this.container.querySelector('.yt-btn-download');
        const originalHtml = downloadBtn.innerHTML;

        try {
            downloadBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> <span class="yt-label">Baixando…</span>';
            downloadBtn.disabled = true;

            const songIdField = document.getElementById('song_id') || document.querySelector('input[name="song_id"]');
            const audioField = document.getElementById('audio_url');

            const response = await fetch('/download_audio', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url: `https://www.youtube.com/watch?v=${this.videoId}`,
                    song_id: songIdField ? songIdField.value : null,
                    old_audio_url: audioField ? audioField.value : null,
                })
            });

            // Sessão expirada: o login_required redireciona pra página de
            // login (HTML), e o .json() dava um erro sem sentido
            const isJson = (response.headers.get('content-type') || '').includes('application/json');
            if (!isJson) {
                throw new Error(response.redirected || response.status === 401
                    ? 'Sua sessão expirou. Entre de novo e tente outra vez.'
                    : `O servidor respondeu ${response.status}.`);
            }
            const data = await response.json();

            if (!data.success) throw new Error(data.error || 'Erro desconhecido');

            if (audioField) audioField.value = data.audio_url;
            this.loadLocalAudio(data.audio_url);
            alert('Áudio baixado.\n\nClique em Salvar para guardar na música.');
        } catch (error) {
            console.error('Erro ao baixar áudio:', error);
            alert(`Não deu pra baixar o áudio:\n${error.message}`);
        } finally {
            downloadBtn.innerHTML = originalHtml;
            downloadBtn.disabled = false;
        }
    }

    loadLocalAudio(audioUrl, songTitle = null, songAuthor = null) {
        const emptyState = this.container.querySelector('.yt-player-empty');
        const playerFrame = this.container.querySelector('#yt-player-frame');

        if (emptyState) emptyState.style.display = 'none';
        playerFrame.style.display = 'block';

        // Título e autor dos campos do formulário se não vierem
        if (!songTitle) songTitle = document.getElementById('title')?.value || 'Música';
        if (!songAuthor) songAuthor = document.getElementById('author')?.value || '';

        const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
        playerFrame.innerHTML = `
            <div class="audio-player-container">
                <div class="audio-player-info">
                    <div class="audio-player-art"><i class="fas fa-music"></i></div>
                    <div class="audio-player-details">
                        <div class="audio-player-title">${esc(songTitle)}</div>
                        ${songAuthor ? `<div class="audio-player-author">${esc(songAuthor)}</div>` : ''}
                    </div>
                </div>
                <audio controls class="local-audio-player" preload="metadata">
                    <source src="${esc(audioUrl)}" type="audio/mpeg">
                </audio>
                <div class="audio-player-badge"><i class="fas fa-circle-check"></i> Áudio guardado no U-Control</div>
            </div>
        `;

        const audioElement = playerFrame.querySelector('audio');
        if (audioElement) audioElement.playbackRate = this.playbackRate;

        this.videoId = null;
        this.setHeader('audio', 'Áudio de referência');
        // Já baixado: sem "Baixar"; "Trocar" põe outro vídeo do YouTube
        this.setFooterActions({ external: false, download: false, change: true });
        this.setSpeedVisible(true);
        this.show();
    }

    // Erros do player do YouTube (via postMessage, enablejsapi=1):
    // 101/150 = o dono não deixa tocar em outros sites; 100 = vídeo
    // removido ou privado; 2 = link inválido
    listenYoutubeErrors() {
        if (this._ytErrorListener) return;
        this._ytErrorListener = (e) => {
            if (!/^https:\/\/www\.youtube(-nocookie)?\.com$/.test(e.origin)) return;
            const iframe = this.container.querySelector('#yt-player-frame iframe');
            if (!iframe || e.source !== iframe.contentWindow) return;
            let data;
            try { data = typeof e.data === 'string' ? JSON.parse(e.data) : e.data; } catch (err) { return; }
            if (!data || data.event !== 'onError' || !this.videoId) return;
            const code = Number(data.info);
            const reason = (code === 101 || code === 150 || code === 152 || code === 153)
                ? 'O dono deste vídeo não deixa tocar fora do YouTube.'
                : code === 100 ? 'Este vídeo foi removido ou é privado.' : 'O YouTube não conseguiu tocar este vídeo.';
            this.showExternalLink(this.videoId, reason, code === 100 || code === 2);
        };
        window.addEventListener('message', this._ytErrorListener);
    }

    showExternalLink(videoId, reason = 'Este vídeo não deixa tocar fora do YouTube.', gone = false) {
        const emptyState = this.container.querySelector('.yt-player-empty');
        const playerFrame = this.container.querySelector('#yt-player-frame');

        playerFrame.style.display = 'none';
        playerFrame.innerHTML = '';

        // No editor: baixar o áudio resolve (fica guardado no U-Control e
        // toca aqui mesmo). Na cifra (somente leitura), só abrir no YouTube.
        const tip = !this.readOnly && !gone
            ? '<p class="yt-empty-tip">Use <b>Baixar áudio</b> para guardar o áudio no U-Control e ouvir aqui.</p>'
            : '';
        emptyState.style.display = 'block';
        emptyState.innerHTML = `
            <i class="fab fa-youtube yt-empty-icon"></i>
            <p>${reason}</p>
            ${gone ? '' : `<a href="https://www.youtube.com/watch?v=${videoId}" target="_blank" rel="noopener" class="yt-btn-add-video">
                <i class="fas fa-arrow-up-right-from-square"></i> Abrir no YouTube
            </a>`}
            ${tip}
        `;
        // Vídeo removido: não tem o que baixar
        this.setFooterActions({ external: false, download: !gone, change: !this.readOnly });
        this.setSpeedVisible(false);
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

    // Vale pro áudio baixado (<audio>) e pro vídeo do YouTube (comando via
    // postMessage, iframe com enablejsapi=1)
    setPlaybackRate(rate) {
        this.playbackRate = rate;
        const audio = this.container.querySelector('#yt-player-frame audio');
        if (audio) audio.playbackRate = rate;
        this.youtubeCommand('setPlaybackRate', [rate]);
    }

    youtubeCommand(func, args = []) {
        const iframe = this.container.querySelector('#yt-player-frame iframe');
        if (iframe && iframe.contentWindow) {
            iframe.contentWindow.postMessage(JSON.stringify({ event: 'command', func, args }), 'https://www.youtube.com');
        }
    }

    play() {
        const audio = this.container.querySelector('#yt-player-frame audio');
        if (audio) audio.play();
        else this.youtubeCommand('playVideo');
    }

    pause() {
        const audio = this.container.querySelector('#yt-player-frame audio');
        if (audio) audio.pause();
        else this.youtubeCommand('pauseVideo');
    }

    getCurrentTime() {
        const audio = this.container.querySelector('#yt-player-frame audio');
        return audio ? audio.currentTime : 0;
    }

    seekTo(seconds) {
        const audio = this.container.querySelector('#yt-player-frame audio');
        if (audio) audio.currentTime = seconds;
        else this.youtubeCommand('seekTo', [seconds, true]);
    }
}

// Exporta para uso global
window.YouTubeFloatingPlayer = YouTubeFloatingPlayer;
