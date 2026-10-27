// Seções de uma música como são apresentadas — a mesma conta pra página da
// música (lyrics_2.js) e pro monitor aberto por endereço (display.js), e
// em Python em songs_store.secoes_apresentadas (reconstrução no servidor).
//
// A lista salva (song.sections) não é a apresentada: um texto com
// marcadores [NOME] vira uma seção por marcador, seção vazia some, e
// partitura vira 'sheet'/'mixed'. O sectionIndex que vai pras telas é a
// posição NESTA lista; `raw` em cada uma diz de qual seção salva veio
// (é o que a Ordem no culto, Song.order, guarda). Antes o monitor por
// endereço e o servidor usavam a lista salva e mostravam a seção errada
// em música com [NOME] no texto.
(function () {
    function processSections(rawSections) {
        const processedSections = [];

        rawSections.forEach((section, raw) => {   // raw: posição na música salva (Ordem no culto)
            // Verifica se é uma seção de partitura integrada no título
            if (section.title && section.title.includes('🎼 PARTITURA_INTEGRADA_')) {
                // Extrai o ID da partitura do título
                const sheetIdMatch = section.title.match(/PARTITURA_INTEGRADA_(\d+)/);
                if (sheetIdMatch) {
                    const sheetId = parseInt(sheetIdMatch[1]);
                    processedSections.push({ raw,
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
                processedSections.push({ raw,
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
                        processedSections.push({ raw,
                            title: sectionTitle,
                            text: [sectionContent],
                            type: 'text'
                        });
                    }
                });
            } else {
                // Sem marcadores, usa a seção como está
                if (fullText.trim()) {
                    processedSections.push({ raw,
                        title: section.title || '',
                        text: [fullText],
                        type: 'text'
                    });
                }
            }
        });

        return processedSections;
    }

    // Ordem no culto -> índices desta lista, com repetição. Sem ordem (ou
    // ordem que não bate com nada), de cima pra baixo.
    function passos(sections, order) {
        const p = Array.isArray(order) ? order.flatMap(r => sections.map((s, i) => (s.raw === r ? i : -1)).filter(i => i >= 0)) : [];
        return p.length ? p : sections.map((_, i) => i);
    }

    window.SongSections = { process: processSections, passos };
})();
