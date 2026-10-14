/*
 * Lógica de linha de cifra (texto plano, letra+cifra intercalada) —
 * compartilhada por toda tela que precisa TRANSPOR (new_song/edit_song),
 * ELIMINAR (tela pública) ou COLORIR (retorno de palco, página de
 * referência /view) uma cifra. Cada uma dessas 5 telas tinha sua própria
 * reimplementação da mesma detecção, com robustez diferente entre elas.
 *
 * Script clássico (não ES module) de propósito: as páginas chamam essas
 * funções de dentro de onclick="" inline e de closures que já existem
 * antes de qualquer import assíncrono resolver — diferente do
 * static/js/sheet_render.js (lib pesada, carregada sob demanda via
 * import() dinâmico), isso é só JS puro, pequeno, sem dependência.
 *
 * Classifica por LINHA inteira (mesma estratégia do Quelea,
 * org.quelea.services.utils.LineTypeChecker.checkChords): só mexe numa
 * linha se TODOS os tokens baterem com o padrão de acorde. Uma linha de
 * letra real quase sempre tem alguma palavra multissílaba/acentuada que
 * não bate, então cai inteira como letra — sem precisar de lista de
 * exceção pra palavras que colidem com forma de acorde ("Em", "Deus",
 * "Fé", "Se"...).
 */
