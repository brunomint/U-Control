/*
 * Transposição de cifras em texto plano (letra+cifra intercalada nos
 * blocos de new_song.html/edit_song.html) — compartilhado entre os dois,
 * que antes tinham essa lógica duplicada byte-a-byte.
 *
 * Script clássico (não ES module) de propósito: as duas páginas chamam
 * essas funções de dentro de onclick="" inline e de closures que já
 * existem antes de qualquer import assíncrono resolver, então um
 * `import()` dinâmico (como o usado pra static/js/sheet_render.js, que
 * é uma lib pesada carregada sob demanda) traria complexidade sem
 * necessidade aqui — isso é só JS puro, pequeno, sem dependência.
 *
 * Classifica por LINHA inteira antes de transpor (mesma estratégia do
 * Quelea, org.quelea.services.utils.LineTypeChecker.checkChords): só
 * mexe numa linha se TODOS os tokens baterem com o padrão de acorde. Uma
 * linha de letra real quase sempre tem alguma palavra multissílaba/
 * acentuada que não bate, então cai inteira como letra — sem precisar de
 * lista de exceção pra palavras que colidem com forma de acorde ("Em",
 * "Deus", "Fé", "Se"...).
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
    // remove marcadores de repetição (x2, 2x) e parênteses/hífen soltos
    const cleaned = trimmed
      .replace(/[xX][0-9]+/g, '')
      .replace(/[0-9]+[xX]/g, '')
      .replace(/[()\-]/g, ' ');
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

  global.ChordTranspose = {
    chordMap: CHORD_MAP,
    chordNames: CHORD_NAMES,
    transposeChord,
    isChordLine,
    transposeLine,
    transposeBlockContent,
  };
})(window);
