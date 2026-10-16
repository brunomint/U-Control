    const socket = io();

    // host=monitor: esta página foi carregada dentro do iframe do /monitor
    // (ver monitor.js/blueprints/display.py, _release_kind) — identifica
    // como 'monitor' pra Modo Público/Monitor conseguir excluir/direcionar
    // esta aba junto com o /monitor em si (_get_monitor_sids em
    // connections.py). Sem o parâmetro (aberta direto, ou dentro do
    // preview do próprio /control), mantém o papel neutro de sempre —
    // excluir o /control do seu próprio preview quebraria a visualização
    // do operador.
    const _isMonitorHost = new URLSearchParams(window.location.search).get('host') === 'monitor';
    socket.emit('identify', { role: _isMonitorHost ? 'monitor' : 'lyrics_display' });

    /**
     * Atualiza o título e texto no DOM e no localStorage.
     * @param {string} title - O título da música.
     * @param {string} text - O texto da música.
     * @param {string} songId - O ID da música.
     */
    const updateLyricsDisplay = (title, text, songId) => {
        // Mostra texto, esconde partitura
        $('#sheet-container').hide();
        $('#section-text').show();
        _lastSheetCall = null; // sem partitura na tela, nada pra redesenhar num toggle de fundo
        
        $('#section-title').text(title).removeClass('bible-title');
        const _el = document.getElementById('section-text');
        applyChordColors(_el, text);

        // Música: sem quebra de linha (white-space: pre), fonte monoespaçada
        // (herdada do <pre>) — necessária pra alinhar cifra embaixo da
        // sílaba certa da letra. Bíblia não tem cifra, por isso troca pra
        // uma fonte normal só nesse modo (ver updateBibleDisplay).
        $('#section-text').css('white-space', 'pre').removeClass('bible-text');

        // Rodapé de versão (só faz sentido pra Bíblia — some ao voltar pra música)
        document.getElementById('bible-version').style.display = 'none';

        localStorage.setItem('currentTitle', title);
        localStorage.setItem('currentText', text);
        localStorage.setItem('currentSongId', songId);
        shrink(); // Ajusta o tamanho do texto
    };

    /**
     * Atualiza o display com texto da Bíblia (com quebra de linha).
     * @param {string} reference - A referência bíblica.
     * @param {string} text - O texto dos versículos.
     */
    const updateBibleDisplay = (reference, text, version) => {
        // Mostra texto, esconde partitura
        $('#sheet-container').hide();
        $('#section-text').show();

        $('#section-title').text(reference).addClass('bible-title');
        $('#section-text').text(text);

        // Bíblia: com quebra de linha (white-space: pre-wrap) e fonte normal
        // (não monoespaçada) — sem cifra pra alinhar, o <pre> herdado de
        // monospace só deixava o texto com cara de "código".
        $('#section-text').css('white-space', 'pre-wrap').addClass('bible-text');

        // Referência já vai no #section-title (igual Holyrics); versão
        // (ex: "ACF") no rodapé — só aparece se o remetente mandou essa
        // informação (telas antigas/sem tradução selecionada não mandam).
        const versionEl = document.getElementById('bible-version');
        if (version) {
            versionEl.textContent = version;
            versionEl.style.display = 'block';
        } else {
            versionEl.style.display = 'none';
        }

        localStorage.setItem('currentTitle', reference);
        localStorage.setItem('currentText', text);
        localStorage.setItem('currentSongId', 'bible');

        // Limpa o mapa de seções e a prévia da próxima seção — os dois só
        // são preenchidos pelo evento section_changed (música), e sem
        // isso ficavam mostrando a estrutura da última música mesmo com
        // um versículo bíblico na tela (bug real: rodapé "preso" na
        // música anterior).
        _mapTitles = [];
        _mapCurrent = -1;
        renderSongMap();
        document.getElementById('next-section-box').innerHTML = '';

        shrink(); // Ajusta o tamanho do texto
    };

    /**
     * Função para ajustar dinamicamente o tamanho da fonte.
     */
     const shrink = () => {
    const textDiv = document.getElementById("lyrics");
    const sectionText = document.getElementById("section-text");
    let fontSize = Math.min(window.innerWidth / 10, 200); // Tamanho inicial da fonte baseado na largura da tela
    // Mínimo só pra não zerar: caber na tela vale mais que legibilidade
    // num caso extremo (seção muito longa em tela baixa ou dividida) — com
    // 10px a cifra passava da tela e ficava cortada
    const minFontSize = 4;

    sectionText.style.fontSize = `${fontSize}px`;
    sectionText.style.fontWeight = 'bold';

    while (
        (textDiv.scrollHeight > textDiv.clientHeight || textDiv.scrollWidth > textDiv.clientWidth) &&
        fontSize > minFontSize
    ) {
        fontSize -= 1;
        sectionText.style.fontSize = `${fontSize}px`;
    }

    if (fontSize <= minFontSize) {
        console.warn("Texto muito grande para caber na tela.");
    }
};