(function (global) {
  const CHORD_MAP = {
    'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3, 'E': 4, 'F': 5,
    'F#': 6, 'Gb': 6, 'G': 7, 'G#': 8, 'Ab': 8, 'A': 9, 'A#': 10, 'Bb': 10, 'B': 11
  };

  // Grafia por nota (mistura sustenido/bemol) em vez de sempre sustenido
  // — mesma convenção usada pelo Quelea (ChordTransposer.TRANSPOSE_STEPS),
  // o resultado padrão de notação musical mais comum quando não se sabe
  // a tonalidade de destino (ex: transpor 3 semitons acima de C vira
  // "Eb", não "D#").
  const CHORD_NAMES = ['C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B'];

  // Grafia pelo tom de destino: tons de sustenido escrevem tudo com # (em
  // Mi, o baixo de E é G#: "E/G#", não "E/Ab"); tons de bemol, tudo com b
  // (em Láb, "Ab" e "Db", não "G#"/"C#"). Dó maior / Lá menor (sem
  // acidentes) ficam com a mistura de CHORD_NAMES. O tom é o 1º acorde do
  // bloco já transposto (ou o próprio acorde, quando vem sozinho).
  const SHARP_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
  const FLAT_NAMES = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B'];
  const SHARP_KEYS = { major: [7, 2, 9, 4, 11, 6], minor: [4, 11, 6, 1, 8] };
  const FLAT_KEYS = { major: [5, 10, 3, 8, 1], minor: [2, 7, 0, 5, 10, 3] };

  // "m", "m7", "mi7", "-7", "ø7" (jazz)... mas não "maj7"
  function isMinorSuffix(rest) {
    return /^(?:m(?!aj)|-|ø)/.test(rest);
  }

  function namesForKey(pitch, minor) {
    const kind = minor ? 'minor' : 'major';
    if (SHARP_KEYS[kind].includes(pitch)) return SHARP_NAMES;
    if (FLAT_KEYS[kind].includes(pitch)) return FLAT_NAMES;
    return CHORD_NAMES;
  }

  // Um acorde (token). Aceita a notação brasileira e a de jazz:
  // qualidade (m, min, mi, maj, dim, aug, sus, add, Δ, ø, °, o7, +, -),
  // extensões encadeadas (7M, maj7, 7+, 5+, b9, #11, alt, 4sus, 6/9),
  // extensões entre parênteses (C7M(9), D7(4/9), F#7(5-), Cm(maj7)) e
  // baixo invertido (/G#). Letras só entram em palavras-chave fechadas,
  // então palavra de letra de música não passa por acorde.
  const CHORD_TOKEN_REGEX = /^[A-G][#b]?(?:maj|Maj|min|mi|m|M|dim|aug|sus|add|Δ|ø|°|º|o(?=7)|\+|-)?(?:[0-9]+|M|maj[0-9]*|Maj[0-9]*|Δ[0-9]*|sus[0-9]*|add[0-9]+|alt|[#b+\-][0-9]+|[+\-°øº]|\((?:add|maj|M)?[#b+\-]?[0-9]+[+\-]?(?:[\/,](?:add|maj|M)?[#b+\-]?[0-9]+[+\-]?)*\)|\/[0-9]+)*(?:\/[A-G][#b]?)?$/;

  // Tokens de acorde de uma linha, já limpos — ou null se algum token não
  // for acorde. Tira marcadores de repetição (x2, 2x), barras de compasso
  // e hífens; parênteses só saem quando estão SOLTOS em volta do acorde
  // ("( C9  D/F# )", "(C9"), nunca quando fazem parte dele — "C7M(9)" é um
  // acorde só (antes os parênteses viravam espaço, o "9" sobrava sozinho
  // e a linha inteira caía como letra: sem cor, sem transpor e aparecendo
  // no telão público — achado na música 412).
  function chordToken(raw) {
    let tok = raw.replace(/^\(+/, '');
    while (tok) {
      if (CHORD_TOKEN_REGEX.test(tok)) return tok;
      if (!tok.endsWith(')')) return null;
      tok = tok.slice(0, -1);
    }
    return null;
  }

  function chordTokens(line) {
    const cleaned = line.trim()
      .replace(/[xX][0-9]+/g, '')
      .replace(/[0-9]+[xX]/g, '')
      .replace(/\|/g, ' ');
    const tokens = [];
    for (const raw of cleaned.split(/\s+/)) {
      // vazio, parêntese ou hífen/travessão soltos ("G - D")
      if (!raw || /^[()\-–—]+$/.test(raw)) continue;
      const tok = chordToken(raw);
      if (tok) { tokens.push(tok); continue; }
      // acordes ligados por hífen ("G-D-Em"); o hífen do acorde (C-7,
      // F#7(5-)) já passou acima como parte do próprio acorde
      const parts = raw.split(/[\-–—]/).filter(Boolean).map(chordToken);
      if (raw.includes('-') && parts.length && parts.every(Boolean)) { tokens.push(...parts); continue; }
      return null;
    }
    return tokens;
  }

  // Transpõe um acorde individual (incluindo baixo após a barra, ex: /G#).
  // names: grafia do tom (namesForKey); sem ela, o próprio acorde decide.
  function transposeChord(chord, semitones, names) {
    const chordRegex = /^([A-G][#b]?)(.*)$/;
    const match = chord.match(chordRegex);
    if (!match) return chord; // não é um acorde válido, retorna original

    const [, baseNote, modifiers] = match;
    const baseIndex = CHORD_MAP[baseNote];
    if (baseIndex === undefined) return chord;

    const newIndex = ((baseIndex + semitones) % 12 + 12) % 12;
    if (!names) names = namesForKey(newIndex, isMinorSuffix(modifiers));
    const transposedBase = names[newIndex];

    const bassRegex = /(\/)([A-G][#b]?)/g;
    const transposedModifiers = modifiers.replace(bassRegex, (m, slash, bassNote) => {
      const bassIndex = CHORD_MAP[bassNote];
      if (bassIndex === undefined) return m;
      return slash + names[((bassIndex + semitones) % 12 + 12) % 12];
    });

    return transposedBase + transposedModifiers;
  }

  // Grafia de um bloco transposto, pelo 1º acorde dele
  function namesForBlock(content, semitones) {
    const match = /^([A-G][#b]?)(.*)$/.exec(detectFirstChordToken([content]) || '');
    if (!match || CHORD_MAP[match[1]] === undefined) return CHORD_NAMES;
    const pitch = ((CHORD_MAP[match[1]] + semitones) % 12 + 12) % 12;
    return namesForKey(pitch, isMinorSuffix(match[2]));
  }

  // Suporta os sufixos //chords e //lyrics no fim da linha pra forçar a
  // classificação manualmente nos raros casos em que o palpite
  // automático erraria.
  function isChordLine(line) {
    const trimmed = line.trim();
    if (!trimmed) return false;
    if (/\/\/chords$/i.test(trimmed)) return true;
    if (/\/\/lyrics$/i.test(trimmed)) return false;
    // Barras de compasso (| ou ||, ex: "| G | G7M | Em D |") também saem
    // na limpeza (chordTokens) — sem isso, intro/solo em notação de
    // compasso era classificada como letra (bug real, música com intro em
    // "| G | G7M | C7M | Em D4 D ||").
    const tokens = chordTokens(trimmed);
    return !!tokens && tokens.length > 0;
  }

  // Transpõe só os tokens de uma linha já confirmada como cifra,
  // preservando os espaços originais entre eles (mantém o alinhamento
  // da cifra em cima da sílaba certa da letra).
  function transposeLine(line, semitones, countRef, names) {
    const leading = line.match(/^\s*/)[0];
    const rest = line.slice(leading.length);
    const parts = rest.split(/(\s+)/);
    const transposedParts = parts.map(part => {
      if (part === '' || /^\s+$/.test(part)) return part;
      const transposed = transposeChord(part, semitones, names);
      if (transposed !== part && countRef) countRef.count++;
      return transposed;
    });
    return leading + transposedParts.join('');
  }

  // Transpõe o conteúdo de um bloco de texto inteiro (múltiplas linhas),
  // linha por linha — só linhas de cifra (isChordLine) são tocadas.
  function transposeBlockContent(content, semitones, countRef) {
    const names = namesForBlock(content, semitones);
    const lines = content.split('\n');
    const newLines = lines.map(line => {
      if (!isChordLine(line)) return line;
      return transposeLine(line, semitones, countRef, names);
    });
    return newLines.join('\n');
  }

  // Remove linhas de cifra inteiras de um texto multi-linha (usado pela
  // tela pública, que não deve mostrar cifra nenhuma). Mantém as linhas
  // de letra exatamente como estão — não tenta limpar cifra dentro de
  // uma linha mista, porque na prática cifra e letra sempre vêm em
  // linhas separadas (confirmado nos dados reais do projeto), então essa
  // cirurgia por palavra nunca é necessária e só adiciona risco.
  function stripChordLines(text) {
    if (!text) return '';
    return text.split('\n')
      .filter(line => !isChordLine(line))
      .join('\n');
  }

  // Envolve cada token (separado por espaço) de uma linha em
  // <span class="chord">...</span> — inclui barra de compasso "|" e
  // parênteses que estejam colados/soltos no meio dos tokens, já que
  // viram "parts" como qualquer outro token não-espaço. Só chame depois
  // de confirmar isChordLine(line) — não filtra nada sozinha, e não
  // escapa HTML (espera texto já pronto pra ir direto num innerHTML,
  // mesmo padrão que view_song.html já usava).
  function highlightChordTokensHtml(line) {
    const leading = line.match(/^\s*/)[0];
    const rest = line.slice(leading.length);
    const parts = rest.split(/(\s+)/);
    const html = parts.map(part => {
      if (part === '' || /^\s+$/.test(part)) return part;
      return `<span class="chord">${part}</span>`;
    }).join('');
    return leading + html;
  }

  // Acorde solto entre barras de compasso no meio de uma linha de letra
  // (ex.: "algumas palavras | A | mais palavras")
  const BAR_CHORD_REGEX = /\|\s*([A-G][#b]?(?:m|min|maj|M|sus|dim|aug|add|°|º)?(?:7M|7|9|11|13|6)?[0-9]*\+?(?:\/[A-G][#b]?)?)\s*\|/g;

  // Colore UMA linha: comentário "//" (nota de palco), linha de cifra ou
  // acorde entre barras. Regra única usada pela página /view e pelo
  // editor de música (static/js/chord_highlight.js). Recebe a linha já
  // em HTML (texto escapado) e devolve HTML; os espaços da linha são
  // mantidos como estão — no editor a cor fica atrás da textarea e
  // precisa casar caractere por caractere.
  function highlightLineHtml(lineHtml) {
    const plain = lineHtml.replace(/<[^>]*>/g, '');
    if (plain.trim().startsWith('//')) {
      return `<span class="comment-line">${lineHtml}</span>`;
    }
    if (isChordLine(plain)) return highlightChordTokensHtml(lineHtml);
    return lineHtml.replace(BAR_CHORD_REGEX, (m) =>
      m.replace(/[^\s|]+|\|/g, (t) => `<span class="chord">${t}</span>`));
  }

  // Nome de tom pra exibir (ex: "G", "Am") a partir de um token de
  // acorde — reduz sufixos de extensão (7, sus4, 9...) à indicação
  // maior/menor só, que é o que "tom" quer dizer (Cmaj7 e C7 são os
  // dois "tom de C", só a nota base + maior/menor importam aqui).
  function describeKey(chordToken) {
    const match = /^([A-G][#b]?)(.*)$/.exec(chordToken || '');
    if (!match) return null;
    const [, root, rest] = match;
    return root + (isMinorSuffix(rest) ? 'm' : '');
  }

  // Acha o primeiro acorde de uma lista de blocos de texto (na ordem em
  // que aparecem) — usado como palpite do "tom" da música, mesma
  // convenção simples que ferramentas de cifra costumam usar (não é
  // infalível: uma música pode não começar no acorde de tônica, mas
  // funciona sem precisar de nenhum dado extra cadastrado).
  function detectFirstChordToken(blockContents) {
    for (const content of blockContents) {
      if (!content) continue;
      const lines = content.split('\n');
      for (const line of lines) {
        if (isChordLine(line)) {
          // Mesma limpeza de isChordLine — sem isso, uma intro em
          // notação "| G | G7M | ..." devolvia o "|" cru como "primeiro
          // acorde" e o "Tom: X" ficava em "—" (bug real, música 296)
          const tokens = chordTokens(line) || [];
          if (tokens.length) return tokens[0];
        }
      }
    }
    return null;
  }

  global.ChordLines = {
    chordMap: CHORD_MAP,
    chordNames: CHORD_NAMES,
    transposeChord,
    isChordLine,
    transposeLine,
    transposeBlockContent,
    stripChordLines,
    highlightChordTokensHtml,
    highlightLineHtml,
    describeKey,
    detectFirstChordToken,
  };
})(window);
