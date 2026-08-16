const CONFIG = JSON.parse(document.getElementById('lyrics-config').textContent);
const songId = CONFIG.songId;
const rawSections = CONFIG.sections; // Seções da música do backend
const sheetData = CONFIG.sheetData; // Dados das partituras
let currentTheme = CONFIG.theme;

        // ── Tema visual ───────────────────────────────────────────────
        function atualizarBotaoTema() {
            const lbl = document.getElementById('btn-tema-label');
            lbl.textContent = currentTheme ? 'Tema ✓' : 'Tema';
        }
        atualizarBotaoTema();

        function abrirModalTema() {
            document.getElementById('modal-tema').style.display = 'block';
            if (currentTheme && currentTheme.url) {
                document.getElementById('tema-preview-img').src = currentTheme.url;
                document.getElementById('tema-preview').style.display = 'block';
            }
            carregarPastasTema();
        }

        function fecharModalTema() {
            document.getElementById('modal-tema').style.display = 'none';
        }

        function limparTema() {
            currentTheme = null;
            document.getElementById('tema-preview').style.display = 'none';
            salvarTema(null);
            fecharModalTema();
        }

        function salvarTema(theme) {
            fetch(`/api/lyrics/${songId}/theme`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({theme: theme})
            }).then(() => { atualizarBotaoTema(); })
              .catch(err => console.error('Erro ao salvar tema:', err));
        }

        function selecionarTema(url, type) {
            currentTheme = {type: type, url: url};
            document.getElementById('tema-preview-img').src = url;
            document.getElementById('tema-preview').style.display = 'block';
            salvarTema(currentTheme);
            fecharModalTema();
        }

        function aplicarCorTema() {
            const color = document.getElementById('cor-tema').value;
            currentTheme = { type: 'color', color: color };
            salvarTema(currentTheme);
            fecharModalTema();
            atualizarBotaoTema();
        }

        function aplicarCorPreset(color) {
            document.getElementById('cor-tema').value = color;
        }

        function aplicarGradiente(css) {
            currentTheme = { type: 'gradient', css: css };
            salvarTema(currentTheme);
            fecharModalTema();
            atualizarBotaoTema();
        }

        let pastaAtiva = 'Geral';
        function carregarPastasTema() {
            fetch('/api/image_folders')
                .then(r => r.json())
                .then(data => {
                    const all = Array.isArray(data) ? data : (data.folders || []);
                    const pastas = ['Geral', ...all.filter(f => f !== 'Geral')];
                    const foldersDiv = document.getElementById('tema-folders');
                    foldersDiv.innerHTML = pastas.map(p =>
                        `<button onclick="carregarImagensTema('${p}')"
                            style="padding:6px 14px;border-radius:20px;cursor:pointer;font-size:.8rem;
                            background:${p===pastaAtiva?'#7c3aed':'rgba(255,255,255,.08)'};
                            color:${p===pastaAtiva?'#fff':'#94a3b8'};border:1px solid rgba(255,255,255,.1);">
                            ${p}</button>`
                    ).join('');
                    carregarImagensTema(pastaAtiva);
                }).catch(() => carregarImagensTema('Geral'));
        }

        function carregarImagensTema(pasta) {
            pastaAtiva = pasta;
            document.querySelectorAll('#tema-folders button').forEach(b => {
                b.style.background = b.textContent.trim() === pasta ? '#7c3aed' : 'rgba(255,255,255,.08)';
                b.style.color = b.textContent.trim() === pasta ? '#fff' : '#94a3b8';
            });
            fetch(`/imagens?folder=${encodeURIComponent(pasta)}`)
                .then(r => r.json())
                .then(urls => {
                    const grid = document.getElementById('tema-grid');
                    if (!urls.length) {
                        grid.innerHTML = '<p style="color:#64748b;font-size:.85rem;">Nenhuma imagem nesta pasta.</p>';
                        return;
                    }
                    grid.innerHTML = urls.map(url => {
                        const active = currentTheme && currentTheme.url === url;
                        return `<div onclick="selecionarTema('${url}','image')"
                            style="cursor:pointer;border-radius:8px;overflow:hidden;
                            border:2px solid ${active?'#7c3aed':'transparent'};transition:border-color .2s;"
                            onmouseover="this.style.borderColor='#a78bfa'"
                            onmouseout="this.style.borderColor='${active?'#7c3aed':'transparent'}'">
                            <img src="${url}" style="width:100%;height:80px;object-fit:cover;border-radius:6px;display:block;">
                        </div>`;
                    }).join('');
                }).catch(() => {
                    document.getElementById('tema-grid').innerHTML =
                        '<p style="color:#64748b;font-size:.85rem;">Erro ao carregar imagens.</p>';
                });
        }

        document.getElementById('modal-tema').addEventListener('click', function(e) {
            if (e.target === this) fecharModalTema();
        });

        // ── Fundo do monitor (preto / branco) ───────────────────────
        let _displayBgDark = true;
        function _atualizarBtnBg() {
            const btn = document.getElementById('btn-bg');
            btn.innerHTML = (_displayBgDark ? '⬛' : '⬜') + ' Fundo';
            btn.style.background = _displayBgDark ? '#1e1e2e' : '#f1f5f9';
            btn.style.color = _displayBgDark ? '#fff' : '#1e293b';
        }
        fetch('/api/display-bg').then(r => r.json()).then(d => {
            _displayBgDark = d.dark !== false;
            _atualizarBtnBg();
        });
        function alternarFundoDisplay() {
            _displayBgDark = !_displayBgDark;
            _atualizarBtnBg();
            socket.emit('set_display_bg', { dark: _displayBgDark });
        }
        
        // Função para salvar estado das letras no banco
        function saveLyricsState(songId, sectionIndex) {
            fetch('/save_lyrics_state', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ song_id: songId, section_index: sectionIndex })
            }).catch(err => console.error('❌ Erro ao salvar estado:', err));
        }
        
        // Função para carregar estado salvo das letras
        function loadLyricsState() {
            fetch('/get_lyrics_state')
                .then(res => res.json())
                .then(state => {
                    console.log('💾 Estado das letras carregado:', state);
                    
                    // Se o estado é da música atual, carrega a seção salva
                    if (state.song_id === songId && state.section_index !== null) {
                        // Valida se o índice ainda existe (pode ter mudado após edição)
                        const validIndex = Math.min(state.section_index, sections.length - 1);
                        if (validIndex !== state.section_index) {
                            console.log(`⚠️ Seção ${state.section_index} não existe mais, carregando seção ${validIndex}`);
                        } else {
                            console.log(`🎯 Restaurando seção ${state.section_index}`);
                        }
                        loadSection(validIndex, false, true);
                    } else {
                        // Carrega primeira seção por padrão
                        loadSection(0, false, true);
                    }
                })
                .catch(err => {
                    console.error('❌ Erro ao carregar estado:', err);
                    loadSection(0, false, true); // Fallback para primeira seção
                });
        }
        
        // Detecta se um bloco de texto contém linhas de cifra (acordes)
        function temCifra(text) {
            const reAcorde = /^[\s]*[A-G][#b]?(?:m|maj|min|sus|aug|dim|add|M)?(?:\d+)?(?:\/[A-G][#b]?)?(?:\s+[A-G][#b]?(?:m|maj|min|sus|aug|dim|add|M)?(?:\d+)?(?:\/[A-G][#b]?)?)*[\s]*$/;
            return text.split('\n').some(line => line.trim() && reAcorde.test(line));
        }

        // Função para processar e separar seções por marcadores [TÍTULO]
        function processSections(rawSections) {
            const processedSections = [];
            
            rawSections.forEach(section => {
                // Verifica se é uma seção de partitura integrada no título
                if (section.title && section.title.includes('🎼 PARTITURA_INTEGRADA_')) {
                    // Extrai o ID da partitura do título
                    const sheetIdMatch = section.title.match(/PARTITURA_INTEGRADA_(\d+)/);
                    if (sheetIdMatch) {
                        const sheetId = parseInt(sheetIdMatch[1]);
                        processedSections.push({
                            title: '🎼 Partitura',
                            text: [''],
                            type: 'sheet',
                            sheetId: sheetId
                        });
                    }
                    return;
                }
                
                const fullText = section.text ? section.text.join('\n\n') : '';
                
                // Verifica se há marcações de partitura no texto
                if (fullText.includes('🎼 PARTITURA_INTEGRADA_')) {
                    // Divide o texto por marcações de partitura
                    const parts = fullText.split(/🎼 PARTITURA_INTEGRADA_(\d+)/);
                    
                    // Cria uma única seção com texto e partituras intercalados
                    const sectionContent = [];
                    const sheetIds = [];
                    
                    for (let i = 0; i < parts.length; i++) {
                        if (i % 2 === 0) {
                            // Parte de texto
                            const textContent = parts[i].trim();
                            if (textContent) {
                                sectionContent.push(textContent);
                            }
                        } else {
                            // ID da partitura (capturado pelo grupo do regex)
                            const sheetId = parseInt(parts[i]);
                            sheetIds.push(sheetId);
                        }
                    }
                    
                    // Adiciona uma única seção com texto e IDs das partituras
                    processedSections.push({
                        title: section.title || '',
                        text: sectionContent,
                        type: 'mixed', // Indica que tem texto e partitura
                        sheetIds: sheetIds
                    });
                    return;
                }
                
                // Detecta marcadores de seção no formato [TÍTULO]
                const sectionRegex = /\[([^\]]+)\]/g;
                const matches = [...fullText.matchAll(sectionRegex)];
                
                if (matches.length > 0) {
                    // Tem marcadores, divide o texto
                    let lastIndex = 0;
                    
                    matches.forEach((match, idx) => {
                        const sectionTitle = match[1];
                        const startIndex = match.index + match[0].length;
                        
                        // Pega o texto até o próximo marcador (ou até o final)
                        const nextMatch = matches[idx + 1];
                        const endIndex = nextMatch ? nextMatch.index : fullText.length;
                        const sectionContent = fullText.substring(startIndex, endIndex).trim();
                        
                        if (sectionContent) {
                            processedSections.push({
                                title: sectionTitle,
                                text: [sectionContent],
                                type: 'text'
                            });
                        }
                    });
                } else {
                    // Sem marcadores, usa a seção como está
                    if (fullText.trim()) {
                        processedSections.push({
                            title: section.title || '',
                            text: [fullText],
                            type: 'text'
                        });
                    }
                }
            });
            
            return processedSections;
        }
        
        const sections = processSections(rawSections);
        console.log('📊 Seções processadas:', sections);
        sections.forEach((s, i) => {
            console.log(`  Seção ${i}: title="${s.title}", type="${s.type}", sheetId=${s.sheetId || 'N/A'}`);
        });
        
        let currentSectionIndex = 0; // Índice da seção atual

        // ── Widget "Tom: X" estilo Cifra Club ────────────────────────
        // Transpõe tanto a prévia local (createSectionLinks/
        // renderSheetInSection) quanto o que é enviado ao vivo pro
        // monitor do músico via socket.io (loadSection) — as duas
        // sempre a partir do dado ORIGINAL em `sections`/`sheetData`
        // (nunca em cima de um resultado já transposto), mesma
        // estratégia "recalcula do zero" de view_song.html. Não salva no
        // servidor; tom persiste em localStorage por música.
        const TRANSPOSE_STORAGE_KEY = 'ucontrol_transpose_' + songId;
        let transposeOffset = parseInt(localStorage.getItem(TRANSPOSE_STORAGE_KEY), 10) || 0;

        function saveTransposeOffset() {
            try {
                if (transposeOffset === 0) localStorage.removeItem(TRANSPOSE_STORAGE_KEY);
                else localStorage.setItem(TRANSPOSE_STORAGE_KEY, String(transposeOffset));
            } catch (e) {
                // localStorage indisponível — transposição ainda funciona
                // nesta visita, só não persiste.
            }
        }

        // Texto bruto (não transposto) de uma seção, pra detectar o tom
        // original e servir de base fixa pra recalcular a cada clique.
        function rawSectionText(section) {
            return section.text ? section.text.join('\n\n') : '';
        }

        function transposedSectionText(section) {
            const raw = rawSectionText(section);
            return transposeOffset !== 0 ? ChordLines.transposeBlockContent(raw, transposeOffset) : raw;
        }

        const firstChordTokenRaw = ChordLines.detectFirstChordToken(sections.map(rawSectionText));

        function updateTomDisplay() {
            const tomEl = document.getElementById('tomAtual');
            if (!tomEl) return;
            if (!firstChordTokenRaw) { tomEl.textContent = '—'; return; }
            const token = transposeOffset !== 0
                ? ChordLines.transposeChord(firstChordTokenRaw, transposeOffset)
                : firstChordTokenRaw;
            const key = ChordLines.describeKey(token);
            tomEl.textContent = key || '—';
            const root = key ? key.replace(/m$/, '') : null;
            document.querySelectorAll('#tomGrid button[data-key]').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.key === root);
            });
        }

        // Reconstrói a lista de seções (texto + partituras) com o tom
        // atual e reenvia a seção ativa ao vivo, mantendo operador e
        // monitor do músico sincronizados.
        function refreshAfterTranspose() {
            $('#sections-list').empty();
            createSectionLinks();
            highlightActiveSection(currentSectionIndex);
            updateTomDisplay();
            saveTransposeOffset();
            loadSection(currentSectionIndex, true); // fromRemote=true: reenvia sem re-emitir section_changed
        }

        window.transposeStep = function(semitones) {
            transposeOffset += semitones;
            refreshAfterTranspose();
        };

        window.undoTranspose = function() {
            if (transposeOffset === 0) return;
            transposeOffset = 0;
            refreshAfterTranspose();
        };

        window.jumpToKey = function(targetRoot) {
            const tomEl = document.getElementById('tomAtual');
            const current = tomEl ? tomEl.textContent : null;
            if (!current || current === '—') return;
            const currentRoot = current.replace(/m$/, '');
            const currentIndex = ChordLines.chordMap[currentRoot];
            const targetIndex = ChordLines.chordMap[targetRoot];
            if (currentIndex === undefined || targetIndex === undefined) return;
            let delta = (targetIndex - currentIndex + 12) % 12;
            if (delta > 6) delta -= 12; // caminho mais curto, só estética
            if (delta === 0) return;
            window.transposeStep(delta);
        };

        window.toggleKeyGrid = function() {
            const panel = document.getElementById('tomPanel');
            if (!panel) return;
            const isHidden = getComputedStyle(panel).display === 'none';
            panel.style.display = isHidden ? 'block' : 'none';
        };

        document.addEventListener('click', function(e) {
            const widget = document.querySelector('.tom-widget');
            const panel = document.getElementById('tomPanel');
            if (!widget || !panel) return;
            if (getComputedStyle(panel).display === 'none') return;
            if (!widget.contains(e.target)) panel.style.display = 'none';
        });

        const socket = io();

        
    
        function loadFullLyrics() {
            $.getJSON(`/full-lyrics/${songId}`, function(data) {
                if (data.error) {
                    alert(data.error);
                    return;
                }
                $('#full-lyrics').text(data.lyrics);
            }).fail(function() {
                alert("Erro ao carregar a letra completa.");
            });
        }
    
        function createSectionLinks() {
            for (let i = 0; i < sections.length; i++) {
                const section = sections[i];
                
                const styleComment = t => t.split('\n').map(l =>
                    l.trim().startsWith('//')
                        ? `<span style="color:#64748b;font-style:italic;font-size:0.85em">${l}</span>`
                        : l
                ).join('\n');

                let content = '';
                if (section.type === 'mixed' && section.sheetIds && section.sheetIds.length > 0) {
                    // Seção mista: renderiza partitura + texto
                    const sectionText = styleComment(transposedSectionText(section));
                    content = `
                        <div id="sheet-render-${i}" style="padding:5px; background:#fff; margin:5px 0;"></div>
                        <pre class="section-preview" style="display:block; white-space:pre; overflow-x:auto; font-size:12px; margin:5px 0; font-family: ui-monospace, 'Cascadia Code', 'Source Code Pro', Menlo, Consolas, 'DejaVu Sans Mono', monospace;">${sectionText}</pre>
                    `;
                } else if (section.type === 'sheet') {
                    // É uma partitura - container para renderização
                    content = `<div id="sheet-render-${i}" style="padding:10px; background:#fff;"></div>`;
                } else {
                    // É texto normal
                    const sectionText = styleComment(transposedSectionText(section));
                    content = `<pre class="section-preview" style="white-space:pre; overflow-x:auto; font-family: ui-monospace, 'Cascadia Code', 'Source Code Pro', Menlo, Consolas, 'DejaVu Sans Mono', monospace; font-size:12px;">${sectionText}</pre>`;
                }
                
                const link = $(`
                    <div id="section-${i}" class="section-link">
                        <span class="section-title">${section.title || `Seção ${i + 1}`}</span>
                        ${content}
                    </div>
                `);
                link.click(function() {
                    loadSection(i);
                });
                $('#sections-list').append(link);
                
                // Se for partitura ou mista, renderiza automaticamente
                if (section.type === 'sheet') {
                    renderSheetInSection(i, section);
                } else if (section.type === 'mixed' && section.sheetIds && section.sheetIds.length > 0) {
                    // Renderiza a primeira partitura da seção mista
                    renderSheetInSection(i, { sheetId: section.sheetIds[0] });
                }
            }
        }
        
        // Função para renderizar partitura dentro do bloco de seção —
        // desenho delegado a static/js/sheet_render.js, compartilhado com
        // o editor (/sheet_editor) e as outras telas de exibição — ver
        // .claude/plans/harmonic-mixing-breeze.md. Antes disso essa função
        // reimplementava o layout/quebra de compasso à mão numa versão
        // mais antiga do VexFlow (4.2.2), sempre assumindo 4/4 fixo,
        // causando divergência visual em relação ao editor.
        async function renderSheetInSection(index, section) {
            const renderDiv = $(`#sheet-render-${index}`);

            const sheet = sheetData.find(s => s.id === section.sheetId);
            const hasContent = sheet && (
                (Array.isArray(sheet.measures) && sheet.measures.some(m => Array.isArray(m) ? m.length > 0 : true)) ||
                (Array.isArray(sheet.notes) && sheet.notes.length > 0)
            );
            if (!hasContent) {
                renderDiv.html('<p style="color:orange;">Partitura vazia</p>');
                return;
            }

            try {
                renderDiv.empty();
                const container = document.getElementById(`sheet-render-${index}`);
                const { renderSheetMusic, transposeSheetData } = await import(window.__sheetRenderURL || '/static/js/sheet_render.js');
                const toRender = transposeOffset !== 0 ? transposeSheetData(sheet, transposeOffset) : sheet;
                await renderSheetMusic(container, toRender, { maxWidth: 900 });
            } catch (error) {
                console.error('❌ Erro ao renderizar partitura:', error);
                renderDiv.html(`<p style="color:red;">Erro: ${error.message}</p>`);
            }
        }

