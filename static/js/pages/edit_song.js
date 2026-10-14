// new_song.js e edit_song.js compartilham a maior parte da lógica do editor de
// blocos/partitura (candidatos a um _song_editor.html futuro). Diferenças reais
// observadas na Fase 4.7: build do VexFlow (4.2.2-cjs aqui vs 4.2.3-cjs em
// new_song.js) e a regra .text-block do CSS (word-wrap/overflow, ver
// static/css/pages/edit_song.css vs new_song.css). Unificação num include
// compartilhado ficou fora de escopo — é refactor comportamental, não estrutural.

const CONFIG = JSON.parse(document.getElementById('edit-song-data').textContent);


        // Document ready function
        $(document).ready(function() {
            $('#songForm').submit(async function(event) {
                event.preventDefault();
                const { normalizeSheetData } = await import(window.__sheetRenderURL || '/static/js/sheet_render.js');

                console.log('📤 Enviando formulário...');
                console.log('🎼 Dados da partitura disponíveis:', window.currentSheetData);
                
                // Captura a estrutura de blocos do editor usando o array global que mantém a ordem
                console.log('🔍 Iniciando captura de dados do formulário...');
                
                const sectionsToSend = [];
                
                // Usa o array blocks global que já mantém a ordem correta dos blocos
                // Acessa o array blocks que está no escopo do editor (linha 2013)
                const editorBlocks = window.editorBlocks || [];
                
                console.log('🧱 Array blocks global:', editorBlocks);
                
                console.log('🧱 Blocos do editor:', editorBlocks);
                
                // Array para armazenar múltiplas partituras
                const sheetDataArray = [];
                
                // Converte os blocos do editor para o formato esperado pelo backend
                // Lógica: seção + próximo texto = uma seção com título e conteúdo
                let currentSection = null;
                
                editorBlocks.forEach((block, index) => {
                    console.log(`🔍 Processando bloco ${index}:`, block.type, block);
                    
                    if (block.type === 'section') {
                        // Se já existe uma seção pendente sem texto, adiciona ela vazia
                        if (currentSection) {
                            sectionsToSend.push(currentSection);
                            console.log(`📋 Seção anterior adicionada (vazia): "${currentSection.title}"`);
                        }
                        
                        // Cria nova seção pendente
                        currentSection = {
                            title: block.title || '',
                            text: []
                        };
                        console.log(`📋 Nova seção criada: "${block.title}"`);
                        
                    } else if (block.type === 'text') {
                        // Bloco de texto (NÃO usar trim para preservar espaços)
                        const content = block.content || '';
                        
                        if (currentSection) {
                            // Se existe seção pendente, adiciona o texto nela
                            if (content.trim()) { // Verifica se tem conteúdo, mas não remove espaços
                                currentSection.text.push(content);
                            }
                            sectionsToSend.push(currentSection);
                            console.log(`📝 Texto adicionado à seção "${currentSection.title}": ${content.substring(0, 50)}...`);
                            currentSection = null; // Limpa seção pendente
                        } else {
                            // Se não existe seção pendente, cria seção sem título
                            if (content.trim()) { // Verifica se tem conteúdo, mas não remove espaços
                                sectionsToSend.push({
                                    title: '',
                                    text: [content]
                                });
                                console.log(`📝 Texto adicionado sem seção: ${content.substring(0, 50)}...`);
                            }
                        }
                        
                    } else if (block.type === 'sheet') {
                        // Bloco de partitura
                        const sheetId = block.id || Date.now();
                        const sheetMarker = `🎼 PARTITURA_INTEGRADA_${sheetId}`;
                        
                        // Se existe seção pendente, adiciona a marcação da partitura no text dela
                        // MAS NÃO FECHA A SEÇÃO (mantém currentSection para próximos blocos de texto)
                        if (currentSection) {
                            currentSection.text.push(sheetMarker);
                            console.log(`🎼 Marcação de partitura adicionada à seção pendente "${currentSection.title}" (seção continua aberta)`);
                        } else if (sectionsToSend.length > 0) {
                            // Se não há seção pendente mas já existem seções enviadas, adiciona à última
                            const lastSection = sectionsToSend[sectionsToSend.length - 1];
                            lastSection.text.push(sheetMarker);
                            console.log(`🎼 Marcação de partitura adicionada à última seção "${lastSection.title}"`);
                        } else {
                            // Se não existe nenhuma seção, cria seção sem título com a marcação
                            sectionsToSend.push({
                                title: '',
                                text: [sheetMarker]
                            });
                            console.log(`🎼 Marcação de partitura adicionada em nova seção sem título`);
                        }
                        
                        // Tenta pegar dados de originalData primeiro, depois sheetData
                        let sheetDataToSave = null;
                        
                        // Prioriza originalData (já está no formato correto)
                        if (block.originalData) {
                            if (typeof block.originalData === 'string') {
                                try {
                                    sheetDataToSave = JSON.parse(block.originalData);
                                } catch (e) {
                                    console.error('❌ Erro ao parsear originalData:', e);
                                }
                            } else {
                                sheetDataToSave = block.originalData;
                            }
                        } else if (block.sheetData) {
                            // Fallback para sheetData
                            try {
                                sheetDataToSave = JSON.parse(block.sheetData);
                            } catch (e) {
                                console.error('❌ Erro ao parsear sheetData:', e);
                            }
                        }
                        
                        // Mantém o formato canônico (measures aninhado) em vez
                        // de achatar pra "notes" com perda de pausas/pontos/
                        // acidentes/ligaduras. normalizeSheetData entende
                        // tanto esse formato quanto o antigo (legado). Ver
                        // Fase 7 em .claude/plans/harmonic-mixing-breeze.md.
                        if (sheetDataToSave) {
                            console.log(`🔍 Dados da partitura ${sheetId}:`, sheetDataToSave);
                            const normalized = normalizeSheetData(sheetDataToSave);
                            const sheetEntry = { id: sheetId, ...normalized };
                            sheetDataArray.push(sheetEntry);
                            const noteCount = normalized.measures.reduce((n, m) => n + m.length, 0);
                            console.log(`🎼 Partitura ${sheetId} adicionada com ${noteCount} notas`);
                        } else {
                            console.warn(`⚠️ Partitura ${sheetId} sem dados`);
                        }
                    }
                });
                
                // Se ainda existe uma seção pendente no final, adiciona ela
                if (currentSection) {
                    sectionsToSend.push(currentSection);
                    console.log(`📋 Seção final adicionada: "${currentSection.title}"`);
                }
                
                // Se não houver blocos, cria um padrão
                if (sectionsToSend.length === 0) {
                    console.log('⚠️ Nenhum bloco encontrado, criando bloco padrão');
                    sectionsToSend.push({ title: '', text: [''] });
                }
                
                console.log('🧱 Estrutura de blocos capturada:', sectionsToSend);
                
                // Cria FormData personalizado
                const formData = new FormData();
                formData.append('title', document.getElementById('title').value);
                formData.append('author', document.getElementById('author').value);
                
                // Adiciona URLs de vídeo e áudio
                const videoUrl = document.getElementById('video_url')?.value || '';
                const audioUrl = document.getElementById('audio_url')?.value || '';
                if (videoUrl) {
                    formData.append('video_url', videoUrl);
                    console.log('🎬 Video URL incluída:', videoUrl);
                }
                if (audioUrl) {
                    formData.append('audio_url', audioUrl);
                    console.log('🎵 Audio URL incluída:', audioUrl);
                }
                
                // Adiciona seções estruturadas no formato esperado pelo backend
                sectionsToSend.forEach((section, index) => {
                    const sectionTitle = section.title || '';
                    const sectionText = section.text.length > 0 ? section.text.join('\n\n') : '';
                    
                    formData.append('sections[]', sectionTitle);
                    formData.append('texts[]', sectionText);
                    
                    console.log(`📋 Enviando seção ${index}:`, {
                        title: sectionTitle,
                        textLength: sectionText.length,
                        preview: sectionText.substring(0, 100) + (sectionText.length > 100 ? '...' : '')
                    });
                });
                
                console.log('📋 Total de seções enviadas:', sectionsToSend.length);
                
                console.log('📋 Dados estruturados preparados para envio');
                
                // Envia múltiplas partituras como array
                if (sheetDataArray.length > 0) {
                    const sheetDataString = JSON.stringify(sheetDataArray);
                    formData.append('sheet_data', sheetDataString);
                    console.log(`✅ ${sheetDataArray.length} partitura(s) adicionada(s) ao formulário`);
                    console.log('📊 Sheet data completo:', sheetDataString);
                    sheetDataArray.forEach((sheet, idx) => {
                        const noteCount = (sheet.measures || []).reduce((n, m) => n + m.length, 0);
                        console.log(`  📊 Partitura ${idx + 1} (ID: ${sheet.id}): ${noteCount} notas`);
                    });
                } else {
                    console.log('⚠️ Nenhum dado de partitura para enviar');
                }
                
                console.log('📋 Enviando dados estruturados...');
                
                $.ajax({
                        type: 'POST',
                        url: '/edit_song/' + CONFIG.songId,
                        data: formData,
                        processData: false,
                        contentType: false,
                        success: function(response) {
                            console.log('✅ Resposta do servidor:', response);
                            alert(response.message);
                            // Permanece na mesma página de edição (recarrega para atualizar dados)
                            window.location.reload();
                        },
                        error: function(xhr, status, error) {
                            console.error('❌ Erro no envio:', error);
                            console.error('📄 Resposta:', xhr.responseText);
                        }
                    });
                });

            
        }); // Fecha $(document).ready principal



        // Sistema de Editor de Blocos com SVG Integrado
        window.addEventListener('load', function() {
            console.log('🎼 Inicializando Editor de Blocos Integrado...');
            
            // ===== FUNCIONALIDADE SEPARAÇÃO AUTOMÁTICA DE LETRAS =====
            
            // Detecta se o texto tem linhas em branco (indicativo de estrofes)
            function hasBlankLines(text) {
                // Verifica se há linhas em branco que separam estrofes
                return /\n\s*\n/.test(text);
            }
            
            // Detecta se o texto parece ser uma letra de música
            function detectLyrics(text) {
                // Remove espaços extras e quebras de linha múltiplas
                const cleanText = text.trim().replace(/\n\s*\n/g, '\n\n');
                
                console.log('🔍 Analisando texto para detecção de letra...');
                console.log('📏 Comprimento:', cleanText.length);
                
                // Critérios básicos
                if (cleanText.length < 30) {
                    console.log('❌ Texto muito curto');
                    return false;
                }
                if (!cleanText.includes('\n')) {
                    console.log('❌ Sem quebras de linha');
                    return false;
                }
                if (cleanText.includes('http')) {
                    console.log('❌ Contém URLs');
                    return false;
                }
                if (cleanText.includes('cifraclub.com')) {
                    console.log('❌ Contém link do Cifra Club');
                    return false;
                }
                
                // Verifica se contém quebras de linha duplas (indicativo de estrofes)
                const hasDoubleLineBreaks = hasBlankLines(text);
                console.log('📄 Tem linhas em branco:', hasDoubleLineBreaks);
                
                // Verifica se contém palavras típicas de estrutura musical
                const musicalStructureWords = /\b(refrão|coro|verso|estrofe|ponte|intro|final|bis|primeira parte|pré-refrão|segunda parte)\b/i;
                const hasMusicalStructure = musicalStructureWords.test(cleanText);
                console.log('🎵 Tem estrutura musical:', hasMusicalStructure);
                
                // Verifica se contém acordes musicais (cifras)
                const chordPattern = /\b[A-G][#b]?[m]?[0-9]?[\/A-G#b]*\b/g;
                const hasChords = chordPattern.test(cleanText);
                console.log('🎸 Tem acordes/cifras:', hasChords);
                
                // Verifica se tem indicadores de tom
                const hasTone = /Tom:\s*[A-G][#b]?/i.test(cleanText);
                console.log('🎼 Tem indicação de tom:', hasTone);
                
                // Verifica se tem seções entre colchetes
                const hasSections = /\[[^\]]+\]/g.test(cleanText);
                console.log('📋 Tem seções em colchetes:', hasSections);
                
                // Verifica se tem múltiplas linhas (mais de 3)
                const lineCount = cleanText.split('\n').length;
                const hasMultipleLines = lineCount >= 3;
                console.log('📊 Múltiplas linhas:', hasMultipleLines, `(${lineCount} linhas)`);
                
                // Verifica se não é apenas uma lista ou código (mas exclui seções musicais)
                const looksLikeCode = /^\s*[\{<]/.test(cleanText) || /[\}>]\s*$/.test(cleanText);
                const looksLikeList = /^\s*[-*•]/.test(cleanText);
                
                // Se tem seções musicais entre colchetes, não é código
                const hasMusicSections = /\[(intro|refrão|coro|verso|estrofe|ponte|final|bis|primeira parte|pré-refrão|segunda parte)\]/i.test(cleanText);
                
                console.log('💻 Parece código/lista:', looksLikeCode || looksLikeList);
                console.log('🎵 Tem seções musicais:', hasMusicSections);
                
                // Se parece código MAS tem seções musicais, provavelmente é letra
                if ((looksLikeCode || looksLikeList) && !hasMusicSections) {
                    console.log('❌ Rejeitado: parece código/lista sem seções musicais');
                    return false;
                }
                
                // NOVA LÓGICA MELHORADA: Múltiplos critérios para identificar letras
                const criteria = {
                    hasBlankLines: hasDoubleLineBreaks,
                    hasMusicalStructure: hasMusicalStructure,
                    hasChords: hasChords,
                    hasTone: hasTone,
                    hasSections: hasSections,
                    hasMusicSections: hasMusicSections,
                    hasMultipleLines: hasMultipleLines
                };
                
                console.log('📊 Critérios atendidos:', criteria);
                
                // Se tem linhas em branco + múltiplas linhas = muito provável
                if (hasDoubleLineBreaks && hasMultipleLines) {
                    console.log('✅ Aprovado: linhas em branco + múltiplas linhas');
                    return true;
                }
                
                // Se tem acordes/cifras + múltiplas linhas = letra com cifra
                if (hasChords && hasMultipleLines) {
                    console.log('✅ Aprovado: acordes + múltiplas linhas');
                    return true;
                }
                
                // Se tem seções musicais + múltiplas linhas = letra estruturada
                if ((hasMusicalStructure || hasSections || hasMusicSections) && hasMultipleLines) {
                    console.log('✅ Aprovado: estrutura musical + múltiplas linhas');
                    return true;
                }
                
                // Se tem indicação de tom = definitivamente música
                if (hasTone && hasMultipleLines) {
                    console.log('✅ Aprovado: indicação de tom + múltiplas linhas');
                    return true;
                }
                
                console.log('❌ Não atendeu aos critérios de letra de música');
                return false;
            }
            
            // Separa a letra em seções automaticamente
            function separateLyricsIntoSections(text) {
                // Remove só linhas em branco do início/fim — trim() sozinho
                // cortaria o espaço de indentação do primeiro acorde (ver
                // apararPreservandoIndentacao acima).
                const cleanText = apararPreservandoIndentacao(text);
                
                console.log('🔄 Iniciando separação de seções...');
                console.log('📄 Texto original:', cleanText);
                
                // PRIORIDADE 1: Separa por quebras de linha duplas (linhas em branco)
                let sections = cleanText.split(/\n\s*\n/);
                console.log('📊 Seções encontradas por linhas em branco:', sections.length);
                
                // Se encontrou seções por linhas em branco, usa essa separação
                if (sections.length > 1) {
                    console.log('✅ Separação por linhas em branco bem-sucedida!');
                    sections = sections
                        .map(section => apararPreservandoIndentacao(section))
                        .filter(section => section.length > 0);
                    return sections;
                }
                
                // PRIORIDADE 2: Tenta separar por seções entre colchetes [Intro], [Refrão], etc.
                const bracketSections = /\n(?=\s*\[[^\]]+\])/g;
                if (bracketSections.test(cleanText)) {
                    console.log('✅ Separação por seções em colchetes!');
                    sections = cleanText.split(bracketSections);
                    sections = sections
                        .map(section => apararPreservandoIndentacao(section))
                        .filter(section => section.length > 0);
                    return sections;
                }
                
                // PRIORIDADE 3: Tenta separar por marcadores de seção explícitos
                const sectionMarkers = /\n(?=\s*(Refrão|Coro|Verso|Estrofe|Ponte|Intro|Final|Bis|Primeira Parte|Pré-Refrão|Segunda Parte)\s*:?\s*\n)/gi;
                if (sectionMarkers.test(cleanText)) {
                    console.log('✅ Separação por marcadores explícitos!');
                    sections = cleanText.split(sectionMarkers);
                    sections = sections
                        .map(section => apararPreservandoIndentacao(section))
                        .filter(section => section.length > 0);
                    return sections;
                }
                
                // PRIORIDADE 3: Separação inteligente por padrões de linha
                const lines = cleanText.split('\n');
                console.log('📏 Total de linhas:', lines.length);
                
                if (lines.length > 6) {
                    console.log('⚙️ Tentando separação inteligente...');
                    sections = [];
                    let currentSection = [];
                    
                    for (let i = 0; i < lines.length; i++) {
                        const line = lines[i];
                        
                        // Se a linha está vazia, pode ser um separador
                        if (line.trim() === '') {
                            if (currentSection.length > 0) {
                                sections.push(currentSection.join('\n'));
                                currentSection = [];
                            }
                        } else {
                            currentSection.push(line);
                        }
                        
                        // Se chegou ao final, adiciona a última seção
                        if (i === lines.length - 1 && currentSection.length > 0) {
                            sections.push(currentSection.join('\n'));
                        }
                    }
                    
                    // Se não conseguiu separar bem, tenta por tamanho
                    if (sections.length <= 1) {
                        console.log('⚙️ Separação por tamanho de seção...');
                        sections = [];
                        currentSection = [];
                        
                        for (let i = 0; i < lines.length; i++) {
                            currentSection.push(lines[i]);
                            
                            // Separa a cada 4-6 linhas
                            if (currentSection.length >= 4 || i === lines.length - 1) {
                                if (currentSection.some(line => line.trim() !== '')) {
                                    sections.push(currentSection.join('\n'));
                                }
                                currentSection = [];
                            }
                        }
                    }
                }
                
                // Limpa e filtra seções vazias
                sections = sections
                    .map(section => apararPreservandoIndentacao(section))
                    .filter(section => section.length > 0);
                
                console.log('🎯 Seções finais:', sections.length);
                sections.forEach((section, i) => {
                    console.log(`📝 Seção ${i + 1}:`, section.substring(0, 50) + '...');
                });
                
                return sections;
            }
            
            // Detecta e sugere títulos para seções baseado no conteúdo
            function suggestSectionTitle(content, index) {
                const lowerContent = content.toLowerCase();
                
                // Verifica se tem seção entre colchetes [Intro], [Refrão], etc.
                const bracketMatch = content.match(/^\s*\[([^\]]+)\]/i);
                if (bracketMatch) {
                    return bracketMatch[1].trim();
                }
                
                // Verifica se já tem um título explícito
                const explicitTitles = /^\s*(refrão|coro|verso|estrofe|ponte|intro|final|bis|primeira parte|pré-refrão|segunda parte)\s*:?/i;
                const match = content.match(explicitTitles);
                if (match) {
                    return match[1].charAt(0).toUpperCase() + match[1].slice(1).toLowerCase();
                }
                
                // Sugere títulos baseado no padrão e posição
                if (index === 0) {
                    if (lowerContent.includes('intro') || content.length < 50) {
                        return 'Intro';
                    }
                    return 'Verso 1';
                }
                
                // Verifica se parece ser um refrão (texto repetitivo ou com palavras-chave)
                const chorusKeywords = /\b(refrão|coro|chorus|hey|oh|yeah|na na|la la)\b/i;
                if (chorusKeywords.test(content)) {
                    return 'Refrão';
                }
                
                // Verifica se é uma ponte
                if (lowerContent.includes('ponte') || (index > 2 && content.length < 100)) {
                    return 'Ponte';
                }
                
                // Verifica se é o final
                if (index >= 3 && (lowerContent.includes('final') || lowerContent.includes('fim'))) {
                    return 'Final';
                }
                
                // Padrão padrão: alterna entre verso e refrão
                if (index % 2 === 0) {
                    return `Verso ${Math.floor(index / 2) + 1}`;
                } else {
                    return 'Refrão';
                }
            }
            
            // Processa a letra colada e cria seções automaticamente
            // blockIndex: caixa de texto onde a letra foi colada — só ela (e o
            // título logo acima) dá lugar às seções novas; o resto da música
            // fica. Sem blockIndex (letra digitada no prompt), substitui tudo.
            async function processLyrics(text, blockIndex = null) {
                try {
                    console.log('🎵 Processando letra de música...');
                    
                    const sections = separateLyricsIntoSections(text);
                    
                    if (sections.length <= 1) {
                        console.log('❌ Não foi possível separar em seções automaticamente');
                        return false;
                    }
                    
                    console.log(`✅ Letra separada em ${sections.length} seções`);
                    
                    // Limpa o editor atual
                    const anteriores = blocks;
                    blocks = [];
                    selectedBlocks.clear();
                    
                    // Cria blocos para cada seção
                    sections.forEach((sectionContent, index) => {
                        // Adiciona bloco de seção (título)
                        const sectionTitle = suggestSectionTitle(sectionContent, index);
                        blocks.push({
                            type: 'section',
                            title: sectionTitle,
                            id: Date.now() + index * 1000
                        });
                        
                        // Remove título explícito do conteúdo se existir — só
                        // engole espaços/tabs na MESMA linha do marcador antes
                        // da quebra (não \s* genérico), senão come também o
                        // espaço que posiciona o primeiro acorde da linha
                        // seguinte.
                        let cleanContent = sectionContent;

                        // Remove seções entre colchetes do início
                        cleanContent = cleanContent.replace(/^\s*\[[^\]]+\][ \t]*\n?/i, '');

                        // Remove títulos explícitos do início
                        cleanContent = cleanContent.replace(/^\s*(refrão|coro|verso|estrofe|ponte|intro|final|bis|primeira parte|pré-refrão|segunda parte)[ \t]*:?[ \t]*\n?/i, '');

                        // Remove indicação de tom se estiver no início
                        cleanContent = cleanContent.replace(/^\s*Tom:[ \t]*[A-G][#b]?[ \t]*\n?/i, '');

                        cleanContent = apararPreservandoIndentacao(cleanContent);
                        
                        // Adiciona bloco de texto
                        blocks.push({
                            type: 'text',
                            content: cleanContent,
                            id: Date.now() + index * 1000 + 500
                        });
                    });
                    
                    let primeiraNova = 0;
                    if (blockIndex !== null) {
                        const novas = blocks;
                        blocks = anteriores;
                        let inicio = blockIndex, quantos = 1;
                        const titulo = blocks[blockIndex - 1];
                        if (titulo && titulo.type === 'section') {
                            // a seção onde colou vira a 1ª seção nova; se já
                            // tinha nome, o nome fica
                            inicio = blockIndex - 1;
                            quantos = 2;
                            if ((titulo.title || '').trim()) novas[0].title = titulo.title;
                        }
                        blocks.splice(inicio, quantos, ...novas);
                        primeiraNova = inicio;
                    }

                    // Re-renderiza o editor e mostra a 1ª seção nova
                    renderBlocks(true);
                    const primeira = document.querySelector(`#blockEditor [data-block-index="${primeiraNova}"]`);
                    if (primeira) primeira.scrollIntoView({ block: 'start', behavior: 'smooth' });
                    
                    console.log('🎉 Letra processada e organizada em seções!');
                    return true;
                    
                } catch (error) {
                    console.error('❌ Erro ao processar letra:', error);
                    return false;
                }
            }
            
            // ===== EDITOR DE BLOCOS INTEGRADO =====
            
            let blocks = [
                { type: 'section', title: '', id: Date.now() },
                { type: 'text', content: '', id: Date.now() + 1 }
            ];
            let selectionMode = false;
            let selectedBlocks = new Set();
            let currentSheetData = null;
            // Escopo: 'all' (música inteira, como sempre foi) ou 'sections'
            // (só as seções marcadas no painel do Tom — ex.: subir meio tom
            // só no último refrão). Cada seção leva junto os blocos de texto
            // e as partituras dela (título até o próximo título).
            let transposeScope = 'all';
            // Seções marcadas, guardadas pelo objeto do título (sobrevive a
            // subir/descer/renomear); 'inicio' = blocos antes do 1º título
            const transposeSelected = new Set();
            
            // Expõe o array blocks globalmente para o formulário poder acessá-lo.
            // Getter, não cópia da referência: colar letra, importar do Cifra
            // Club e "Limpar tudo" trocam o array inteiro (blocks = [...]) e a
            // referência antiga fazia o Salvar gravar a versão anterior.
            Object.defineProperty(window, 'editorBlocks', {
                configurable: true,
                get: () => blocks,
                set: (v) => { blocks = v; },
            });
            
            // Elementos
            const blockContainer = document.getElementById('blockContainer');
            const hiddenTextarea = document.getElementById('entrada');
            
            // Renderiza todos os blocos
            // skipFocus: se true, não foca em nenhum elemento (usado ao deletar para manter scroll)
            function renderBlocks(skipFocus = false) {
                console.log('🎨 renderBlocks() chamada! Total de blocos:', blocks.length);
                console.log('📦 Container:', blockContainer);
                // Redesenhar apaga tudo e as caixas de texto nascem com 50px —
                // a página encolhe e o navegador sobe a rolagem. Segura a altura
                // e a rolagem até as caixas voltarem ao tamanho certo.
                const keepScrollY = window.scrollY;
                blockContainer.style.minHeight = blockContainer.offsetHeight + 'px';
                blockContainer.innerHTML = '';
                
                blocks.forEach((block, index) => {
                    console.log(`🧱 Renderizando bloco ${index}:`, block.type, block);
                    // Adiciona botão de inserção antes do bloco (exceto no primeiro)
                    if (index > 0) {
                        const insertButton = createInsertButton(index);
                        blockContainer.appendChild(insertButton);
                    }
                    
                    // Adiciona o bloco
                    if (block.type === 'text') {
                        const textBlock = createTextBlock(block, index);
                        textBlock.dataset.blockIndex = index;
                        blockContainer.appendChild(textBlock);
                    } else if (block.type === 'sheet') {
                        const sheetBlock = createSheetBlock(block, index);
                        sheetBlock.dataset.blockIndex = index;
                        blockContainer.appendChild(sheetBlock);
                    } else if (block.type === 'section') {
                        const sectionBlock = createSectionBlock(block, index);
                        sectionBlock.dataset.blockIndex = index;
                        blockContainer.appendChild(sectionBlock);
                    }
                });
                
                // Adiciona botão de inserção no final
                const finalInsertButton = createInsertButton(blocks.length);
                blockContainer.appendChild(finalInsertButton);

                // Altura certa das caixas de texto já agora (o ajuste do
                // createTextBlock só roda depois, tarde demais pra rolagem)
                blockContainer.querySelectorAll('textarea.text-block').forEach(ta => {
                    if (ta._chordSync) ta._chordSync();
                    ta.style.height = 'auto';
                    ta.style.height = ta.scrollHeight + 'px';
                });
                blockContainer.style.minHeight = '';
                window.scrollTo(0, keepScrollY);

                // Atualiza campo oculto
                updateHiddenField();
                updateTomDisplay();
            }

            // Atualiza o rótulo "Tom: X" com base no primeiro acorde
            // encontrado nos blocos de texto, na ordem em que aparecem
            // (ChordLines.detectFirstChordToken/describeKey, static/js/
            // chord_lines.js) — não é infalível (uma música pode não
            // começar no acorde de tônica), mas funciona sem precisar de
            // nenhum dado extra cadastrado sobre a música.
            function updateTomDisplay() {
                const tomEl = document.getElementById('tomAtual');
                if (!tomEl) return;
                const contents = blocks.filter(b => b.type === 'text').map(b => b.content);
                const firstChord = ChordLines.detectFirstChordToken(contents);
                const key = firstChord ? ChordLines.describeKey(firstChord) : null;
                tomEl.textContent = key || '—';

                // Grade, lista de seções e rótulo do painel do Tom (destaca
                // o tom da música inteira ou das seções marcadas)
                renderTomScope();
            }

            // Expõe a função globalmente para o script de carregamento
            window.renderBlocksFunction = renderBlocks;
            
            // Cria botão de inserção entre blocos
            function createInsertButton(position) {
                const container = document.createElement('div');
                container.style.cssText = 'text-align: center; margin: 5px 0; position: relative;';
                
                const button = document.createElement('button');
                button.type = 'button'; // Importante: evita submit do formulário
                button.innerHTML = '<i class="fas fa-plus"></i>';
                button.title = 'Inserir bloco aqui';
                button.className = 'insert-btn';
                
                // Menu de opções (inicialmente oculto)
                const menu = document.createElement('div');
                menu.style.cssText = `
                    position: absolute;
                    top: 35px;
                    left: 50%;
                    transform: translateX(-50%);
                    background: var(--uc-surface-2);
                    border: 1px solid var(--uc-line);
                    color: var(--uc-text);
                    border-radius: 8px;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                    padding: 8px;
                    display: none;
                    z-index: 1000;
                    min-width: 200px;
                `;
                
                // Opções do menu
                const options = [
                    { icon: 'fas fa-font', text: 'Bloco de Texto', action: () => insertBlockAt(position, 'text') },
                    { icon: 'fas fa-heading', text: 'Seção (Coro, Verso...)', action: () => insertBlockAt(position, 'section') },
                    { icon: 'fas fa-music', text: 'Partitura', action: () => insertBlockAt(position, 'sheet') }
                ];
                
                options.forEach(option => {
                    const optionDiv = document.createElement('div');
                    optionDiv.style.cssText = `
                        padding: 8px 12px;
                        cursor: pointer;
                        border-radius: 4px;
                        display: flex;
                        align-items: center;
                        gap: 8px;
                        transition: background 0.2s ease;
                    `;
                    optionDiv.innerHTML = `<i class="${option.icon}"></i> ${option.text}`;
                    
                    optionDiv.addEventListener('mouseenter', () => {
                        optionDiv.style.background = 'var(--uc-surface-3)';
                    });
                    
                    optionDiv.addEventListener('mouseleave', () => {
                        optionDiv.style.background = 'transparent';
                    });
                    
                    optionDiv.addEventListener('click', (e) => {
                        e.preventDefault(); // Evita submit do formulário
                        e.stopPropagation();
                        option.action();
                        menu.style.display = 'none';
                        button.style.opacity = '0.7';
                    });
                    
                    menu.appendChild(optionDiv);
                });
                
                // Event listeners do botão
                button.addEventListener('mouseenter', () => {
                    button.style.opacity = '1';
                    button.style.transform = 'scale(1.1)';
                });
                
                button.addEventListener('mouseleave', () => {
                    if (menu.style.display === 'none') {
                        button.style.opacity = '0.7';
                        button.style.transform = 'scale(1)';
                    }
                });
                
                button.addEventListener('click', (e) => {
                    e.preventDefault(); // Evita submit do formulário
                    e.stopPropagation();
                    const isVisible = menu.style.display === 'block';
                    
                    // Fecha todos os outros menus
                    document.querySelectorAll('.insert-menu').forEach(m => m.style.display = 'none');
                    
                    menu.style.display = isVisible ? 'none' : 'block';
                    button.style.opacity = isVisible ? '0.7' : '1';
                });
                
                // Fecha menu ao clicar fora
                document.addEventListener('click', () => {
                    menu.style.display = 'none';
                    button.style.opacity = '0.7';
                });
                
                menu.className = 'insert-menu';
                container.appendChild(button);
                container.appendChild(menu);
                
                return container;
            }
            
            // Insere bloco na posição especificada
            function insertBlockAt(position, type) {
                let newBlock;
                
                if (type === 'text') {
                    newBlock = { type: 'text', content: '', id: Date.now() };
                } else if (type === 'section') {
                    const sectionName = prompt('Nome da seção (ex: Coro, Verso 1, Ponte...):', 'Coro');
                    if (!sectionName) return;
                    newBlock = { type: 'section', title: sectionName, id: Date.now() };
                    // Seção já vem com o bloco de texto embaixo
                    blocks.splice(position, 0, newBlock, { type: 'text', content: '', id: Date.now() + 1 });
                    newBlock = null;
                } else if (type === 'sheet') {
                    newBlock = { type: 'sheet', content: '', id: Date.now() };
                }
                
                // Salva a posição do scroll antes de re-renderizar
                const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
                
                // Insere o bloco na posição correta
                if (newBlock) blocks.splice(position, 0, newBlock);
                
                // Re-renderiza
                renderBlocks(true); // skipFocus=true para manter posição do scroll
                
                // Restaura a posição do scroll após re-renderizar
                requestAnimationFrame(() => {
                    window.scrollTo(0, scrollTop);
                });
                
                console.log(`✅ Bloco ${type} inserido na posição ${position}`);
            }
            
            // Cria bloco de texto
            function createTextBlock(block, index) {
                const container = document.createElement('div');
                container.style.cssText = 'position: relative; margin: 10px 0;';
                
                const div = document.createElement('textarea');
                div.className = 'text-block';
                div.style.cssText = `padding: ${selectionMode ? '10px 10px 10px 35px' : '10px'}; min-height: 50px; outline: none; border: none; background: var(--uc-surface-2); border: 1px solid var(--uc-line); border-radius: 6px; white-space: pre; overflow-x: auto; overflow-y: hidden; width: 100%; resize: none; line-height: 1.4; box-sizing: border-box; color: var(--uc-text);`;
                div.setAttribute('placeholder', 'Digite a letra da música...');
                div.setAttribute('wrap', 'off');
                div.value = block.content || '';
                ChordHighlight.attach(div);
                
                // Função para ajustar altura automaticamente
                const adjustHeight = () => {
                    div.style.height = 'auto';
                    div.style.height = div.scrollHeight + 'px';
                };
                
                // Ajusta altura inicial
                setTimeout(adjustHeight, 0);
                
                // Event listeners
                div.addEventListener('input', () => {
                    const content = div.value;
                    blocks[index].content = content;
                    updateHiddenField();
                    updateTomDisplay();
                    adjustHeight();
                });
                
                // Ctrl+Enter: quebra o texto no cursor e abre uma nova seção
                // (nome + texto) com o que estava abaixo do cursor
                div.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter' && e.ctrlKey) {
                        e.preventDefault();
                        const before = div.value.slice(0, div.selectionStart).replace(/\n+$/, '');
                        const after = div.value.slice(div.selectionEnd).replace(/^\n+/, '');
                        blocks[index].content = before;
                        addSectionBlock(index + 1, after);
                    }
                });
                
                
                // Checkbox de seleção
                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.style.cssText = `position: absolute; top: 10px; left: 10px; z-index: 10; display: ${selectionMode ? 'block' : 'none'};`;
                checkbox.checked = selectedBlocks.has(index);
                checkbox.onchange = () => toggleBlockSelection(index);
                
                // Controles de ação
                const controls = document.createElement('div');
                controls.className = 'text-controls';
                controls.style.cssText = `position: absolute; top: 5px; right: 5px; opacity: 1; display: ${selectionMode ? 'none' : 'block'};`;
                
                const deleteBtn = document.createElement('button');
                deleteBtn.type = 'button'; // Evita submit do formulário
                deleteBtn.innerHTML = '<i class="fas fa-trash-can"></i>';
                deleteBtn.title = 'Excluir bloco';
                deleteBtn.style.cssText = 'background: var(--uc-danger-soft); color: var(--uc-danger); border: 1px solid transparent; border-radius: 6px; padding: 5px 9px; cursor: pointer; font-size: 14px; ';
                deleteBtn.onclick = (e) => {
                    e.preventDefault(); // Evita submit do formulário
                    e.stopPropagation();
                    deleteBlock(index);
                };
                
                controls.appendChild(deleteBtn);
                container.appendChild(checkbox);
                container.appendChild(div);
                container.appendChild(controls);
                
                // Mostra controles no hover
                container.addEventListener('mouseenter', () => controls.style.opacity = '1');
                container.addEventListener('mouseleave', () => controls.style.opacity = '0');
                
                return container;
            }
            
            // Cria bloco de partitura
            function createSheetBlock(block, index) {
                const div = document.createElement('div');
                div.className = 'sheet-block';
                div.style.cssText = 'padding: 15px; background: #fff; border: 1px solid var(--uc-line); border-radius: 8px; margin: 10px 0; position: relative; text-align: center;';
                
                // Container para a partitura
                const sheetContainer = document.createElement('div');
                sheetContainer.id = `sheet-preview-${block.id}`;
                sheetContainer.style.cssText = 'min-height: 120px; display: flex; align-items: center; justify-content: center;';
                
                // Cria os controles primeiro (antes de usar)
                const controls = document.createElement('div');
                controls.className = 'sheet-controls';
                controls.style.cssText = 'position: absolute; top: 5px; right: 5px; opacity: 1;';
                
                const editBtn = document.createElement('button');
                editBtn.type = 'button';
                editBtn.textContent = '✏️';
                editBtn.title = 'Editar';
                editBtn.style.cssText = 'background: rgba(0,0,0,0.7); color: white; border: none; border-radius: 3px; padding: 4px 8px; margin-left: 4px; cursor: pointer; font-size: 12px;';
                editBtn.onclick = (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    editSheet(index);
                };
                
                const deleteBtn = document.createElement('button');
                deleteBtn.type = 'button';
                deleteBtn.innerHTML = '<i class="fas fa-trash-can"></i>';
                deleteBtn.title = 'Excluir';
                deleteBtn.style.cssText = 'background: var(--uc-danger-soft); color: var(--uc-danger); border: 1px solid transparent; border-radius: 6px; padding: 5px 9px; margin-left: 4px; cursor: pointer; font-size: 14px; ';
                deleteBtn.onclick = (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    deleteBlock(index);
                };
                
                controls.appendChild(editBtn);
                controls.appendChild(deleteBtn);
                
                // Renderiza a partitura se tiver dados — desenho delegado a
                // static/js/sheet_render.js, compartilhado com o editor e as
                // telas de exibição (ver .claude/plans/harmonic-mixing-breeze.md).
                // createSheetBlock() precisa devolver `div` de forma síncrona
                // (renderBlocks() faz appendChild logo em seguida), então o
                // desenho em si roda em segundo plano (fire-and-forget) depois
                // que o container já está no DOM — mesmo padrão usado nas
                // Fases 4/5.
                const originalData = block.originalData;
                const hasContent = originalData && (
                    (Array.isArray(originalData.measures) && originalData.measures.some(m => Array.isArray(m) ? m.length > 0 : true)) ||
                    (Array.isArray(originalData.notes) && originalData.notes.length > 0)
                );
                if (hasContent) {
                    import(window.__sheetRenderURL || '/static/js/sheet_render.js').then(({ renderSheetMusic }) =>
                        renderSheetMusic(sheetContainer, originalData, { maxWidth: 600 })
                    ).then(() => {
                        const svg = sheetContainer.querySelector('svg');
                        if (svg) {
                            svg.style.cssText = 'max-width: 100%; height: auto; background: white; border-radius: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);';
                        }
                    }).catch(error => {
                        console.error('Erro ao renderizar partitura:', error);
                        sheetContainer.innerHTML = '<p style="color: #999; font-style: italic;">Erro ao renderizar partitura</p>';
                    });
                } else {
                    sheetContainer.innerHTML = '<p style="color: #999; font-style: italic;">Partitura sem dados</p>';
                }
                
                div.appendChild(sheetContainer);
                div.appendChild(controls);
                
                // Mostra controles no hover
                div.addEventListener('mouseenter', () => controls.style.opacity = '1');
                div.addEventListener('mouseleave', () => controls.style.opacity = '0');
                
                return div;
            }
            
            // Cria bloco de seção
            function createSectionBlock(block, index) {
                const div = document.createElement('div');
                div.className = 'section-block';
                div.style.cssText = `background: var(--uc-accent-soft); color: var(--uc-accent-text); padding: 9px 14px; margin: 18px 0 8px 0; border-radius: 8px; font-weight: 800; font-size: 13px; letter-spacing: .06em; text-transform: uppercase; position: relative; border: ${selectedBlocks.has(index) ? '3px solid #f2b84b' : 'none'}; border-left: 3px solid var(--uc-accent);`;
                
                // Checkbox de seleção
                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.style.cssText = `position: absolute; top: 12px; left: 15px; z-index: 10; display: ${selectionMode ? 'block' : 'none'}; transform: scale(1.2);`;
                checkbox.checked = selectedBlocks.has(index);
                checkbox.onchange = () => toggleBlockSelection(index);
                
                // Input para o título da seção
                const input = document.createElement('input');
                input.type = 'text';
                input.placeholder = 'Nome da seção (ex: Verso 1, Coro, Estrofe...)';
                input.value = block.title || '';
                input.style.cssText = `background: transparent; border: none; color: var(--uc-accent-text); font-weight: bold; font-size: 16px; width: calc(100% - ${selectionMode ? '120px' : '180px'}); outline: none; margin-left: ${selectionMode ? '25px' : '0'};`;
                
                // Event listener para atualizar título
                input.addEventListener('input', () => {
                    blocks[index].title = input.value;
                    updateHiddenField();
                });
                
                // Enter no nome da seção pula pro texto logo abaixo;
                // Alt+↑/↓ move a seção inteira
                input.addEventListener('keydown', (e) => {
                    if (e.altKey && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) {
                        e.preventDefault();
                        moveSection(index, e.key === 'ArrowUp' ? -1 : 1);
                        return;
                    }
                    if (e.key !== 'Enter') return;
                    e.preventDefault();
                    const ta = document.querySelector(`#blockEditor [data-block-index="${index + 1}"] textarea`);
                    if (ta) { ta.focus(); ta.setSelectionRange(0, 0); }
                });
                
                // Controles
                const controls = document.createElement('div');
                controls.className = 'section-controls';
                controls.style.cssText = `position: absolute; top: 50%; transform: translateY(-50%); right: 8px; display: ${selectionMode ? 'none' : 'flex'};`;
                
                // Subir / descer / duplicar a seção inteira (título + blocos
                // até a próxima seção) e excluir só o título
                const groups = sectionGroups();
                const groupPos = groups.findIndex(g => g.start === index);
                const addBtn = (icon, title, onClick, extraClass, disabled) => {
                    const btn = document.createElement('button');
                    btn.type = 'button'; // Evita submit do formulário
                    btn.className = 'sec-btn' + (extraClass ? ' ' + extraClass : '');
                    btn.innerHTML = `<i class="fas ${icon}"></i>`;
                    btn.title = title;
                    btn.setAttribute('aria-label', title);
                    btn.disabled = !!disabled;
                    btn.onclick = (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        onClick();
                    };
                    controls.appendChild(btn);
                };
                addBtn('fa-arrow-up', 'Subir seção (Alt+↑)', () => moveSection(index, -1), '', groupPos <= 0);
                addBtn('fa-arrow-down', 'Descer seção (Alt+↓)', () => moveSection(index, 1), '', groupPos === groups.length - 1);
                addBtn('fa-clone', 'Duplicar seção', () => duplicateSection(index));
                addBtn('fa-trash-can', 'Excluir título da seção', () => deleteBlock(index), 'danger');
                
                div.appendChild(checkbox);
                div.appendChild(input);
                div.appendChild(controls);
                
                return div;
            }
            
            // Adiciona bloco de texto
            function addTextBlock(position = -1) {
                if (position === -1) position = blocks.length;
                blocks.splice(position, 0, { type: 'text', content: '', id: Date.now() });
                renderBlocks(true);

                const ta = document.querySelector(`#blockEditor [data-block-index="${position}"] textarea`);
                if (ta) {
                    ta.focus({ preventScroll: true });
                    ta.scrollIntoView({ block: 'center', behavior: 'smooth' });
                }
            }
            
            // Adiciona uma seção já com o bloco de texto logo abaixo e põe o
            // cursor no nome da seção
            function addSectionBlock(position = -1, text = '') {
                if (position === -1) position = blocks.length;
                const now = Date.now();
                blocks.splice(position, 0,
                    { type: 'section', title: '', id: now },
                    { type: 'text', content: text, id: now + 1 });
                renderBlocks(true);
                
                const input = document.querySelector(`#blockEditor [data-block-index="${position}"] input[type="text"]`);
                if (input) {
                    input.focus({ preventScroll: true });
                    input.scrollIntoView({ block: 'center', behavior: 'smooth' });
                }
            }
            
            // Adiciona bloco de partitura
            function addSheetBlock() {
                const svgData = localStorage.getItem('vexflow_sheet_svg');
                const sheetData = localStorage.getItem('vexflow_sheet_data');
                
                if (!svgData) {
                    alert('❌ Nenhuma partitura encontrada. Crie uma partitura primeiro!');
                    return;
                }
                
                // Verifica se há dados válidos (não apenas uma partitura vazia)
                if (sheetData) {
                    try {
                        const parsed = JSON.parse(sheetData);
                        if (parsed.measures && parsed.measures.length > 0 && parsed.measures[0].length === 0) {
                            alert('⚠️ A partitura está vazia. Adicione algumas notas antes de inserir!');
                            return;
                        }
                    } catch (e) {
                        console.warn('Erro ao verificar dados da partitura:', e);
                    }
                }
                
                // Salva a posição do scroll antes de re-renderizar
                const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
                
                console.log('📊 Dados capturados do localStorage:');
                console.log('SVG:', svgData ? 'Presente' : 'Ausente');
                console.log('JSON:', sheetData ? 'Presente' : 'Ausente');
                
                const newBlock = { 
                    type: 'sheet', 
                    svgData: svgData,
                    sheetData: sheetData, // Salva como string mesmo
                    originalData: sheetData, // Backup dos dados originais
                    id: Date.now()
                };
                blocks.push(newBlock);
                renderBlocks(true); // skipFocus=true para manter posição do scroll
                
                // Restaura a posição do scroll após re-renderizar
                requestAnimationFrame(() => {
                    window.scrollTo(0, scrollTop);
                });
                
                console.log('✅ Bloco de partitura adicionado com dados:', newBlock);
            }
            
            // Edita partitura
            function editSheet(index) {
                // Salva dados da partitura atual no localStorage para o editor carregar
                const currentBlock = window.editorBlocks[index];
                console.log('🔍 Editando partitura do bloco:', index, currentBlock);
                console.log('🔍 Total de blocos:', window.editorBlocks.length);
                console.log('🔍 Todos os blocos:', window.editorBlocks);
                
                if (currentBlock && (currentBlock.originalData || currentBlock.sheetData)) {
                    // LIMPA localStorage COMPLETAMENTE primeiro para evitar cache antigo
                    localStorage.clear();
                    console.log('🧹 localStorage completamente limpo');
                    
                    // Salva o SVG atual para o editor poder carregar
                    localStorage.setItem('vexflow_sheet_svg', currentBlock.svgData);
                    console.log('💾 SVG salvo no localStorage');
                    
                // Usa os dados originais se existirem — normalizeSheetData
                // (static/js/sheet_render.js, compartilhado com o editor e as
                // telas de exibição, ver .claude/plans/harmonic-mixing-breeze.md)
                // entende tanto o formato canônico (measures aninhado) quanto
                // o antigo (notes achatado, de antes da Fase 1), então
                // substitui a conversão manual que só entendia o campo
                // "notes" — ficou quebrada quando o campo virou "measures".
                if (currentBlock.originalData || currentBlock.sheetData) {
                    const originalData = currentBlock.originalData || JSON.parse(currentBlock.sheetData);
                    console.log('📊 Dados originais da partitura:', originalData);

                    const hasContent =
                        (Array.isArray(originalData.measures) && originalData.measures.some(m => Array.isArray(m) ? m.length > 0 : true)) ||
                        (Array.isArray(originalData.notes) && originalData.notes.length > 0);
                    if (!hasContent) {
                        console.log('⚠️ Dados vazios detectados - não salvando');
                        alert('⚠️ Esta partitura está vazia. Crie algumas notas primeiro!');
                        return;
                    }

                    import(window.__sheetRenderURL || '/static/js/sheet_render.js').then(({ normalizeSheetData }) => {
                        const convertedData = normalizeSheetData(originalData);
                        const dataToSave = JSON.stringify(convertedData);
                        localStorage.setItem('vexflow_sheet_data', dataToSave);
                        console.log('💾 Dados convertidos e salvos no localStorage:', dataToSave);
                        openSheetEditorPopup();
                    });
                    return; // abre o popup só depois do import() acima resolver
                } else {
                    console.log('⚠️ Criando dados básicos para edição');
                    const basicData = JSON.stringify({
                        clef: 'treble',
                        keySig: 'C',
                        timeSig: '4/4',
                        measures: [[{pitch: 'C/4', duration: 'q'}]], // Adiciona uma nota básica
                        ties: [],
                        chords: []
                    });
                    localStorage.setItem('vexflow_sheet_data', basicData);
                    console.log('💾 Dados básicos salvos:', basicData);
                }
                } else {
                    console.log('❌ Nenhuma partitura encontrada no bloco');
                }

                openSheetEditorPopup();

                function openSheetEditorPopup() {
                // Abre editor VexFlow
                const vexWindow = window.open('/sheet_editor', 'VexFlowEditor', 'width=1200,height=800,scrollbars=yes,resizable=yes');
                
                // Monitora fechamento
                const checkClosed = setInterval(async () => {
                    if (vexWindow.closed) {
                        clearInterval(checkClosed);

                        console.log('🎼 Editor VexFlow fechado, capturando dados...');

                        // Captura dados da partitura para persistência — mantém
                        // o formato canônico (measures) em vez de achatar pra
                        // "notes" com perda de dados. Ver Fase 7 em
                        // .claude/plans/harmonic-mixing-breeze.md.
                        const sheetDataFromStorage = localStorage.getItem('vexflow_sheet_data');
                        if (sheetDataFromStorage) {
                            try {
                                const parsedData = JSON.parse(sheetDataFromStorage);
                                console.log('📊 Dados capturados do localStorage:', parsedData);

                                const { normalizeSheetData } = await import(window.__sheetRenderURL || '/static/js/sheet_render.js');
                                window.currentSheetData = normalizeSheetData(parsedData);
                                console.log('💾 Dados salvos globalmente:', window.currentSheetData);

                                const noteCount = window.currentSheetData.measures.reduce((n, m) => n + m.length, 0);
                                if (noteCount > 0) {
                                    const textareas = document.querySelectorAll('textarea[name="texts[]"]');
                                    const textarea = textareas[textareas.length - 1]; // Pega o último textarea
                                    if (textarea && !textarea.value.includes('[🎼 PARTITURA_INTEGRADA]')) {
                                        textarea.value += '\n[🎼 PARTITURA_INTEGRADA]\n';
                                        console.log('📝 Marcador adicionado ao texto');
                                    }
                                }

                            } catch (error) {
                                console.error('❌ Erro ao processar dados da partitura:', error);
                            }
                        }
                        
                        // Atualiza partitura
                        const newSvgData = localStorage.getItem('vexflow_sheet_svg');
                        const newSheetData = localStorage.getItem('vexflow_sheet_data');
                        
                        console.log('🔄 Atualizando partitura após edição...');
                        console.log('Novo SVG:', newSvgData ? 'Presente' : 'Ausente');
                        console.log('Novos dados:', newSheetData ? 'Presente' : 'Ausente');
                        
                        if (newSheetData && window.currentSheetData) {
                            // Atualiza com os dados convertidos (formato original)
                            window.editorBlocks[index].svgData = newSvgData;
                            window.editorBlocks[index].sheetData = JSON.stringify(window.currentSheetData);
                            window.editorBlocks[index].originalData = window.currentSheetData; // Objeto já parseado
                            
                            console.log('📝 Bloco atualizado:', window.editorBlocks[index]);
                            renderBlocks();
                            console.log('✅ Partitura atualizada com sucesso!');
                        } else {
                            console.log('❌ Nenhum dado novo encontrado');
                        }
                    }
                }, 1000);

                vexWindow.focus();
                }
            }

            // Funções de seleção múltipla
            function toggleSelectionMode() {
                selectionMode = !selectionMode;
                selectedBlocks.clear();
                
                const selectBtn = document.getElementById('selectModeBtn');
                const deleteBtn = document.getElementById('deleteSelectedBtn');
                
                if (selectionMode) {
                    selectBtn.innerHTML = '<i class="fas fa-xmark"></i> Cancelar seleção';
                    selectBtn.classList.add('active');
                    deleteBtn.style.display = 'inline-flex';
                } else {
                    selectBtn.innerHTML = '<i class="fas fa-square-check"></i> Selecionar';
                    selectBtn.classList.remove('active');
                    deleteBtn.style.display = 'none';
                }
                
                renderBlocks(true);
            }
            
            function toggleBlockSelection(index) {
                if (selectedBlocks.has(index)) {
                    selectedBlocks.delete(index);
                } else {
                    selectedBlocks.add(index);
                }
                renderBlocks(true);
            }
            
            function deleteSelectedBlocks() {
                if (selectedBlocks.size === 0) {
                    alert('⚠️ Nenhum bloco selecionado!');
                    return;
                }
                
                if (confirm(`🗑️ Tem certeza que deseja excluir ${selectedBlocks.size} bloco(s) selecionado(s)?`)) {
                    // Salva a posição do scroll antes de re-renderizar
                    const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
                    
                    // Ordena índices em ordem decrescente para não afetar os índices durante remoção
                    const sortedIndexes = Array.from(selectedBlocks).sort((a, b) => b - a);
                    
                    sortedIndexes.forEach(index => {
                        blocks.splice(index, 1);
                    });
                    
                    selectedBlocks.clear();
                    
                    if (blocks.length === 0) {
                        blocks.push({ type: 'text', content: '', id: Date.now() });
                    }
                    
                    renderBlocks(true); // skipFocus=true para manter posição do scroll
                    
                    // Restaura a posição do scroll após re-renderizar
                    requestAnimationFrame(() => {
                        window.scrollTo(0, scrollTop);
                    });
                    
                    console.log(`✅ ${sortedIndexes.length} bloco(s) excluído(s)!`);
                }
            }
            
            // Deleta bloco
            // Seções como grupos: cada uma vai do seu título até antes do
            // próximo título. Blocos antes do primeiro título formam um
            // grupo sem título (fica onde está, mas conta pra subir/descer).
            function sectionGroups() {
                const groups = [];
                blocks.forEach((b, i) => {
                    if (b.type === 'section' || groups.length === 0) groups.push({ start: i, end: i + 1 });
                    else groups[groups.length - 1].end = i + 1;
                });
                return groups;
            }

            // Re-renderiza e leva a seção pra vista, com um destaque rápido
            function showSectionAt(start) {
                renderBlocks(true);
                const el = document.querySelector(`#blockEditor [data-block-index="${start}"]`);
                if (!el) return;
                el.scrollIntoView({ block: 'center', behavior: 'smooth' });
                el.classList.add('section-flash');
                setTimeout(() => el.classList.remove('section-flash'), 900);
                const input = el.querySelector('input[type="text"]');
                if (input) input.focus({ preventScroll: true });
            }

            function moveSection(index, dir) {
                const groups = sectionGroups();
                const pos = groups.findIndex(g => g.start === index);
                const other = pos + dir;
                if (pos < 0 || other < 0 || other >= groups.length) return;
                const [a, b] = dir < 0 ? [groups[other], groups[pos]] : [groups[pos], groups[other]];
                const first = blocks.slice(a.start, a.end);
                const second = blocks.slice(b.start, b.end);
                blocks.splice(a.start, b.end - a.start, ...second, ...first);
                updateHiddenField();
                updateTomDisplay();
                showSectionAt(dir < 0 ? a.start : a.start + second.length);
            }

            // Cópia logo abaixo da original (ex.: repetir o refrão); depois
            // é só subir/descer a cópia até o lugar certo
            function duplicateSection(index) {
                const group = sectionGroups().find(g => g.start === index);
                if (!group) return;
                const now = Date.now();
                const copy = blocks.slice(group.start, group.end)
                    .map((b, i) => ({ ...JSON.parse(JSON.stringify(b)), id: now + i }));
                blocks.splice(group.end, 0, ...copy);
                updateHiddenField();
                updateTomDisplay();
                showSectionAt(group.end);
            }

            function deleteBlock(index) {
                const block = blocks[index];
                const blockType = block.type === 'section' ? 'seção' : 
                                 block.type === 'sheet' ? 'partitura' : 'texto';
                
                if (confirm(`🗑️ Tem certeza que deseja excluir este bloco de ${blockType}?`)) {
                    // Salva a posição do scroll antes de re-renderizar
                    const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
                    
                    blocks.splice(index, 1);
                    if (blocks.length === 0) {
                        blocks.push({ type: 'text', content: '', id: Date.now() });
                    }
                    renderBlocks(true); // skipFocus=true para manter posição do scroll
                    
                    // Restaura a posição do scroll após re-renderizar
                    requestAnimationFrame(() => {
                        window.scrollTo(0, scrollTop);
                    });
                    
                    console.log(`✅ Bloco de ${blockType} excluído!`);
                }
            }
            
            // Atualiza campo oculto para envio
            function updateHiddenField() {
                let content = '';
                blocks.forEach(block => {
                    if (block.type === 'section') {
                        content += `[${block.title || 'SEÇÃO'}]\n\n`;
                    } else if (block.type === 'text') {
                        // Usa diretamente o conteúdo para preservar espaços
                        content += block.content || '';
                        content += '\n\n';
                    } else if (block.type === 'sheet') {
                        content += '[🎼 PARTITURA_INTEGRADA]\n\n';
                    }
                });
                hiddenTextarea.value = content;
            }
            
            
            // ===== FUNCIONALIDADE CIFRA CLUB =====

            // O Cifra Club duplica cada linha de acorde+letra quando o texto é
            // copiado da página deles: uma vez normal, e de novo prefixada com
            // um fragmento solto de atributo HTML (ex: '">') seguido de uma
            // versão simplificada do acorde e a MESMA linha de letra repetida
            // — mesmo achado de new_song.js. Não é nada que o nosso código
            // gera (o paste sempre chega como texto puro) — é a própria
            // página do Cifra Club que injeta isso no clipboard. Remove essas
            // linhas fantasma e colapsa as duplicatas que sobram.
            // Linhas repetidas só são colapsadas quando há linha fantasma: letra
            // colada de outro lugar tem repetição de propósito ("A terra alegre
            // está" 2x) e não pode perder linha.
            function limparColagemCifraClub(texto) {
                const linhas = texto.split('\n');
                if (!linhas.some(linha => linha.trim().startsWith('">'))) return texto;
                const semFantasmas = linhas.filter(linha => !linha.trim().startsWith('">'));
                const semDuplicatas = [];
                for (const linha of semFantasmas) {
                    const anterior = semDuplicatas[semDuplicatas.length - 1];
                    if (linha.trim() !== '' && linha === anterior) continue;
                    semDuplicatas.push(linha);
                }
                return semDuplicatas.join('\n');
            }

            // trim() sozinho corta o espaço de indentação do primeiro acorde de
            // uma seção — é o primeiro caractere do bloco, cai no que trim()
            // considera "espaço à esquerda pra remover" (bug real: "primeira
            // linha de cada verso vem com o acorde forçado no começo,
            // ignorando o espaço"). Remove só linhas em branco no início/fim,
            // preservando o espaçamento de posicionamento da primeira linha
            // real de conteúdo.
            function apararPreservandoIndentacao(texto) {
                return texto.replace(/^(?:[ \t]*\n)+/, '').replace(/\s+$/, '');
            }

            // Tira [Intro], [Refrão]… sem mexer nas colunas: o marcador vira
            // espaços do mesmo tamanho. No Cifra Club ele às vezes fica NA
            // MESMA linha dos acordes ("[Intro] F9  Am7  G" com a linha de
            // baixo alinhada por baixo) — apagar puxava os acordes pra
            // esquerda e desalinhava. Depois tira o recuo que sobrou igual em
            // todas as linhas (ex.: os 8 espaços do "[Intro] ").
            function tirarMarcadoresPreservandoColunas(texto) {
                const semMarcador = apararPreservandoIndentacao(
                    texto.replace(/\[[^\]\n]*\][ \t]*/g, (m) => ' '.repeat(m.length)));
                const linhas = semMarcador.split('\n');
                const recuos = linhas.filter(l => l.trim()).map(l => l.match(/^ */)[0].length);
                const comum = recuos.length ? Math.min(...recuos) : 0;
                return comum ? linhas.map(l => l.slice(Math.min(comum, l.match(/^ */)[0].length))).join('\n') : semMarcador;
            }

            // Detecta links do Cifra Club
            function detectCifraClubLink(text) {
                const cifraClubRegex = /https?:\/\/(www\.)?cifraclub\.com\.br\/[^\/\s]+\/[^\/\s]+\/?/g;
                return text.match(cifraClubRegex);
            }
            
            // Extrai informações do link
            function extractSongInfo(url) {
                try {
                    console.log('🔍 Analisando URL:', url);
                    const parts = url.split('/');
                    console.log('📊 Partes da URL:', parts);
                    
                    // URL: https://www.cifraclub.com.br/harpa-crista/porque-ele-vive/
                    // Índices: [0]https: [1]'' [2]www.cifraclub.com.br [3]harpa-crista [4]porque-ele-vive [5]''
                    const artist = parts[3]?.replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                    const song = parts[4]?.replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                    
                    console.log('🎤 Artista extraído:', artist);
                    console.log('🎵 Música extraída:', song);
                    
                    return { artist, song, url };
                } catch (e) {
                    console.error('❌ Erro ao extrair informações:', e);
                    return null;
                }
            }
            
            // Extrai letra da música do Cifra Club
            async function extractLyricsFromCifraClub(url) {
                try {
                    console.log('🎵 Extraindo letra do Cifra Club...');
                    const response = await fetch(`/cifra?url=${encodeURIComponent(url)}`);
                    
                    if (!response.ok) {
                        throw new Error(`Erro HTTP: ${response.status}`);
                    }
                    
                    const lyrics = await response.text();
                    console.log('✅ Letra extraída com sucesso!');
                    return lyrics;
                } catch (error) {
                    console.error('❌ Erro ao extrair letra:', error);
                    return null;
                }
            }
            
            // Divide letra em blocos automáticos
            function divideLyricsIntoBlocks(lyrics) {
                console.log('🔄 Dividindo letra em blocos...');
                
                // A resposta de /cifra e /cifra_com_video sempre começa com
                // "título\n\ncompositor\n\n" (blueprints/cifras.py) — pula os
                // dois primeiros parágrafos. Antes procurava a primeira linha
                // que começasse com A–G, e compositor como "Gloria Gaither"
                // virava uma seção "VERSO 1".
                const semCabecalho = lyrics.split(/\n\s*\n/).slice(2).join('\n\n');
                
                // Junta marcador [Nome] com o conteúdo seguinte quando tem
                // linha em branco entre os dois (padrão comum do Cifra Club:
                // "[Primeira Parte]\n\n G  G2...") — sem isto, o split por
                // linha em branco logo abaixo separava o marcador do próprio
                // conteúdo, virando uma seção fantasma vazia (só o título) e
                // a seção seguinte com o conteúdo sem título nenhum.
                const cleanLyrics = semCabecalho
                    .replace(/(\[[^\]]+\])\n\s*\n/g, '$1\n');

                // Divide por parágrafos (linhas vazias)
                const paragraphs = cleanLyrics.split(/\n\s*\n/).filter(p => p.trim());

                const blocks = [];
                let verseCount = 1;
                let lastFromMarker = false;
                
                paragraphs.forEach((paragraph, index) => {
                    let sectionName = 'VERSO ' + verseCount;
                    
                    // Usa o marcador do próprio Cifra Club quando o parágrafo
                    // começa com um ("[Tab - Solo Intro]", "[Primeira Parte]").
                    // Parágrafo sem marcador logo depois de uma seção marcada é
                    // a continuação dela (2ª estrofe do refrão etc.): entra como
                    // mais um bloco de texto, sem abrir seção nova.
                    const marker = paragraph.trim().match(/^\[([^\]]+)\]/);
                    if (!marker && lastFromMarker) {
                        blocks.push({
                            type: 'text',
                            content: apararPreservandoIndentacao(paragraph),
                            id: Date.now() + index * 2 + 1
                        });
                        return;
                    }
                    lastFromMarker = !!marker;
                    const text = paragraph.toLowerCase();
                    if (marker) {
                        sectionName = marker[1].trim().toUpperCase();
                    } else if (text.includes('refrão') || text.includes('coro')) {
                        sectionName = 'REFRÃO';
                    } else if (text.includes('intro')) {
                        sectionName = 'INTRO';
                    } else if (text.includes('ponte')) {
                        sectionName = 'PONTE';
                    } else if (text.includes('final')) {
                        sectionName = 'FINAL';
                    } else {
                        verseCount++;
                    }
                    
                    // Remove marcadores [Refrão], [Verso], etc.
                    const cleanText = tirarMarcadoresPreservandoColunas(paragraph);
                    
                    blocks.push({
                        type: 'section',
                        title: sectionName,
                        id: Date.now() + index * 2
                    });
                    
                    blocks.push({
                        type: 'text',
                        content: cleanText,
                        id: Date.now() + index * 2 + 1
                    });
                });
                
                return blocks;
            }
            // Processa link do Cifra Club
            async function processCifraClubLink(url) {
                const info = extractSongInfo(url);
                if (!info) return false;
                
                // Atualiza campos do formulário
                console.log('📝 Preenchendo campos:');
                console.log('  - Título:', info.song);
                console.log('  - Autor:', info.artist);
                
                const titleField = document.getElementById('title');
                const authorField = document.getElementById('author');
                
                if (titleField) {
                    titleField.value = info.song || '';
                    console.log('✅ Título preenchido:', titleField.value);
                } else {
                    console.error('❌ Campo título não encontrado!');
                }
                
                if (authorField) {
                    authorField.value = info.artist || '';
                    console.log('✅ Autor preenchido:', authorField.value);
                } else {
                    console.error('❌ Campo autor não encontrado!');
                }
                
                // Tenta extrair cifra COM vídeo usando a nova rota
                console.log('🔄 Extraindo cifra e vídeo...');
                let lyrics = null;
                let videoUrl = null;
                
                try {
                    const response = await fetch(`/cifra_com_video?url=${encodeURIComponent(url)}`);
                    if (response.ok) {
                        const data = await response.json();
                        lyrics = data.cifra;
                        videoUrl = data.video_url;

                        // Título e artista como estão na página do Cifra Club
                        // (com acento); os do endereço ficam só de reserva
                        if (titleField && data.titulo && data.titulo !== 'Título não encontrado') {
                            titleField.value = data.titulo;
                        }
                        if (authorField && data.artista) {
                            authorField.value = data.artista;
                        }
                        
                        console.log('✅ Cifra extraída com sucesso!');
                        if (videoUrl) {
                            console.log('🎬 Vídeo encontrado:', videoUrl);
                            
                            // Atualiza campo oculto do vídeo
                            const videoField = document.getElementById('video_url');
                            if (videoField) {
                                videoField.value = videoUrl;
                            }
                            
                            // Carrega vídeo no player flutuante
                            if (window.ytPlayer) {
                                window.ytPlayer.loadVideoFromUrl(videoUrl);
                            }
                        } else {
                            console.log('⚠️ Nenhum vídeo encontrado na página');
                        }
                    } else {
                        // Fallback para rota antiga
                        lyrics = await extractLyricsFromCifraClub(url);
                    }
                } catch (error) {
                    console.error('❌ Erro ao extrair cifra com vídeo:', error);
                    // Fallback para rota antiga
                    lyrics = await extractLyricsFromCifraClub(url);
                }
                
                // Limpa blocos existentes
                blocks = [];
                
                // Adiciona bloco de referência
                blocks.push({
                    type: 'section',
                    title: '🔗 REFERÊNCIA',
                    id: Date.now()
                });
                
                blocks.push({
                    type: 'text',
                    content: `Link original: ${url}\nArtista: ${info.artist}\nMúsica: ${info.song}`,
                    id: Date.now() + 1
                });
                
                if (lyrics) {
                    // Divide letra em blocos automáticos
                    const lyricsBlocks = divideLyricsIntoBlocks(lyrics);
                    blocks.push(...lyricsBlocks);
                    console.log('✅ Letra dividida em blocos automáticos!');
                } else {
                    // Se não conseguiu extrair, cria estrutura básica
                    console.log('⚠️ Não foi possível extrair a letra. Criando estrutura básica...');
                    const sections = ['INTRO', 'VERSO 1', 'REFRÃO', 'VERSO 2', 'REFRÃO', 'PONTE', 'REFRÃO FINAL'];
                    
                    sections.forEach((section, index) => {
                        blocks.push({
                            type: 'section',
                            title: section,
                            id: Date.now() + index + 2
                        });
                        
                        blocks.push({
                            type: 'text',
                            content: `[Cole aqui a ${section.toLowerCase()}]`,
                            id: Date.now() + index + 10
                        });
                    });
                }
                
                // Atualiza a referência global para o formulário poder acessar
                window.editorBlocks = blocks;
                
                renderBlocks();
                
                // Notifica o usuário
                const message = lyrics 
                    ? `🎵 Link processado com sucesso!\n\nArtista: ${info.artist}\nMúsica: ${info.song}\n\n✅ Letra extraída e dividida automaticamente em blocos!\n🎼 Seções: Intro, Versos, Refrão, Ponte, etc.`
                    : `🎵 Link processado!\n\nArtista: ${info.artist}\nMúsica: ${info.song}\n\n⚠️ Não foi possível extrair a letra automaticamente.\nEstrutura básica criada para preenchimento manual.`;
                
                alert(message);
                
                console.log('✅ Link do Cifra Club processado:', info);
                return true;
            }
            
            // Colagem: um ponto só pro título, as caixas de texto e qualquer
            // outro campo — antes eram três listeners e a mesma colagem era
            // tratada duas vezes (pergunta e aviso em dobro). Espera o texto
            // colado entrar no campo.
            document.addEventListener('paste', function(e) {
                const el = e.target;
                if (el.tagName !== 'TEXTAREA' && el.tagName !== 'INPUT') return;
                setTimeout(() => tratarColagem(el), 500);
            });

            async function tratarColagem(el) {
                const text = limparColagemCifraClub(el.value);
                if (text !== el.value) {
                    el.value = text;
                    el.dispatchEvent(new Event('input'));
                }

                const links = detectCifraClubLink(text);
                if (links && links.length > 0) {
                    if (confirm(`🎵 Link do Cifra Club detectado!\n\n${links[0]}\n\nDeseja processar automaticamente?`)) {
                        await processCifraClubLink(links[0]);
                        if (el.isConnected) {
                            el.value = '';
                            el.dispatchEvent(new Event('input'));
                        }
                    }
                    return;
                }

                // Letra: só nas caixas de texto do editor. Com linha em branco
                // entre as estrofes separa direto; sem, pergunta antes.
                const holder = el.classList.contains('text-block') && el.closest('[data-block-index]');
                if (!holder || !detectLyrics(text)) return;
                const perguntou = !hasBlankLines(text);
                if (perguntou && !confirm(`🎵 Letra de música detectada!\n\nDeseja separar automaticamente em seções?\n\n✅ SIM: Organizar em versos, refrões, etc.\n❌ NÃO: Manter como texto único`)) return;
                const ok = await processLyrics(text, Number(holder.dataset.blockIndex));
                if (!ok && perguntou) {
                    alert('⚠️ Não foi possível separar automaticamente.\nTente separar manualmente as seções com linhas em branco.');
                }
            }
            
            // Função para processamento manual de links
            window.processCifraClubManual = async function() {
                const url = prompt(`🎵 Cole o link do Cifra Club:\n\nExemplo:\nhttps://www.cifraclub.com.br/legiao-urbana/tempo-perdido/`);
                
                if (url && url.trim()) {
                    const links = detectCifraClubLink(url.trim());
                    
                    if (links && links.length > 0) {
                        await processCifraClubLink(links[0]);
                    } else {
                        alert('❌ Link inválido!\n\nCertifique-se de que é um link válido do Cifra Club.\n\nExemplo correto:\nhttps://www.cifraclub.com.br/artista/musica/');
                    }
                } else if (url !== null) {
                    alert('⚠️ Nenhum link foi fornecido.');
                }
            };
            
            // Event listeners dos botões
            document.getElementById('addSectionBtn').onclick = () => addSectionBlock();
            document.getElementById('addTextBlockBtn').onclick = () => addTextBlock();
            document.getElementById('addSheetBlockBtn').onclick = () => addSheetBlock();
            
            document.getElementById('insertSheetBtn').onclick = () => {
                const vexWindow = window.open('/sheet_editor', 'VexFlowEditor', 'width=1200,height=800,scrollbars=yes,resizable=yes');
                vexWindow.focus();
            };
            
            document.getElementById('clearAllBtn').onclick = () => {
                if (confirm('🗑️ Tem certeza que deseja limpar TODOS os blocos?\n\nEsta ação não pode ser desfeita!')) {
                    blocks = [{ type: 'text', content: '', id: Date.now() }];
                    selectedBlocks.clear();
                    renderBlocks();
                    console.log('🧹 Todos os blocos foram limpos!');
                }
            };
            
            document.getElementById('selectModeBtn').onclick = () => {
                toggleSelectionMode();
            };
            
            document.getElementById('deleteSelectedBtn').onclick = () => {
                deleteSelectedBlocks();
            };
            
            // Renderização inicial
            renderBlocks();
            
            // Inicializa o player de vídeo flutuante
            window.ytPlayer = new YouTubeFloatingPlayer({
                onVideoUrlChange: function(url) {
                    // Atualiza o campo oculto quando o usuário adicionar vídeo manualmente
                    const videoField = document.getElementById('video_url');
                    if (videoField) {
                        videoField.value = url;
                        console.log('🎬 URL do vídeo atualizada:', url);
                    }
                }
            });
            console.log('🎬 Player de vídeo inicializado');
            
            // Carrega áudio local existente se houver (prioridade sobre vídeo)
            const audioField = document.getElementById('audio_url');
            const videoField = document.getElementById('video_url');
            const existingAudioUrl = audioField?.value;
            const existingVideoUrl = videoField?.value;
            
            console.log('🔍 Campo audio_url encontrado:', !!audioField, 'valor:', existingAudioUrl);
            console.log('🔍 Campo video_url encontrado:', !!videoField, 'valor:', existingVideoUrl);
            
            if (existingAudioUrl && existingAudioUrl.trim()) {
                console.log('🎵 Carregando áudio local existente:', existingAudioUrl);
                window.ytPlayer.loadLocalAudio(existingAudioUrl);
            } else if (existingVideoUrl && existingVideoUrl.trim()) {
                console.log('🎬 Carregando vídeo existente:', existingVideoUrl);
                window.ytPlayer.loadVideoFromUrl(existingVideoUrl);
            } else {
                console.log('⚠️ Nenhum áudio ou vídeo para carregar');
            }
            
            // ===== FUNÇÃO DE TRANSPOSIÇÃO DE ACORDES =====
            // Lógica em si (chordMap/chordNames/transposeChord/
            // isChordLine/transposeLine/describeKey/detectFirstChordToken)
            // mora em static/js/chord_lines.js, compartilhada com
            // new_song.js (as duas eram cópias idênticas). Aqui só sobra o
            // que é específico desta página: percorrer os blocos,
            // re-renderizar, e manter o rótulo "Tom" sincronizado.
            //
            // UI tipo Cifra Club: em vez de escolher quantos semitons de
            // uma vez (select -5..+5) e confirmar num botão "Transpor",
            // +/- aplica meio tom por clique, o rótulo "Tom: X" mostra o
            // tom atual (detectado a partir do primeiro acorde do texto,
            // igual o site já faz), um botão "desfazer" volta ao tom
            // original e uma grade de 12 notas pula direto pro tom
            // escolhido (como o seletor de tom do Cifra Club).
            function transposeGroupKey(g) {
                return blocks[g.start].type === 'section' ? blocks[g.start] : 'inicio';
            }

            function transposeTargets() {
                if (transposeScope === 'all') return blocks.map((_, i) => i);
                const idx = [];
                sectionGroups().forEach(g => {
                    if (!transposeSelected.has(transposeGroupKey(g))) return;
                    for (let i = g.start; i < g.end; i++) idx.push(i);
                });
                return idx;
            }

            // Tom do que vai ser transposto (música inteira ou seções marcadas)
            function transposeScopeKey() {
                if (transposeScope === 'all') {
                    const t = document.getElementById('tomAtual');
                    return t && t.textContent !== '—' ? t.textContent : null;
                }
                const contents = transposeTargets().map(i => blocks[i])
                    .filter(b => b.type === 'text').map(b => b.content);
                const first = ChordLines.detectFirstChordToken(contents);
                return first ? ChordLines.describeKey(first) : null;
            }

            // Grade, rótulo e botões conforme o escopo (sem reconstruir a lista)
            function refreshTransposeControls() {
                const key = transposeScopeKey();
                const root = key ? key.replace(/m$/, '') : null;
                document.querySelectorAll('#tomGrid button[data-key]').forEach(btn => {
                    btn.classList.toggle('active', btn.dataset.key === root);
                });
                const blocked = transposeScope === 'sections' && transposeSelected.size === 0;
                document.querySelectorAll('#tomPanel .bto-transpor, #tomGrid button').forEach(b => { b.disabled = blocked; });
                const lbl = document.getElementById('tomScopeKey');
                if (lbl) {
                    lbl.textContent = transposeScope !== 'sections' ? ''
                        : blocked ? 'Marque as seções que vão mudar de tom'
                        : `Tom das seções marcadas: ${key || '—'}`;
                }
            }

            function renderTomScope() {
                document.querySelectorAll('.tom-scope-btn').forEach(b => {
                    b.setAttribute('aria-pressed', String(b.dataset.scope === transposeScope));
                });
                const box = document.getElementById('tomSections');
                if (!box) return;
                const groups = sectionGroups();
                const alive = new Set(groups.map(transposeGroupKey));
                [...transposeSelected].forEach(k => { if (!alive.has(k)) transposeSelected.delete(k); });
                box.hidden = transposeScope !== 'sections';
                if (transposeScope === 'sections') {
                    box.innerHTML = '';
                    groups.forEach(g => {
                        const key = transposeGroupKey(g);
                        const part = blocks.slice(g.start, g.end);
                        if (key === 'inicio' && !part.some(b => b.type === 'sheet' || (b.type === 'text' && (b.content || '').trim()))) return;
                        const label = document.createElement('label');
                        label.className = 'tom-section-item';
                        const cb = document.createElement('input');
                        cb.type = 'checkbox';
                        cb.checked = transposeSelected.has(key);
                        // Só atualiza os controles: reconstruir a lista aqui
                        // tiraria o checkbox clicado do DOM e o clique-fora
                        // fecharia o painel
                        cb.onchange = () => {
                            if (cb.checked) transposeSelected.add(key); else transposeSelected.delete(key);
                            refreshTransposeControls();
                        };
                        const name = document.createElement('span');
                        name.textContent = key === 'inicio' ? 'Início (sem título)' : (key.title || 'Seção sem nome');
                        label.append(cb, name);
                        if (part.some(b => b.type === 'sheet')) {
                            const icon = document.createElement('i');
                            icon.className = 'fas fa-music';
                            icon.title = 'Tem partitura — vai junto';
                            label.append(icon);
                        }
                        box.appendChild(label);
                    });
                    if (!box.children.length) {
                        box.innerHTML = '<p class="tom-empty">Crie seções para transpor só uma parte da música.</p>';
                    }
                }
                refreshTransposeControls();
            }

            window.setTransposeScope = function(scope) {
                transposeScope = scope;
                renderTomScope();
            };

            window.transposeStep = async function(semitones) {
                const targets = transposeTargets();
                if (!targets.length) return;
                const countRef = { count: 0 };
                // sheet_render.js é ES module (import/export) — este arquivo
                // é script clássico, então só dá pra acessar via import()
                // dinâmico, mesmo padrão já usado em createSheetBlock.
                const { transposeSheetData } = await import(window.__sheetRenderURL || '/static/js/sheet_render.js');

                targets.forEach(index => {
                    const block = blocks[index];
                    if (block.type === 'text' && block.content) {
                        block.content = ChordLines.transposeBlockContent(block.content, semitones, countRef);
                    } else if (block.type === 'sheet' && block.originalData) {
                        // Muta block.originalData em memória, igual o bloco de
                        // texto já faz — é exatamente esse campo que Salvar
                        // envia, então transpor aqui muda o que fica salvo.
                        block.originalData = transposeSheetData(block.originalData, semitones);
                    } else {
                        return;
                    }
                    // Semitons andados por bloco (não vai pro Salvar): o
                    // "voltar ao tom original" desfaz exatamente o que cada
                    // bloco andou, mesmo com seções transpostas à parte
                    block._semi = (block._semi || 0) + semitones;
                });

                renderBlocks(true); // já atualiza o rótulo "Tom" (updateTomDisplay no fim de renderBlocks)
            };

            // Volta cada bloco exatamente ao tom em que estava ao carregar a
            // página, aplicando o inverso do que ele andou (soma módulo 12).
            window.undoTranspose = async function() {
                const moved = blocks.filter(b => b._semi);
                if (!moved.length) return;
                const countRef = { count: 0 };
                const { transposeSheetData } = await import(window.__sheetRenderURL || '/static/js/sheet_render.js');
                moved.forEach(block => {
                    if (block.type === 'text' && block.content) {
                        block.content = ChordLines.transposeBlockContent(block.content, -block._semi, countRef);
                    } else if (block.type === 'sheet' && block.originalData) {
                        block.originalData = transposeSheetData(block.originalData, -block._semi);
                    }
                    block._semi = 0;
                });
                renderBlocks(true);
            };

            // Pula direto pro tom escolhido na grade, calculando o delta
            // de semitons entre o tom atual (da música ou das seções
            // marcadas) e a nota clicada.
            window.jumpToKey = function(targetRoot) {
                const current = transposeScopeKey();
                if (!current) return;
                const currentRoot = current.replace(/m$/, '');
                const currentIndex = ChordLines.chordMap[currentRoot];
                const targetIndex = ChordLines.chordMap[targetRoot];
                if (currentIndex === undefined || targetIndex === undefined) return;
                let delta = (targetIndex - currentIndex + 12) % 12;
                if (delta > 6) delta -= 12; // caminho mais curto, só estética
                if (delta === 0) return;
                window.transposeStep(delta);
            };

            // Mostra/esconde a grade de tons (botão com seta ao lado do Tom).
            // Abre/fecha a janelinha flutuante (like Cifra Club) com
            // desfazer/±meio-tom/grade de notas — chamada tanto pelo clique
            // no rótulo "Tom: X" quanto pelo ⌄ de fechar dentro do painel.
            window.toggleKeyGrid = function() {
                const panel = document.getElementById('tomPanel');
                if (!panel) return;
                // O estado escondido inicial vem da classe CSS (.tom-popover
                // { display:none }), não de style inline — por isso lê o
                // computado em vez de comparar panel.style.display direto.
                const isHidden = getComputedStyle(panel).display === 'none';
                panel.style.display = isHidden ? 'block' : 'none';
            };

            // Fecha a janelinha ao clicar fora dela (comportamento padrão
            // de popover) — ignora cliques dentro do próprio widget, já
            // tratados pelos onclick dos botões internos.
            document.addEventListener('click', function(e) {
                const widget = document.querySelector('.tom-widget');
                const panel = document.getElementById('tomPanel');
                if (!widget || !panel) return;
                if (getComputedStyle(panel).display === 'none') return;
                if (!widget.contains(e.target)) {
                    panel.style.display = 'none';
                }
            });

            console.log('✅ Editor de blocos integrado inicializado!');
            
            // Dispara evento de inicialização (não aguarda VexFlow)
            console.log('🔍 Verificando VexFlow:', typeof Vex !== 'undefined' ? 'Disponível' : 'Não disponível');
            window.editorReady = true;
            console.log('🚀 Disparando evento editorInitialized...');
            $(document).trigger('editorInitialized');
            console.log('✅ Evento editorInitialized disparado!');
        });

