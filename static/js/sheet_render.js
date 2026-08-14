/*
 * Módulo de renderização de partitura (VexFlow) compartilhado entre o
 * editor (/sheet_editor) e as telas que exibem uma partitura salva
 * (view_song, lyrics, display) — ver .claude/plans/harmonic-mixing-breeze.md.
 * Mesma versão do VexFlow, mesmo algoritmo de layout/compassos/feixes/
 * ligaduras/cifras em todo lugar, pra a exibição nunca mais divergir do
 * editor.
 *
 * Só desenha — não sabe nada sobre edição/seleção/undo. Isso fica no
 * editor, como uma camada fina por cima do que renderSheetMusic() retorna.
 */

let _vfPromise = null;
export function loadVexFlow() {
  if (!_vfPromise) {
    _vfPromise = import('/static/vendor/vexflow/4.2.5-esm/entry/vexflow.js');
  }
  return _vfPromise;
}

const DUR_BASE = { w: 1, h: 1 / 2, q: 1 / 4, 8: 1 / 8, 16: 1 / 16 };
const durValue = (d, dotted = false) => (DUR_BASE[d] ?? DUR_BASE.q) * (dotted ? 1.5 : 1);
const timeValues = (ts) => {
  const [b, v] = String(ts || '4/4').split('/').map(n => parseInt(n, 10));
  return { beats: b || 4, beatValue: v || 4, capacity: (b || 4) / (v || 4) };
};

