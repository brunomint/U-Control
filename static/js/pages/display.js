    const socket = io();

    socket.emit('identify', { role: 'lyrics_display' });

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
        
        $('#section-title').text(title);
        const _el = document.getElementById('section-text');
        applyChordColors(_el, text);

        // Música: sem quebra de linha (white-space: pre)
        $('#section-text').css('white-space', 'pre');
        
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
    const updateBibleDisplay = (reference, text) => {
        // Mostra texto, esconde partitura
        $('#sheet-container').hide();
        $('#section-text').show();
        
        $('#section-title').text(reference);
        $('#section-text').text(text);
        
        // Bíblia: com quebra de linha (white-space: pre-wrap)
        $('#section-text').css('white-space', 'pre-wrap');
        
        localStorage.setItem('currentTitle', reference);
        localStorage.setItem('currentText', text);
        localStorage.setItem('currentSongId', 'bible');
        shrink(); // Ajusta o tamanho do texto
    };

    /**
     * Função para ajustar dinamicamente o tamanho da fonte.
     */
     const shrink = () => {
    const textDiv = document.getElementById("lyrics");
    const sectionText = document.getElementById("section-text");
    let fontSize = Math.min(window.innerWidth / 10, 200); // Tamanho inicial da fonte baseado na largura da tela
    const minFontSize = 10; // Tamanho mínimo da fonte

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
                    const section = song.sections[sectionIndex || 0];
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
        
        // PRIORIDADE 2: localStorage (cache local)
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
        console.log('📖 Display recebeu update_bible:', data);
        
        // Formata o texto dos versículos
        let verseText = '';
        if (data.verses && Array.isArray(data.verses)) {
            verseText = data.verses.map(v => `${v.num} ${v.text}`).join('\n');
        } else if (data.text) {
            verseText = data.text;
        }
        
        // Exibe com quebra de linha para Bíblia
        updateBibleDisplay(data.reference || 'Bíblia', verseText);
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
        // Posiciona o next-section-box logo acima do song-map (altura variável por flex-wrap)
        requestAnimationFrame(() => {
            const nextBox = document.getElementById('next-section-box');
            if (nextBox) nextBox.style.bottom = el.offsetHeight + 'px';
        });
    }

    function escapeHtml(s) {
        return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    }

    socket.on('section_changed', (data) => {
        if (data.sectionTitles) _mapTitles = data.sectionTitles;
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

    });
    // Restaura preferência salva no servidor ao carregar
    fetch('/api/display-bg').then(r => r.json()).then(d => applyDisplayBg(d.dark !== false));

    socket.on('set_display_bg', (data) => {
        applyDisplayBg(data.dark !== false);
    });

    // Escuta eventos do servidor via WebSocket
    socket.on('update_lyrics', (data) => {
        console.log('📨 Display recebeu update_lyrics:', data);
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
    });
    
    // Função para renderizar partitura — desenho delegado a
    // static/js/sheet_render.js, compartilhado com o editor e as outras
    // telas de exibição (ver .claude/plans/harmonic-mixing-breeze.md).
    function renderSheet(title, sheetData) {
        console.log('🎼 Renderizando partitura:', title, sheetData);

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
        import('/static/js/sheet_render.js').then(({ renderSheetMusic }) =>
            renderSheetMusic(container, sheetData, { maxWidth: 900 })
        ).then(() => {
            console.log('✅ Partitura renderizada com sucesso!');
        }).catch(error => {
            console.error('❌ Erro ao renderizar partitura:', error);
            $('#sheet-container').html(`<p style="color:red; text-align:center; padding:40px;">Erro ao renderizar partitura:<br>${error.message}</p>`);
        });
    }
    
    // Função para renderizar seção mista com ordem preservada
    function renderMixedSectionOrdered(title, elements) {
        console.log('🎭 Renderizando seção mista ordenada:', title, elements);
        
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
                const textDiv = $('<pre></pre>')
                    .text(element.data)
                    .css({
                        'font-size': '24px',
                        'font-weight': 'bold',
                        'white-space': 'pre-wrap',
                        'margin': '0',
                        'font-family': 'Roboto, sans-serif'
                    });
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
        import('/static/js/sheet_render.js').then(({ renderSheetMusic }) =>
            renderSheetMusic(container, sheetData, { maxWidth: 900 })
        ).then(() => {
            console.log('✅ Seção mista renderizada com sucesso!');
            shrink();
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

    // Inicializa a aplicação ao carregar a página
    $(document).ready(initializeApp);