// Script para carregar dados da música existente (só roda se a música existir)
if (CONFIG.song) {
        // REGISTRA O HANDLER IMEDIATAMENTE, antes de qualquer coisa
        $(document).on('editorInitialized', function() {
                console.log('🎉 Editor inicializado! Carregando dados da música...');
                
                // Limpa os blocos iniciais (usa o array global do editor)
                window.editorBlocks.length = 0;
                
                // Carrega as seções da música
                const songData = CONFIG.song;
                console.log('📊 Dados da música:', songData);
                
                if (songData.sections && songData.sections.length > 0) {
                    songData.sections.forEach(function(section, index) {
                        console.log(`📦 Processando seção ${index}:`, section);
                        
                        // Primeiro: verifica se há um título (seção ou partitura)
                        if (section.title && section.title.trim()) {
                            // Verifica se é uma partitura
                            if (section.title.includes('🎼 PARTITURA_INTEGRADA')) {
                                // Extrai o ID da partitura
                                const sheetIdMatch = section.title.match(/_(\d+)$/);
                                const sheetId = sheetIdMatch ? parseInt(sheetIdMatch[1]) : Date.now();
                                
                                // Busca os dados da partitura correspondente
                                if (songData.sheet_data) {
                                    const sheetDataArray = Array.isArray(songData.sheet_data) ? songData.sheet_data : [songData.sheet_data];
                                    const sheetData = sheetDataArray.find(s => s.id === sheetId);
                                    
                                    if (sheetData) {
                                        const newBlock = {
                                            type: 'sheet',
                                            id: sheetId,
                                            sheetData: JSON.stringify(sheetData),
                                            originalData: sheetData,
                                            svgData: null // Será renderizado depois
                                        };
                                        window.editorBlocks.push(newBlock);
                                        console.log('🎼 Bloco de partitura adicionado:', sheetId);
                                    }
                                }
                            } else {
                                // Bloco de seção (título)
                                const newBlock = {
                                    type: 'section',
                                    title: section.title,
                                    id: Date.now() + window.editorBlocks.length
                                };
                                window.editorBlocks.push(newBlock);
                                console.log('📋 Bloco de seção adicionado:', section.title);
                            }
                        }
                        
                        // Depois: adiciona o texto se houver (depois do título)
                        if (section.text && section.text.length > 0) {
                            // Junta todo o texto
                            let fullText = section.text.join('\n');
                            
                            // Limpa tags HTML que podem ter sido inseridas acidentalmente
                            fullText = fullText
                                .replace(/<div>/gi, '\n')      // Converte <div> em quebra de linha
                                .replace(/<\/div>/gi, '')      // Remove </div>
                                .replace(/<br\s*\/?>/gi, '\n') // Converte <br> em quebra de linha
                                .replace(/<[^>]+>/g, '')       // Remove qualquer outra tag HTML
                                .replace(/\n{3,}/g, '\n\n');   // Normaliza múltiplas quebras de linha
                            
                            // Verifica se há marcações de partitura no texto
                            const sheetMarkerRegex = /🎼 PARTITURA_INTEGRADA_(\d+)/g;
                            const parts = fullText.split(sheetMarkerRegex);
                            
                            // Processa as partes alternadas: texto, sheetId, texto, sheetId, ...
                            for (let i = 0; i < parts.length; i++) {
                                if (i % 2 === 0) {
                                    // Parte de texto (NÃO usar trim para preservar espaços)
                                    const textContent = parts[i];
                                    if (textContent && textContent.trim()) {
                                        const newBlock = {
                                            type: 'text',
                                            content: textContent,
                                            id: Date.now() + window.editorBlocks.length
                                        };
                                        window.editorBlocks.push(newBlock);
                                        console.log('📝 Bloco de texto adicionado:', textContent.substring(0, 50));
                                        
                                        // Debug: mostra espaços ao carregar
                                        const spaces = (textContent.match(/ /g) || []).length;
                                        console.log('🔍 Espaços carregados:', spaces, 'Preview:', JSON.stringify(textContent.substring(0, 100)));
                                    }
                                } else {
                                    // ID da partitura (capturado pelo grupo do regex)
                                    const sheetId = parseInt(parts[i]);
                                    
                                    // Busca os dados da partitura correspondente
                                    if (songData.sheet_data) {
                                        const sheetDataArray = Array.isArray(songData.sheet_data) ? songData.sheet_data : [songData.sheet_data];
                                        const sheetData = sheetDataArray.find(s => s.id === sheetId);
                                        
                                        if (sheetData) {
                                            const newBlock = {
                                                type: 'sheet',
                                                id: sheetId,
                                                sheetData: JSON.stringify(sheetData),
                                                originalData: sheetData,
                                                svgData: null // Será renderizado depois
                                            };
                                            window.editorBlocks.push(newBlock);
                                            console.log('🎼 Bloco de partitura adicionado do text:', sheetId);
                                        }
                                    }
                                }
                            }
                        }
                    });
                }
                
                // Se não há blocos, adiciona um bloco de texto vazio
                if (window.editorBlocks.length === 0) {
                    window.editorBlocks.push({ type: 'text', content: '', id: Date.now() });
                }
                
                console.log('📦 Total de blocos carregados:', window.editorBlocks.length);
                console.log('🔍 Verificando função renderBlocksFunction:', typeof window.renderBlocksFunction);
                
                // Renderiza os blocos usando a função global
                if (typeof window.renderBlocksFunction === 'function') {
                    console.log('🎨 Chamando renderBlocksFunction...');
                    window.renderBlocksFunction();
                    console.log('✅ Blocos renderizados!');
                } else {
                    console.error('❌ Função renderBlocksFunction não encontrada');
                    console.log('🔍 Tentando renderizar diretamente...');
                    // Tenta encontrar o container e renderizar manualmente
                    const container = document.getElementById('blockContainer');
                    if (container) {
                        console.log('📦 Container encontrado, limpando...');
                        container.innerHTML = '';
                        window.editorBlocks.forEach((block, index) => {
                            console.log(`🧱 Renderizando bloco ${index}:`, block.type);
                            if (block.type === 'text') {
                                const div = document.createElement('div');
                                div.className = 'text-block';
                                div.style.cssText = 'margin: 10px 0; padding: 10px; border: 1px solid #ddd; border-radius: 4px;';
                                const textarea = document.createElement('div');
                                textarea.contentEditable = true;
                                textarea.textContent = block.content;
                                textarea.style.cssText = 'min-height: 50px; padding: 8px;';
                                div.appendChild(textarea);
                                container.appendChild(div);
                            } else if (block.type === 'section') {
                                const div = document.createElement('div');
                                div.className = 'section-block';
                                div.style.cssText = 'margin: 10px 0; padding: 10px; background: #e3f2fd; border-radius: 4px;';
                                div.innerHTML = `<strong>📋 ${block.title}</strong>`;
                                container.appendChild(div);
                            } else if (block.type === 'sheet') {
                                const div = document.createElement('div');
                                div.className = 'sheet-block';
                                div.style.cssText = 'margin: 10px 0; padding: 10px; background: #fff3e0; border-radius: 4px;';
                                div.innerHTML = `<strong>🎼 Partitura (ID: ${block.id})</strong>`;
                                container.appendChild(div);
                            }
                        });
                    } else {
                        console.error('❌ Container blockContainer não encontrado!');
                    }
                }
                
                console.log('✅ Dados carregados com sucesso! Total de blocos:', window.editorBlocks.length);
            });

}
