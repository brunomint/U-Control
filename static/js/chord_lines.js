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

  const CHORD_TOKEN_REGEX = /^[A-G][#b]?(?:m|min|maj|M|sus|dim|aug|add)?[0-9]*(?:M)?(?:º)?(?:\([0-9]+\))?(?:\/[A-G][#b]?)?$/;

  // Transpõe um acorde individual (incluindo baixo após a barra, ex: /G#)
  function transposeChord(chord, semitones) {
    const chordRegex = /^([A-G][#b]?)(.*)$/;
    const match = chord.match(chordRegex);
    if (!match) return chord; // não é um acorde válido, retorna original

    const [, baseNote, modifiers] = match;
    const baseIndex = CHORD_MAP[baseNote];
    if (baseIndex === undefined) return chord;

    let newIndex = (baseIndex + semitones) % 12;
    if (newIndex < 0) newIndex += 12;
    const transposedBase = CHORD_NAMES[newIndex];

    const bassRegex = /(\/)([A-G][#b]?)/g;
    const transposedModifiers = modifiers.replace(bassRegex, (m, slash, bassNote) => {
      const bassIndex = CHORD_MAP[bassNote];
      if (bassIndex === undefined) return m;
      let newBassIndex = (bassIndex + semitones) % 12;
      if (newBassIndex < 0) newBassIndex += 12;
      return slash + CHORD_NAMES[newBassIndex];
    });

    return transposedBase + transposedModifiers;
  }

  // Suporta os sufixos //chords e //lyrics no fim da linha pra forçar a
  // classificação manualmente nos raros casos em que o palpite
  // automático erraria.
  function isChordLine(line) {
    const trimmed = line.trim();
    if (!trimmed) return false;
    if (/\/\/chords$/i.test(trimmed)) return true;
    if (/\/\/lyrics$/i.test(trimmed)) return false;
    // remove marcadores de repetição (x2, 2x), parênteses/hífen soltos e
    // barras de compasso (| ou ||, ex: "| G | G7M | Em D |") — sem isso,
    // "|" vira um token que não bate com CHORD_TOKEN_REGEX (não começa
    // com A-G), e a linha inteira de intro/solo em notação de compasso
    // era classificada como letra em vez de cifra: não era removida na
    // tela pública nem transposta (bug real, achado com música real que
    // tinha intro em "| G | G7M | C7M | Em D4 D ||").
    const cleaned = trimmed
      .replace(/[xX][0-9]+/g, '')
      .replace(/[0-9]+[xX]/g, '')
      .replace(/[()\-|]/g, ' ');
    const tokens = cleaned.split(/\s+/).filter(Boolean);
    if (tokens.length === 0) return false;
    return tokens.every(tok => CHORD_TOKEN_REGEX.test(tok));
  }

  // Transpõe só os tokens de uma linha já confirmada como cifra,
  // preservando os espaços originais entre eles (mantém o alinhamento
  // da cifra em cima da sílaba certa da letra).
  function transposeLine(line, semitones, countRef) {
    const leading = line.match(/^\s*/)[0];
    const rest = line.slice(leading.length);
    const parts = rest.split(/(\s+)/);
    const transposedParts = parts.map(part => {
      if (part === '' || /^\s+$/.test(part)) return part;
      const transposed = transposeChord(part, semitones);
      if (transposed !== part && countRef) countRef.count++;
      return transposed;
    });
    return leading + transposedParts.join('');
  }

  // Transpõe o conteúdo de um bloco de texto inteiro (múltiplas linhas),
  // linha por linha — só linhas de cifra (isChordLine) são tocadas.
  function transposeBlockContent(content, semitones, countRef) {
    const lines = content.split('\n');
    const newLines = lines.map(line => {
      if (!isChordLine(line)) return line;
      return transposeLine(line, semitones, countRef);
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
    const isMinor = /^m(?!aj)/.test(rest); // "m", "m7"... mas não "maj7"
    return root + (isMinor ? 'm' : '');
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
          // Mesma limpeza de isChordLine (repetição, parênteses/hífen/barra
          // de compasso) — sem isso, uma intro em notação "| G | G7M | ..."
          // devolvia o "|" cru como "primeiro acorde", e o widget "Tom: X"
          // ficava travado em "—" pra sempre (bug real, achado com a
          // música 296 — intro começa exatamente nesse formato).
          const cleaned = line.trim()
            .replace(/[xX][0-9]+/g, '')
            .replace(/[0-9]+[xX]/g, '')
            .replace(/[()\-|]/g, ' ');
          const tokens = cleaned.split(/\s+/).filter(Boolean);
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