// Encolhe a(s) partitura(s) renderizada(s) pra caber sem precisar de
// barra de rolagem — igual `shrink()` já faz pro texto, mas partitura
// não é redimensionável por font-size, então reduz width/height do SVG
// diretamente (o viewBox do VexFlow escala o desenho por dentro
// proporcionalmente). Usa width/height (não transform:scale) de
// propósito: transform não muda o tamanho de layout/scrollHeight, só o
// visual — não eliminaria a rolagem de verdade.
const fitSheetsToScreen = () => {
    const lyrics = document.getElementById('lyrics');
    const svgs = lyrics ? lyrics.querySelectorAll('#sheet-container svg') : [];
    if (!lyrics || !svgs.length) return;

    svgs.forEach(svg => {
        if (!svg.dataset.naturalWidth) {
            svg.dataset.naturalWidth = svg.getAttribute('width');
            svg.dataset.naturalHeight = svg.getAttribute('height');
        }
    });
    // Texto da seção mista (acordes embaixo da partitura) encolhe junto, na
    // mesma proporção: com o texto fixo em 24px, numa tela baixa (celular
    // deitado no app Android) só a partitura encolhia e virava uma tirinha
    const textos = lyrics.querySelectorAll('#sheet-container pre');
    textos.forEach(pre => {
        if (!pre.dataset.naturalFont) pre.dataset.naturalFont = parseFloat(getComputedStyle(pre).fontSize) || 24;
    });

    const apply = (scale) => {
        svgs.forEach(svg => {
            svg.style.width = (parseFloat(svg.dataset.naturalWidth) * scale) + 'px';
            svg.style.height = (parseFloat(svg.dataset.naturalHeight) * scale) + 'px';
        });
        textos.forEach(pre => {
            pre.style.fontSize = Math.max(8, parseFloat(pre.dataset.naturalFont) * scale) + 'px';
        });
    };

    // Reduz em passos, medindo scrollHeight/clientHeight de verdade a
    // cada volta — mais robusto que calcular a proporção necessária de
    // uma vez só (uma fórmula de proporção única erra fácil quando tem
    // outro conteúdo, tipo texto/título, misturado com a partitura).
    // Numa tela de exibição ao vivo ninguém vai rolar durante o culto,
    // então caber sem barra de rolagem importa mais que manter um
    // tamanho mínimo de legibilidade num caso extremo (música muito
    // longa numa tela muito baixa).
    const minScale = 0.02; // só evita tamanho zero/negativo, não limita legibilidade — caber é a prioridade
    let scale = 1;
    apply(scale);
    let guard = 60;
    while (lyrics.scrollHeight > lyrics.clientHeight && scale > minScale && guard-- > 0) {
        scale = Math.max(minScale, scale - 0.03);
        apply(scale);
    }
};



    /**
     * Carrega os dados iniciais de uma música via AJAX.
     * @param {string} songId - O ID da música.
     */
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
            error: (err) => {
                console.error('Erro ao carregar os dados iniciais:', err);
            }
        });
    };

    /**
     * Inicializa a aplicação, carregando dados salvos ou padrão.
     */
    const initializeApp = () => {
        // PRIORIDADE 1: Parâmetros da URL (vindo do monitor)
        const urlParams = new URLSearchParams(window.location.search);
        const songId = urlParams.get('song_id');
        const sectionIndex = urlParams.get('section');
        
        if (songId) {
            console.log(`🎵 Display: Carregando música ${songId}, seção ${sectionIndex || 0} (via URL)`);
            fetch(`/api/lyrics/${songId}`)
                .then(res => res.json())
                .then(song => {
                    console.log('✅ Display: Música carregada:', song);
                    const idx = parseInt(sectionIndex || 0, 10);
                    const section = song.sections[idx];
                    const next = song.sections[idx + 1];
                    const nextText = next ? (Array.isArray(next.text) ? next.text.join('\n') : (next.text || '')) : null;
                    renderFooter({
                        sectionTitles: song.sections.map(s => s.title),
                        sectionIndex: idx,
                        nextTitle: next ? next.title : null,
                        nextText: nextText,
                    });
                    console.log('📄 Display: Seção selecionada:', section);
                    
                    if (section) {
                        // Verifica se é uma seção de partitura no título
                        if (section.title && section.title.includes('🎼 PARTITURA_INTEGRADA_')) {
                            console.log('🎼 Display: Detectada partitura integrada no título!');
                            const sheetIdMatch = section.title.match(/PARTITURA_INTEGRADA_(\d+)/);
                            if (sheetIdMatch && song.sheet_data) {
                                const sheetId = parseInt(sheetIdMatch[1]);
                                const sheet = song.sheet_data.find(s => s.id === sheetId);
                                if (sheet) {
                                    console.log('🎵 Display: Renderizando partitura:', sheet);
                                    renderSheet('🎼 Partitura', sheet);
                                    return;
                                }
                            }
                        }
                        
                        // Prepara o texto da seção
                        let sectionText = '';
                        if (Array.isArray(section.text)) {
                            console.log('📋 Display: Array de texto:', section.text);
                            sectionText = section.text.filter(t => t && t.trim()).join('\n\n');
                        } else if (typeof section.text === 'string') {
                            sectionText = section.text;
                        }
                        
                        // Verifica se há marcação de partitura no texto
                        if (sectionText.includes('🎼 PARTITURA_INTEGRADA_')) {
                            console.log('🎼 Display: Detectada partitura integrada no texto!');
                            
                            // Divide o texto pela marcação da partitura para preservar a ordem
                            const parts = sectionText.split(/(🎼 PARTITURA_INTEGRADA_\d+)/);
                            const elements = [];
                            
                            parts.forEach(part => {
                                if (part.includes('🎼 PARTITURA_INTEGRADA_')) {
                                    // É uma marcação de partitura
                                    const sheetIdMatch = part.match(/PARTITURA_INTEGRADA_(\d+)/);
                                    if (sheetIdMatch && song.sheet_data) {
                                        const sheetId = parseInt(sheetIdMatch[1]);
                                        const sheet = song.sheet_data.find(s => s.id === sheetId);
                                        if (sheet) {
                                            elements.push({ type: 'sheet', data: sheet });
                                        }
                                    }
                                } else if (part.trim()) {
                                    // É texto
                                    elements.push({ type: 'text', data: part.trim() });
                                }
                            });
                            
                            console.log('🎵 Display: Renderizando seção mista com ordem preservada:', elements);
                            renderMixedSectionOrdered(section.title || 'Seção', elements);
                            return;
                        }
                        
                        console.log('📝 Display: Texto da seção (final):', sectionText);
                        console.log('📏 Display: Tamanho do texto:', sectionText.length);
                        
                        if (!sectionText || sectionText.trim() === '') {
                            console.warn('⚠️ Display: Seção sem texto! Mostrando mensagem padrão.');
                            sectionText = '(Seção vazia - adicione conteúdo no editor)';
                        }
                        
                        updateLyricsDisplay(section.title || `Seção ${sectionIndex || 0}`, sectionText);
                    }
                })
                .catch(err => console.error('❌ Erro ao carregar música:', err));
            return; // Não carrega do localStorage
        }
        
        // PRIORIDADE 2: o que está no ar agora, segundo o servidor (com o
        // rodapé). Antes ia direto pro localStorage, que só funciona no
        // mesmo navegador — o Pi recarregado ou a prévia do Controle ficavam
        // com outra letra, ou sem rodapé.
        fetch('/api/current-display')
            .then(r => r.json())
            .then(data => {
                if (data && data.mode === 'lyrics' && (data.text || data.sheetData || data.sheets)) {
                    onUpdateLyrics(data);
                    shrink();
                } else {
                    loadFromLocalCache();
                }
            })
            .catch(loadFromLocalCache);
    };

    // PRIORIDADE 3: localStorage (cache local, sem rede)
    const loadFromLocalCache = () => {
        const savedSongId = localStorage.getItem('currentSongId');
        const savedTitle = localStorage.getItem('currentTitle');
        const savedText = localStorage.getItem('currentText');

        if (savedSongId && savedTitle && savedText) {
            console.log('💾 Display: Carregando do localStorage');
            updateLyricsDisplay(savedTitle, savedText, savedSongId);
        } else if (savedSongId) {
            loadInitialLyrics(savedSongId);
        } else {
            console.warn("⚠️ Nenhum dado salvo encontrado.");
        }

        shrink(); // Ajusta o texto ao carregar
    };

    // Escuta eventos de versículos da Bíblia
    socket.on('update_bible', (data) => {
        // Cifra dentro do monitor: o versículo só vai pro palco liberado
        // pra ele, na página da Bíblia — a cifra dos músicos fica
        if (_isMonitorHost) return;
        console.log('📖 Display recebeu update_bible:', data);
        
        // Formata o texto dos versículos
        let verseText = '';
        if (data.verses && Array.isArray(data.verses)) {
            verseText = data.verses.map(v => `${v.num} ${v.text}`).join('\n');
        } else if (data.text) {
            verseText = data.text;
        }
        
        // Exibe com quebra de linha para Bíblia
        updateBibleDisplay(data.reference || 'Bíblia', verseText, data.version);
    });

    // Detecção de linha de cifra via ChordLines.isChordLine
    // (static/js/chord_lines.js) — mesma lógica robusta usada em toda
    // tela que lida com cifra no projeto (linha inteira, não palavra por
    // palavra). Aqui a linha de cifra é COLORIDA (mantida visível), não
    // eliminada — é a tela de retorno de palco, pros músicos.
    function temCifra(text) {
        return text.split('\n').some(l => l.trim() && ChordLines.isChordLine(l));
    }

    function applyChordColors(el, text) {
        el.textContent = '';
        if (!text) return;
        const lines = text.split('\n');
        lines.forEach((line, i) => {
            if (line.trim().startsWith('//')) {
                const span = document.createElement('span');
                span.className = 'private-note';
                span.textContent = '📝 ' + line.trim().slice(2).trim();
                el.appendChild(span);
            } else if (ChordLines.isChordLine(line)) {
                const span = document.createElement('span');
                span.className = 'chord';
                span.textContent = line;
                el.appendChild(span);
            } else {
                el.appendChild(document.createTextNode(line));
            }
            if (i < lines.length - 1) {
                el.appendChild(document.createTextNode('\n'));
            }
        });
    }

    let _bgDark = true; // espelha o estado atual de applyDisplayBg
    // Guarda a última chamada de renderSheet/renderMixedSectionOrdered
    // pra poder redesenhar com a cor certa quando o fundo alterna — a
    // partitura não é CSS-estilizável (VexFlow desenha a cor no SVG),
    // então precisa reprocessar com renderSheetMusic de novo.
    let _lastSheetCall = null;

    // Alterna fundo preto/branco
    function applyDisplayBg(dark) {
        _bgDark = dark;
        document.getElementById('media-layer').style.background = dark ? '#000' : '#fff';
        document.body.style.background = dark ? '#000' : '#fff';
        document.body.dataset.bg = dark ? 'dark' : 'light';
        document.getElementById('lyrics').style.color = dark ? '#fff' : '#000';
        document.getElementById('section-title').style.color = dark ? '#f87171' : '#b91c1c';
        document.documentElement.style.setProperty('--chord-color', dark ? '#fbbf24' : '#1d4ed8');
        document.getElementById('song-map').style.background =
            dark ? 'rgba(0,0,0,0.45)' : 'rgba(255,255,255,0.75)';
        document.documentElement.style.setProperty('--chip-active-bg', dark ? '#fbbf24' : '#1d4ed8');
        document.documentElement.style.setProperty('--chip-active-fg', dark ? '#000' : '#fff');

        // Redesenha a partitura (se houver) com a cor certa pro novo
        // fundo — precisa reprocessar porque a cor é desenhada dentro do
        // SVG pelo VexFlow, não vem de CSS.
        if (_lastSheetCall) {
            if (_lastSheetCall.type === 'single') renderSheet(_lastSheetCall.title, _lastSheetCall.sheetData);
            else renderMixedSectionOrdered(_lastSheetCall.title, _lastSheetCall.elements);
        }
    }

    // Mapa da música
    let _mapTitles = [];
    let _mapCurrent = -1;

    function renderSongMap() {
        const el = document.getElementById('song-map');
        if (!_mapTitles.length) { el.innerHTML = ''; return; }
        el.innerHTML = _mapTitles.map((t, i) =>
            `<span class="map-chip${i === _mapCurrent ? ' active' : ''}">${t}</span>`
        ).join('');
        // next-section-box e song-map ficam no fluxo normal (não fixed)
        // e nessa ordem no HTML — não precisa mais calcular/posicionar
        // via JS, o flex do body (#lyrics: flex:1) já abre espaço
        // automaticamente pras duas barras, em qualquer proporção de
        // tela (achado ao vivo: o cálculo de padding via JS que existia
        // antes não bastava numa tela bem larga/baixa).
    }

    function escapeHtml(s) {
        return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    }

    // Rodapé (mapa da música + "A seguir: …") vem junto com a seção que
    // entrou no ar (update_lyrics, ou /api/current-display ao abrir) — não
    // mais de section_changed, que a página da música emite ao PREPARAR (o
    // rodapé avançava antes da seção entrar e sumia em tela recarregada).
    function renderFooter(data) {
        _mapTitles = data.sectionTitles || [];
        _mapCurrent = data.sectionIndex ?? -1;
        renderSongMap();

        // Próximo slide
        const nextBox = document.getElementById('next-section-box');
        if (data.nextTitle != null) {
            // Mesmo ChordLines.isChordLine usado no resto do arquivo —
            // antes era uma 2ª regex diferente só pra esse preview,
            // divergente de _reAcorde (agora ChordLines.isChordLine) que
            // colore a exibição principal, risco de uma reconhecer uma
            // linha como cifra e a outra não pra o mesmo texto.
            const previewLines = (data.nextText || '')
                .split('\n')
                .map(l => l.trim())
                .filter(l => l && !l.startsWith('//') && !ChordLines.isChordLine(l))
                .slice(0, 3);
            const preview = previewLines.join('  /  ');
            nextBox.innerHTML =
                `<span class="next-label">A seguir:</span>` +
                `<span class="next-title">${escapeHtml(data.nextTitle)}</span>` +
                (preview ? `<span class="next-preview">${escapeHtml(preview)}</span>` : '');
            nextBox.style.display = 'block';
        } else {
            nextBox.style.display = 'none';
        }
    }
    // Restaura preferência salva no servidor ao carregar
    fetch('/api/display-bg').then(r => r.json()).then(d => applyDisplayBg(d.dark !== false));

    socket.on('set_display_bg', (data) => {
        applyDisplayBg(data.dark !== false);
    });

    // Escuta eventos do servidor via WebSocket
    socket.on('update_lyrics', (data) => onUpdateLyrics(data));
    const onUpdateLyrics = (data) => {
        console.log('📨 Display recebeu update_lyrics:', data);
        renderFooter(data);
        // Suprime tema no monitor interno se a seção tem linhas de acorde
        const theme = (data.type === 'text' && data.text && temCifra(data.text)) ? null : data.theme;
        const mediaImg   = document.getElementById('media-img');
        const mediaVideo = document.getElementById('media-video');
        if (theme && theme.type === 'image' && theme.url) {
            mediaVideo.pause(); mediaVideo.style.display = 'none';
            mediaImg.src = theme.url; mediaImg.style.display = 'block';
            document.getElementById('media-layer').style.background = '';
        } else if (theme && theme.type === 'video' && theme.url) {
            mediaImg.style.display = 'none';
            mediaVideo.src = theme.url; mediaVideo.style.display = 'block';
            mediaVideo.play().catch(() => {});
            document.getElementById('media-layer').style.background = '';
        } else if (theme && theme.type === 'color' && theme.color) {
            mediaImg.style.display = 'none';
            mediaVideo.pause(); mediaVideo.style.display = 'none';
            document.getElementById('media-layer').style.background = theme.color;
        } else if (theme && theme.type === 'gradient' && theme.css) {
            mediaImg.style.display = 'none';
            mediaVideo.pause(); mediaVideo.style.display = 'none';
            document.getElementById('media-layer').style.background = theme.css;
        } else {
            mediaImg.style.display = 'none';
            mediaVideo.pause(); mediaVideo.style.display = 'none';
            // Restaura o fundo do modo atual (não limpar para #000 do CSS)
            document.getElementById('media-layer').style.background = _bgDark ? '#000' : '#fff';
        }
        if (data.type === 'mixed' && data.sheets && data.sheets.length > 0) {
            // Seção mista: tem texto e partituras
            console.log('🎭 Detectado tipo: mixed (texto + partitura)');
            // Por enquanto, assume que a partitura vem antes do texto (ordem padrão)
            const elements = [
                { type: 'sheet', data: data.sheets[0] }
            ];
            if (data.text && data.text.trim()) {
                elements.push({ type: 'text', data: data.text });
            }
            renderMixedSectionOrdered(data.title, elements);
        } else if (data.type === 'sheet' && data.sheetData) {
            // É uma partitura
            console.log('🎵 Detectado tipo: sheet, chamando renderSheet()');
            renderSheet(data.title, data.sheetData);
        } else {
            // É texto normal
            console.log('📝 Detectado tipo: text, chamando updateLyricsDisplay()');
            updateLyricsDisplay(data.title, data.text, data.id);
        }
    };
    
    // Função para renderizar partitura — desenho delegado a
    // static/js/sheet_render.js, compartilhado com o editor e as outras
    // telas de exibição (ver .claude/plans/harmonic-mixing-breeze.md).
    function renderSheet(title, sheetData) {
        console.log('🎼 Renderizando partitura:', title, sheetData);
        _lastSheetCall = { type: 'single', title, sheetData };

        $('#section-text').hide();
        $('#sheet-container').show().empty();
        $('#section-title').text(title);

        const hasContent = sheetData && (
            (Array.isArray(sheetData.measures) && sheetData.measures.some(m => Array.isArray(m) ? m.length > 0 : true)) ||
            (Array.isArray(sheetData.notes) && sheetData.notes.length > 0)
        );
        if (!hasContent) {
            console.warn('⚠️ Partitura sem notas!');
            $('#sheet-container').html('<p style="color:orange; text-align:center; padding:40px;">Partitura vazia - sem notas para exibir</p>');
            return;
        }

        const container = document.getElementById('sheet-container');
        desenharPartituraGrande(container, sheetData).then(() => {
            console.log('✅ Partitura renderizada com sucesso!');
            fitSheetsToScreen();
        }).catch(error => {
            console.error('❌ Erro ao renderizar partitura:', error);
            $('#sheet-container').html(`<p style="color:red; text-align:center; padding:40px;">Erro ao renderizar partitura:<br>${error.message}</p>`);
        });
    }
    
    // Monitor: a partitura no MAIOR tamanho que cabe na tela. Tenta do
    // zoom maior pro menor — com zoom maior cabem menos compassos por
    // linha (o layout compact do sheet_render.js redistribui) — e fica
    // com o primeiro cuja altura cabe. Largura/altura do <svg> já saem
    // com o zoom (o viewBox continua o do desenho), então o
    // fitSheetsToScreen() de depois só encolhe se ainda sobrar texto.
    async function desenharPartituraGrande(container, sheetData) {
        const { renderSheetMusic } = await import(window.__sheetRenderURL || '/static/js/sheet_render.js');
        const lyrics = document.getElementById('lyrics');
        const availW = container.clientWidth || (lyrics.clientWidth - 20) || 900;
        const availH = lyrics.getBoundingClientRect().bottom - container.getBoundingClientRect().top - 16;
        // Sempre preto: a partitura fica num "papel" branco (display.css)
        const color = '#000';
        for (const zoom of [2.6, 2.2, 1.9, 1.65, 1.45, 1.3, 1.15, 1]) {
            await renderSheetMusic(container, sheetData, { maxWidth: Math.floor(availW / zoom), color, compact: true });
            const svg = container.querySelector('svg');
            if (!svg) return;
            const w = parseFloat(svg.getAttribute('width'));
            const h = parseFloat(svg.getAttribute('height'));
            if (h * zoom <= availH || zoom === 1) {
                if (!svg.getAttribute('viewBox')) svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
                svg.style.width = svg.style.maxWidth = svg.style.height = '';
                svg.setAttribute('width', Math.round(w * zoom));
                svg.setAttribute('height', Math.round(h * zoom));
                // Não deixa passar da borda direita do monitor (o container
                // pode começar um pouco pra dentro)
                const sobra = svg.getBoundingClientRect().right - (lyrics.getBoundingClientRect().right - 10);
                if (sobra > 0) {
                    const f = (w * zoom - sobra) / (w * zoom);
                    svg.setAttribute('width', Math.round(w * zoom * f));
                    svg.setAttribute('height', Math.round(h * zoom * f));
                }
                return;
            }
        }
    }

    // Função para renderizar seção mista com ordem preservada
    function renderMixedSectionOrdered(title, elements) {
        console.log('🎭 Renderizando seção mista ordenada:', title, elements);
        _lastSheetCall = { type: 'mixed', title, elements };

        $('#section-title').text(title);
        $('#section-text').hide();
        $('#sheet-container').show().empty();
        
        // Cria container principal para todos os elementos
        const mainContainer = $('<div></div>').css({
            'display': 'flex',
            'flex-direction': 'column',
            'gap': '20px',
            'padding': '10px'
        });
        
        // Renderiza cada elemento na ordem
        elements.forEach((element, index) => {
            if (element.type === 'text') {
                // Renderiza texto
                // Acordes coloridos como nas seções só de texto (antes ia
                // como texto puro e os acordes ficavam brancos)
                const textDiv = $('<pre></pre>')
                    .css({
                        'font-size': '24px',
                        'font-weight': 'bold',
                        'white-space': 'pre-wrap',
                        'margin': '0',
                        'font-family': 'Roboto, sans-serif'
                    });
                applyChordColors(textDiv[0], element.data);
                mainContainer.append(textDiv);
            } else if (element.type === 'sheet') {
                // Cria div para a partitura
                const sheetDiv = $('<div></div>').attr('id', `sheet-part-${index}`);
                mainContainer.append(sheetDiv);
            }
        });
        
        // Adiciona ao DOM primeiro
        $('#sheet-container').append(mainContainer);
        
        // Agora renderiza as partituras (depois que os divs estão no DOM)
        elements.forEach((element, index) => {
            if (element.type === 'sheet') {
                renderSheetInDiv(`sheet-part-${index}`, element.data);
            }
        });
    }
    
    // Função auxiliar para renderizar partitura em um div específico
    // Função auxiliar para renderizar partitura em um div específico —
    // mesmo módulo compartilhado usado em renderSheet() acima.
    function renderSheetInDiv(divId, sheetData) {
        const hasContent = sheetData && (
            (Array.isArray(sheetData.measures) && sheetData.measures.some(m => Array.isArray(m) ? m.length > 0 : true)) ||
            (Array.isArray(sheetData.notes) && sheetData.notes.length > 0)
        );
        if (!hasContent) {
            $(`#${divId}`).html('<p style="color:orange; text-align:center; padding:10px;">Partitura vazia</p>');
            shrink();
            return;
        }

        const container = document.getElementById(divId);
        // Mesmo motivo de renderSheet(): usa a largura real disponível
        // em vez de um valor fixo, pra minimizar quantos sistemas
        // (linhas) a partitura precisa, facilitando caber na tela.
        const availW = container.clientWidth || (document.getElementById('lyrics').clientWidth - 20) || 900;
        import(window.__sheetRenderURL || '/static/js/sheet_render.js').then(({ renderSheetMusic }) =>
            renderSheetMusic(container, sheetData, { maxWidth: availW, color: '#000', compact: true })
        ).then(() => {
            console.log('✅ Seção mista renderizada com sucesso!');
            shrink();
            fitSheetsToScreen();
        }).catch(error => {
            console.error('❌ Erro ao renderizar seção mista:', error);
            $('#sheet-container').html(`<p style="color:red; text-align:center; padding:20px;">Erro: ${error.message}</p>`);
            shrink();
        });
    }

// Chama a função shrink ao carregar a página
window.addEventListener('load', shrink);

// Chama a função shrink ao redimensionar a janela
window.addEventListener('resize', shrink);
window.addEventListener('resize', fitSheetsToScreen);

// E sempre que o espaço da letra mudar sem a janela mudar: rodapé
// ("A seguir", mapa) aparecendo/sumindo ou quebrando em mais linhas —
// antes a letra ficava do tamanho antigo e passava por baixo do rodapé.
if (window.ResizeObserver) {
    let lastBox = '';
    let pending = false;
    new ResizeObserver(() => {
        const l = document.getElementById('lyrics');
        const box = l.clientWidth + 'x' + l.clientHeight;
        if (box === lastBox || pending) return;
        lastBox = box;
        pending = true;
        requestAnimationFrame(() => { pending = false; shrink(); fitSheetsToScreen(); });
    }).observe(document.getElementById('lyrics'));
}

    // Inicializa a aplicação ao carregar a página
    $(document).ready(initializeApp);