// Aceita "C4" ou "C/4"
function pitchToKey(p) {
  const m = /^([A-Ga-g])(?:(?:#{1,2}|b{1,2}|n))?[/]?(\d)$/.exec(p || '');
  if (!m) return 'c/4';
  return m[1].toLowerCase() + '/' + m[2];
}

function measureVisualWidth(measure, baseW) {
  const NOTE_W = 14, MEASURE_PAD_R = 24;
  const count = measure?.length ?? 0;
  return Math.max(baseW * 0.75, baseW) + count * NOTE_W + MEASURE_PAD_R;
}

function splitIntoSystems(widths, maxWidth) {
  const systems = []; let row = [], acc = 0;
  for (let i = 0; i < widths.length; i++) {
    const w = widths[i];
    if (row.length > 0 && acc + w > maxWidth) { systems.push(row); row = [i]; acc = w; }
    else { row.push(i); acc += w; }
  }
  if (row.length) systems.push(row);
  return systems;
}

function createBeams(Beam, notes) {
  if (!notes.length || !Beam) return [];
  const beams = [];
  let currentGroup = [];
  for (let i = 0; i < notes.length; i++) {
    const duration = notes[i].getDuration();
    const canBeam = ['8', '16', '32', '64'].includes(duration.replace('r', ''));
    const isRest = duration.includes('r');
    if (canBeam && !isRest) {
      currentGroup.push(notes[i]);
    } else {
      if (currentGroup.length >= 2) {
        try { beams.push(new Beam(currentGroup)); } catch (e) { console.warn('Erro ao criar beam:', e); }
      }
      currentGroup = [];
    }
  }
  if (currentGroup.length >= 2) {
    try { beams.push(new Beam(currentGroup)); } catch (e) { console.warn('Erro ao criar beam final:', e); }
  }
  return beams;
}

/**
 * Detecta e converte formato antigo (measures/notes achatado, sem
 * agrupar por compasso — dado salvo antes da Fase 1 do plano) pro
 * formato canônico ({measures: [[nota,...], ...]}). Best-effort: dado já
 * perdido na conversão antiga (accidental/dotted/ties) não é
 * recuperável, só reagrupa o que sobreviveu usando o time_signature real
 * salvo (em vez do 4/4 fixo que os 3 renderizadores antigos assumiam —
 * melhoria esperada pra partitura antiga não-4/4, não regressão).
 *
 * Cifras (`chords`) só são realinhadas se o compasso salvo for 4/4
 * (mesma suposição que a conversão antiga já fazia, então {m,i} antigo
 * continua válido) — pra qualquer outro compasso, reagrupar mudaria as
 * posições e a cifra colaria na nota errada, então é descartada com um
 * aviso em vez de arriscar isso (nenhuma música real hoje combina
 * cifras com compasso não-4/4 em formato antigo).
 */
export function normalizeSheetData(raw) {
  const empty = { clef: 'treble', keySig: 'C', timeSig: '4/4', measures: [[]], ties: [], chords: [] };
  if (!raw) return empty;

  const clef = raw.clef || 'treble';
  const keySig = raw.keySig || raw.key_sig || 'C';
  const timeSig = raw.timeSig || raw.time_signature || '4/4';
  const chords = raw.chords || [];

  const measuresField = raw.measures ?? raw.notes;
  const isCanonical = Array.isArray(measuresField) && (measuresField.length === 0 || Array.isArray(measuresField[0]));
  if (isCanonical) {
    return { clef, keySig, timeSig, measures: measuresField.length ? measuresField : [[]], ties: raw.ties || [], chords };
  }

  const flat = measuresField || [];
  const { capacity } = timeValues(timeSig);
  const measures = [[]];

  flat.forEach((n) => {
    const pitch = n.pitch || (n.keys && n.keys[0]) || 'B4';
    const noteObj = {
      pitch,
      duration: n.duration || 'q',
      dotted: !!n.dotted,
      accidental: n.accidental || '',
      rest: !!n.rest,
    };
    let mIndex = measures.length - 1;
    const used = measures[mIndex].reduce((s, x) => s + durValue(x.duration, x.dotted), 0);
    if (measures[mIndex].length && used + durValue(noteObj.duration, noteObj.dotted) > capacity + 1e-6) {
      measures.push([]);
      mIndex = measures.length - 1;
    }
    measures[mIndex].push(noteObj);
  });

  let remappedChords = [];
  if (chords.length) {
    if (timeSig === '4/4') {
      remappedChords = chords; // {m,i} antigo bate com o reagrupamento novo (mesma regra)
    } else {
      console.warn('normalizeSheetData: cifras descartadas — dado antigo em compasso não-4/4, sem como realinhar com segurança.', timeSig);
    }
  }

  return { clef, keySig, timeSig, measures, ties: [], chords: remappedChords };
}

// Tabelas próprias (não importa de chord_lines.js) — sheet_editor.html
// usa este módulo sem carregar chord_lines.js, uma dependência dura
// quebraria esse consumidor. Também precisa lidar com acidente duplo
// (##/bb, estados reais alcançáveis no editor), que a tabela de cifra
// não cobre.
const NOTE_BASE = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
const ACC_OFFSET = { '': 0, n: 0, '#': 1, '##': 2, b: -1, bb: -2 };
// Mesma grafia (mista sustenido/bemol) que ChordLines.chordNames em
// chord_lines.js — cópia literal e independente de propósito (ver nota
// acima); se uma mudar, a outra precisa mudar junto.
const PITCH_SPELLING = ['C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B'];

function parsePitch(pitch) {
  const m = /^([A-Ga-g])(#{1,2}|b{1,2}|n)?[/]?(\d)$/.exec(pitch || '');
  if (!m) return null;
  return { letter: m[1].toUpperCase(), acc: m[2] || '', octave: parseInt(m[3], 10) };
}

// Pra pitch class "tecla preta" (1,3,6,8,10) existem duas grafias
// enarmônicas válidas — ex. classe 8 é "G#" ou "Ab", mesmo som. Sem
// contexto de armadura, cai na tabela fixa de sempre (PITCH_SPELLING);
// com armadura, prefere a grafia cuja letra já é alterada por ela (ex.:
// numa armadura de 3 sustenidos — Fá#,Dó#,Sol# — a classe 8 vira "G#",
// não "Ab", porque a letra Sol já é sustenida ali, e assim a nota nem
// precisa de acidente explícito desenhado).
const SHARP_SPELL = { 1: 'C#', 3: 'D#', 6: 'F#', 8: 'G#', 10: 'A#' };
const FLAT_SPELL = { 1: 'Db', 3: 'Eb', 6: 'Gb', 8: 'Ab', 10: 'Bb' };

function spellPitchClass(pitchClass, keyAccidentals) {
  if (!(pitchClass in SHARP_SPELL)) {
    // classe natural (0,2,4,5,7,9,11) — sempre a letra pura, sem acidente.
    return { letter: PITCH_SPELLING[pitchClass], acc: '' };
  }
  const sharpName = SHARP_SPELL[pitchClass];
  const flatName = FLAT_SPELL[pitchClass];
  let chosen;
  if (keyAccidentals?.sharps.has(sharpName[0])) chosen = sharpName;
  else if (keyAccidentals?.flats.has(flatName[0])) chosen = flatName;
  else if (keyAccidentals) chosen = keyAccidentals.sharps.size >= keyAccidentals.flats.size ? sharpName : flatName;
  else chosen = PITCH_SPELLING[pitchClass]; // sem armadura de contexto (chamada avulsa) — tabela fixa de sempre
  return { letter: chosen[0], acc: chosen.length > 1 ? chosen[1] : '' };
}

/**
 * Transpõe uma altura de nota (ex: "C#4") por `semitones`, com rollover
 * de oitava correto (B4 +1 -> C5). `pitch` e `accidental` voltam juntos
 * e em sincronia — StaveNote usa a oitava/letra embutida em `pitch` pra
 * posição na pauta, mas o desenho do sustenido/bemol/natural vem do
 * campo `accidental` separado (ver sheet_editor.html:256,291-302), então
 * os dois precisam ser atualizados como uma unidade só. `keyAccidentals`
 * (opcional, de keySignatureAccidentals) escolhe a grafia enarmônica
 * certa pra armadura de destino — sem ele, cai na tabela fixa de sempre
 * (mesmo resultado que antes, usado pelos testes unitários diretos).
 */
export function transposePitch(pitch, semitones, keyAccidentals) {
  const p = parsePitch(pitch);
  if (!p || !semitones) return { pitch, accidental: undefined };
  const abs = p.octave * 12 + NOTE_BASE[p.letter] + (ACC_OFFSET[p.acc] ?? 0) + semitones;
  const newOctave = Math.floor(abs / 12);
  const pitchClass = ((abs % 12) + 12) % 12;
  const { letter, acc } = spellPitchClass(pitchClass, keyAccidentals);
  return { pitch: `${letter}${acc}${newOctave}`, accidental: acc };
}

function transposeKeySig(keySig, semitones) {
  const m = /^([A-Ga-g])(#|b)?(m)?$/.exec(keySig || '');
  if (!m || !semitones) return keySig || 'C';
  const idx = NOTE_BASE[m[1].toUpperCase()] + (ACC_OFFSET[m[2] || ''] ?? 0);
  const newIdx = ((idx + semitones) % 12 + 12) % 12;
  return PITCH_SPELLING[newIdx] + (m[3] || '');
}

// Ordem padrão em que sustenidos/bemóis entram numa armadura de clave
// (círculo de quintas). Quantidade de cada uma das 12 armaduras maiores
// que transposeKeySig pode produzir — mesmo índice de PITCH_SPELLING
// (nunca Db/Gb/Cb, mesma limitação já aceita pro nome da armadura).
const SHARP_ORDER = ['F', 'C', 'G', 'D', 'A', 'E', 'B'];
const FLAT_ORDER = ['B', 'E', 'A', 'D', 'G', 'C', 'F'];
const MAJOR_KEY_SHARPS = [0, 7, 2, 0, 4, 0, 6, 1, 0, 3, 0, 5]; // C C# D Eb E F F# G Ab A Bb B
const MAJOR_KEY_FLATS = [0, 0, 0, 3, 0, 1, 0, 0, 4, 0, 2, 0];

// Letras já alteradas pela armadura de clave — pra tom menor usa a
// armadura do relativo maior (tônica + 3 semitons), que é a mesma
// (mesma quantidade de sustenido/bemol de qualquer tom menor real).
function keySignatureAccidentals(keySig) {
  const m = /^([A-Ga-g])(#|b)?(m)?$/.exec(keySig || 'C');
  if (!m) return { sharps: new Set(), flats: new Set() };
  let idx = NOTE_BASE[m[1].toUpperCase()] + (ACC_OFFSET[m[2] || ''] ?? 0);
  idx = ((idx % 12) + 12) % 12;
  if (m[3]) idx = (idx + 3) % 12;
  return {
    sharps: new Set(SHARP_ORDER.slice(0, MAJOR_KEY_SHARPS[idx])),
    flats: new Set(FLAT_ORDER.slice(0, MAJOR_KEY_FLATS[idx])),
  };
}

/**
 * Decide se uma nota precisa de marca explícita de acidente desenhada,
 * ou se a armadura de clave já cobre sozinha. Ex.: em Dm (1 bemol, Bb),
 * uma nota "Bb" não precisa de bemol explícito — a armadura já altera
 * todo Si pra bemol. Sem isso, toda nota transposta ganharia acidente
 * redundante mesmo quando a armadura já resolve, poluindo a partitura.
 */
function accidentalForKey(letter, rawAccidental, keyAccidentals) {
  const implied = keyAccidentals.sharps.has(letter) ? '#' : keyAccidentals.flats.has(letter) ? 'b' : '';
  if (rawAccidental === implied) return '';
  if (rawAccidental === '') return 'n'; // armadura alteraria a nota, mas ela deve soar natural
  return rawAccidental;
}

/**
 * Resolve a altura REAL de uma nota salva, considerando a armadura de
 * clave original: `sheet_editor.html` só embute o acidente na própria
 * string de `pitch` quando ele é EXPLÍCITO (mantém `pitch` e
 * `accidental` em sincronia ao salvar) — uma nota que soa alterada só
 * pela armadura (ex.: "F4"/accidental:"" no tom de Sol maior, que já
 * altera todo Fá pra sustenido) fica salva com a letra pura, sem o
 * sustenido embutido. Ler isso litéralmente (como se fosse F natural)
 * daria o semitom de partida errado pra transposição — bug real
 * encontrado testando com dado de produção (música 342, nota "F4" em
 * tom de Sol virou "Eb" ao transpor um tom abaixo, quando deveria virar
 * "E" natural).
 */
function resolvePitchWithKey(pitch, storedAccidental, keyAccidentals) {
  if (storedAccidental) return pitch; // acidente explícito, já embutido na string
  const p = parsePitch(pitch);
  if (!p) return pitch;
  const implied = keyAccidentals.sharps.has(p.letter) ? '#' : keyAccidentals.flats.has(p.letter) ? 'b' : '';
  return implied ? `${p.letter}${implied}${p.octave}` : pitch;
}

/**
 * Transpõe uma partitura inteira (notas + cifra sobreposta + armadura de
 * clave) por `semitones`, sempre recalculando a partir do dado ORIGINAL
 * (nunca transpõe em cima de um resultado já transposto) — mesma
 * estratégia "recalcula do zero" que view_song.html já usa pra letra,
 * evitando erro acumulado em cliques repetidos de +/-.
 */
export function transposeSheetData(canonicalData, semitones) {
  const data = normalizeSheetData(canonicalData);
  // normalizeSheetData() só devolve os campos de desenho — não carrega
  // `id` (não precisa dele pra desenhar), mas quem chama esta função
  // precisa pra achar o elemento "sheet-display-<id>" certo no DOM.
  const id = canonicalData?.id;
  if (!semitones) return { ...data, id };
  const newKeySig = transposeKeySig(data.keySig, semitones);
  const newKeyAccidentals = keySignatureAccidentals(newKeySig);
  const origKeyAccidentals = keySignatureAccidentals(data.keySig);
  return {
    ...data,
    id,
    keySig: newKeySig,
    measures: data.measures.map(measure => measure.map(note => {
      if (note.rest) return note;
      const effectivePitch = resolvePitchWithKey(note.pitch, note.accidental, origKeyAccidentals);
      const { pitch, accidental: rawAccidental } = transposePitch(effectivePitch, semitones, newKeyAccidentals);
      const accidental = accidentalForKey(pitch[0], rawAccidental, newKeyAccidentals);
      return { ...note, pitch, accidental };
    })),
    chords: data.chords.map(c => ({
      ...c,
      // Cifra sobreposta só existe junto com chord_lines.js nas páginas
      // que já o carregam hoje — sheet_editor.html nunca chama esta
      // função, então o guard nunca precisa disparar ali.
      symbol: (typeof window !== 'undefined' && window.ChordLines?.transposeChord)
        ? window.ChordLines.transposeChord(c.symbol, semitones)
        : c.symbol,
    })),
  };
}

/**
 * Desenha a partitura em `container` (elemento DOM). Não sabe de
 * seleção/edição — devolve `vfNotesByMI` (mapa [measure][note] -> objeto
 * StaveNote do VexFlow) pra quem chamou construir interatividade por
 * cima (o editor faz isso; as telas de exibição não precisam).
 */
export async function renderSheetMusic(container, rawOrCanonicalData, options = {}) {
  const VF = await loadVexFlow();
  const { Factory, StaveNote, Voice, Formatter, Accidental, StaveTie, Dot, Beam } = VF;

  const data = normalizeSheetData(rawOrCanonicalData);
  container.innerHTML = '';

  const BASE_MEASURE_W = 220;
  const STAVE_H = 140, SYSTEM_GAP = 30, LEFT = 24, RIGHT = 24, TOP = 20;

  const { beats, beatValue } = timeValues(data.timeSig);
  const viewportW = options.maxWidth ?? (container.clientWidth || container.parentElement?.clientWidth || 900);
  const maxSystemW = viewportW - (LEFT + RIGHT);

  const proportion = (beats / beatValue) / (4 / 4);
  const baseW = BASE_MEASURE_W * Math.max(0.7, proportion);

  const widths = data.measures.map(m => measureVisualWidth(m, baseW));
  const systemsIdx = splitIntoSystems(widths, Math.max(260, maxSystemW));
  const totalH = TOP + systemsIdx.length * STAVE_H + (systemsIdx.length - 1) * SYSTEM_GAP + 20;
  const totalW = viewportW;

  if (!container.id) container.id = `sheet-render-${Math.random().toString(36).slice(2)}`;
  const vf = new Factory({ renderer: { elementId: container.id, width: totalW, height: totalH } });
  const ctx = vf.getContext();

  // Cor da notação — default preto (todo lugar com fundo claro: editor,
  // view_song, etc.). Telas com fundo escuro (ex.: /lyrics/display com o
  // fundo preto ativado) passam options.color:'#fff', senão a partitura
  // fica preta sobre preto, invisível. ctx.setFillStyle/setStrokeStyle
  // sozinhos NÃO bastam — Stave/StaveNote têm cor própria embutida que
  // ignora o estilo ambiente do contexto (achado testando: a pauta
  // continuava cinza #999999 mesmo com o contexto setado pra branco) —
  // precisa de .setStyle({fillStyle, strokeStyle}) em cada elemento.
  const notationColor = options.color || '#000';
  const notationStyle = { fillStyle: notationColor, strokeStyle: notationColor };
  ctx.setFillStyle(notationColor);
  ctx.setStrokeStyle(notationColor);

  const vfNotesByMI = Array(data.measures.length).fill(null).map(() => []);

  systemsIdx.forEach((row, s) => {
    const y = TOP + s * (STAVE_H + SYSTEM_GAP);
    let x = LEFT;

    row.forEach((mIndex, j) => {
      const measureNotes = data.measures[mIndex] ?? [];
      const w = widths[mIndex];

      const stave = vf.Stave({ x, y, width: w });
      stave.setStyle(notationStyle);
      if (j === 0) { stave.addClef(data.clef).addKeySignature(data.keySig).addTimeSignature(data.timeSig); }
      stave.setContext(ctx).draw();

      const tickables = measureNotes.map(m => {
        const dur = m.duration + (m.rest ? 'r' : '');
        const key = m.rest ? 'b/4' : pitchToKey(m.pitch);
        const sn = new StaveNote({ clef: data.clef, keys: [key], duration: dur, dots: m.dotted ? 1 : 0 });
        sn.setStyle(notationStyle);

        if (!m.rest && m.accidental && m.accidental !== '') {
          const type = (m.accidental === 'n') ? 'n' : m.accidental;
          try {
            if (typeof sn.addAccidental === 'function') sn.addAccidental(0, new Accidental(type));
            else if (typeof sn.addModifier === 'function') sn.addModifier(new Accidental(type), 0);
          } catch (e) { console.warn('Falha ao anexar acidente:', e); }
        }
        if (m.dotted) {
          if (typeof sn.addDotToAll === 'function') sn.addDotToAll();
          else Dot.buildAndAttach([sn], { all: true });
        }
        return sn;
      });

      vfNotesByMI[mIndex] = tickables;

      if (tickables.length) {
        const voice = new Voice({ num_beats: beats, beat_value: beatValue, resolution: 4 }).setStrict(false);
        voice.addTickables(tickables);

        const beams = createBeams(Beam, tickables);

        const formatter = new Formatter();
        formatter.joinVoices([voice]);

        if (typeof formatter.formatToStave === 'function') {
          formatter.formatToStave([voice], stave, { stavePadding: 0 });
        } else {
          const startX = (typeof stave.getNoteStartX === 'function') ? stave.getNoteStartX() : (stave.getX() + 12);
          const endX = (typeof stave.getNoteEndX === 'function') ? stave.getNoteEndX() : (stave.getX() + stave.getWidth() - 14);
          const avail = Math.max(20, endX - startX);
          formatter.format([voice], avail);
        }

        voice.draw(ctx, stave);

        beams.forEach(beam => {
          try {
            beam.setStyle(notationStyle);
            beam.setContext(ctx).draw();
          } catch (e) { console.warn('Erro ao desenhar beam:', e); }
        });
      }

      x += w;
    });
  });

  data.ties.forEach(t => {
    const first = vfNotesByMI[t.from.m]?.[t.from.i];
    const last = vfNotesByMI[t.to.m]?.[t.to.i];
    if (first && last) {
      const tie = new StaveTie({ first_note: first, last_note: last });
      tie.setStyle(notationStyle);
      tie.setContext(ctx).draw();
    }
  });

  data.chords.forEach(chord => {
    const note = vfNotesByMI[chord.m]?.[chord.i];
    if (!note) return;
    try {
      const bbox = note.getBoundingBox();
      if (bbox) {
        const systemIndex = Math.floor((bbox.y - TOP) / (STAVE_H + SYSTEM_GAP));
        const staveY = TOP + systemIndex * (STAVE_H + SYSTEM_GAP);
        ctx.save();
        ctx.font = '14px Arial, sans-serif';
        ctx.fillStyle = notationColor;
        ctx.textAlign = 'center';
        ctx.fillText(chord.symbol, bbox.x + bbox.w / 2, staveY + 2);
        ctx.restore();
      }
    } catch (e) { console.warn('Erro ao desenhar acorde:', e); }
  });

  return { vfNotesByMI, systemsIdx, svgEl: container.querySelector('svg'), data };
}