// Função para limpar o conteúdo da exibição
const clearLyricsDisplay = () => {
    $('#section-text').empty(); // Limpa o conteúdo do <pre> onde a letra é exibida
    $('#section-title').empty(); // Limpa o título da música, se necessário
    localStorage.removeItem('currentTitle'); // Remove os dados salvos no localStorage
    localStorage.removeItem('currentText');
    localStorage.removeItem('currentSongId');
};

// Adiciona o evento de clique no botão "Limpar Letras"
$('#clear-lyrics').click(function() {
    clearLyricsDisplay(); // Chama a função para limpar
    socket.emit('clear_lyrics'); // Emite o evento para outros clientes, se necessário
});

    
        function separarNotas(rawText) {
            if (!rawText) return { texto: '', notas: '' };
            const linhas = rawText.split('\n');
            const notas  = linhas.filter(l => l.trim().startsWith('//')).map(l => l.trim().slice(2).trim());
            const texto  = linhas.filter(l => !l.trim().startsWith('//'));
            return { texto: texto.join('\n'), notas: notas.join(' · ') };
        }

        // silent=true: só atualiza a visualização LOCAL do operador (preview,
        // seção destacada) sem mandar nada pras telas — usado só pelo
        // restauro automático ao abrir/recarregar a página (loadLyricsState),
        // que antes reusava este mesmo caminho e acabava mandando ao vivo
        // sem nenhuma ação do operador (bug real reportado ao vivo,
        // 2026-08-16: abrir /lyrics/<id> mudava a tela pública sozinho).
        async function loadSection(index, fromRemote = false, silent = false) {
            if (index < 0 || index >= sections.length) {
                alert("Seção inválida.");
                return;
            }

            // Usa os dados locais das seções processadas (não precisa chamar o backend)
            const section = sections[index];

            // Precisa de transposeSheetData só quando a seção tem
            // partitura — import() dinâmico porque sheet_render.js é ES
            // module e esta página é script clássico (mesmo padrão já
            // usado em renderSheetInSection).
            const needsSheetTranspose = transposeOffset !== 0 &&
                ((section.type === 'mixed' && section.sheetIds && section.sheetIds.length > 0) ||
                 (section.type === 'sheet' && section.sheetId));
            const transposeSheetData = needsSheetTranspose
                ? (await import(window.__sheetRenderURL || '/static/js/sheet_render.js')).transposeSheetData
                : null;

            // Verifica o tipo de seção
            if (section.type === 'mixed' && section.sheetIds && section.sheetIds.length > 0) {
                // Seção mista: tem texto e partituras
                const sectionText = transposedSectionText(section);
                let sheets = section.sheetIds.map(id => sheetData.find(s => s.id === id)).filter(s => s);
                if (transposeSheetData) sheets = sheets.map(s => transposeSheetData(s, transposeOffset));

                const dataToSend = {
                    title: section.title || `Seção ${index + 1}`,
                    type: 'mixed',
                    text: sectionText,
                    sheets: sheets,
                    theme: null
                };

                console.log(`📤 Enviando seção mista ${index}:`, dataToSend);

                // Emite para o display via WebSocket com texto e partituras
                // (silent: só restaurando a visualização local, não manda ao vivo)
                if (!silent) socket.emit('update_lyrics', dataToSend);
                console.log(`✅ Seção mista ${index} carregada:`, section.title, `${sheets.length} partitura(s)`);
            } else if (section.type === 'sheet' && section.sheetId) {
                // Apenas partitura
                let sheet = sheetData.find(s => s.id === section.sheetId);
                if (sheet && transposeSheetData) sheet = transposeSheetData(sheet, transposeOffset);

                if (sheet) {
                    // Emite partitura para o display via WebSocket
                    if (!silent) socket.emit('update_lyrics', {
                        title: section.title || '🎼 Partitura',
                        type: 'sheet',
                        sheetData: sheet,
                        theme: null
                    });
                    console.log(`✅ Partitura ${index} carregada:`, section.title, sheet);
                } else {
                    console.warn(`⚠️ Dados da partitura ${section.sheetId} não encontrados`);
                }
            } else {
                // É uma seção de texto normal
                const sectionText = transposedSectionText(section);

                // Emite para o display via WebSocket (texto completo, incluindo linhas //)
                if (!silent) socket.emit('update_lyrics', {
                    title: section.title || `Seção ${index + 1}`,
                    type: 'text',
                    text: sectionText,
                    theme: currentTheme || null
                });
                console.log(`✅ Seção ${index} carregada:`, section.title);
            }
            
            highlightActiveSection(index);
            currentSectionIndex = index; // Atualiza o índice da seção atual
            
            // Ajusta fonte do conteúdo para não quebrar linha
            setTimeout(() => {
                ajustarFonteParaCabimento('.main-content');
            }, 100);
            
            // Salva estado das letras no banco de dados (bookmark do operador —
            // sempre roda, mesmo em silent, não afeta nenhuma tela sozinho)
            saveLyricsState(songId, currentSectionIndex);

            // Atualiza também o DisplayState para que o monitor siga
            // (silent: não é uma mudança de verdade, não deve mexer no que
            // está no ar)
            if (!silent) {
                const displayUrl = `/lyrics/display?song_id=${songId}&section=${currentSectionIndex}`;
                fetch('/save_display_state', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url1: displayUrl, url2: '' })
                }).catch(err => console.error('❌ Erro ao salvar display state:', err));
            }

            // Só emite section_changed se não veio de um evento remoto (evita loop)
            // nem for uma restauração silenciosa
            if (!fromRemote && !silent) {
                const nextSec  = sections[currentSectionIndex + 1] || null;
                const nextRaw  = nextSec ? (nextSec.text ? nextSec.text[0] || '' : '') : null;
                let nextClean = nextRaw !== null ? separarNotas(nextRaw).texto : null;
                if (nextClean && transposeOffset !== 0) nextClean = ChordLines.transposeBlockContent(nextClean, transposeOffset);
                const currRaw  = sections[currentSectionIndex]?.text?.[0] || '';
                const currObs  = separarNotas(currRaw).notas;
                socket.emit('section_changed', {
                    songId: songId,
                    sectionIndex: currentSectionIndex,
                    sectionTitles: sections.map(s => s.title),
                    total: sections.length,
                    nextTitle: nextSec ? nextSec.title : null,
                    nextText: nextClean,
                    currentObs: currObs
                });
            }
        }
    
        function highlightActiveSection(index) {
            $('.section-link').removeClass('active');
            const activeSection = $(`#section-${index}`);
            activeSection.addClass('active');
            
            // Scroll automático para manter a seção ativa visível na tela
            if (activeSection.length) {
                activeSection[0].scrollIntoView({
                    behavior: 'smooth',
                    block: 'center'  // Centraliza a seção na tela
                });
            }
        }
    
        // Botão para mostrar/esconder letras no monitor e public — parte do
        // estado real persistido no servidor (LyricsState.visible), não mais
        // assumido como true a cada carregamento da página; o HTML do botão
        // já nasce com o ícone/texto certos (ver templates/lyrics.html).
        //
        // Função de nível superior (fora do $(document).ready) de propósito:
        // o modal de leitura da Bíblia (lyrics_4.js) fica por cima de tudo
        // (z-index maior) e cobre o botão original — em vez de duplicar a
        // lógica, o botão de dentro do modal chama esta mesma função.
        // Atualiza TODO botão com a classe .lyrics-toggle-btn (pode ter mais
        // de um na página), pra os dois ficarem sempre em sincronia.
        let lyricsVisible = CONFIG.lyricsVisible !== false;

        function toggleLyricsVisibility() {
            lyricsVisible = !lyricsVisible;
            socket.emit('toggle_lyrics_visibility', { visible: lyricsVisible });

            document.querySelectorAll('.lyrics-toggle-btn').forEach(btn => {
                const icon = btn.querySelector('i');
                const text = btn.querySelector('.toggle-text');
                if (lyricsVisible) {
                    btn.classList.remove('show-mode');
                    if (icon) { icon.classList.remove('fa-eye-slash'); icon.classList.add('fa-eye'); }
                    if (text) text.textContent = 'Esconder';
                } else {
                    btn.classList.add('show-mode');
                    if (icon) { icon.classList.remove('fa-eye'); icon.classList.add('fa-eye-slash'); }
                    if (text) text.textContent = 'Mostrar';
                }
            });

            console.log(`👁️ Letras ${lyricsVisible ? 'mostradas' : 'escondidas'}`);
        }

        $(document).ready(function() {
            loadFullLyrics();
            createSectionLinks();
            updateTomDisplay();
            loadLyricsState(); // Carrega estado salvo (música + seção)
    
            $('#next').click(function() {
                if (currentSectionIndex < sections.length - 1) {
                    loadSection(currentSectionIndex + 1); // Carrega a próxima seção
                } else {
                    alert("Você já está na última seção.");
                }
            });
    
            $('#prev').click(function() {
                if (currentSectionIndex > 0) {
                    loadSection(currentSectionIndex - 1); // Carrega a seção anterior
                } else {
                    alert("Você já está na primeira seção.");
                }
            });
            
            $('#toggle-lyrics').click(toggleLyricsVisibility);

            // Adicionando a funcionalidade de navegação com as teclas "up" e "down"
            // Também suporta pedais Bluetooth (PageUp/PageDown, Space, Enter, etc.)
            $(document).keydown(function(event) {
                // Teclas para VOLTAR seção (pedal esquerdo)
                // ArrowUp, PageUp, ArrowLeft
                if (event.key === "ArrowUp" || event.key === "PageUp" || event.key === "ArrowLeft") {
                    event.preventDefault();
                    if (currentSectionIndex > 0) {
                        loadSection(currentSectionIndex - 1);
                    }
                } 
                // Teclas para AVANÇAR seção (pedal direito)
                // ArrowDown, PageDown, ArrowRight, Space, Enter
                else if (event.key === "ArrowDown" || event.key === "PageDown" || event.key === "ArrowRight" || event.key === " " || event.key === "Enter") {
                    // Ignora se estiver digitando em um input
                    if (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA') {
                        return;
                    }
                    event.preventDefault();
                    if (currentSectionIndex < sections.length - 1) {
                        loadSection(currentSectionIndex + 1);
                    }
                }
            });
    
            // Ouvir o evento de mudança de seção (de outros clientes)
            socket.on('section_changed', function(data) {
                if (data.songId === songId) { // Verifica se é a mesma música
                    loadSection(data.sectionIndex, true); // fromRemote=true para evitar loop
                }
            });
        });
