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

  const vfNotesByMI = Array(data.measures.length).fill(null).map(() => []);

  systemsIdx.forEach((row, s) => {
    const y = TOP + s * (STAVE_H + SYSTEM_GAP);
    let x = LEFT;

    row.forEach((mIndex, j) => {
      const measureNotes = data.measures[mIndex] ?? [];
      const w = widths[mIndex];

      const stave = vf.Stave({ x, y, width: w });
      if (j === 0) { stave.addClef(data.clef).addKeySignature(data.keySig).addTimeSignature(data.timeSig); }
      stave.setContext(ctx).draw();

      const tickables = measureNotes.map(m => {
        const dur = m.duration + (m.rest ? 'r' : '');
        const key = m.rest ? 'b/4' : pitchToKey(m.pitch);
        const sn = new StaveNote({ clef: data.clef, keys: [key], duration: dur, dots: m.dotted ? 1 : 0 });

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
          try { beam.setContext(ctx).draw(); } catch (e) { console.warn('Erro ao desenhar beam:', e); }
        });
      }

      x += w;
    });
  });

  data.ties.forEach(t => {
    const first = vfNotesByMI[t.from.m]?.[t.from.i];
    const last = vfNotesByMI[t.to.m]?.[t.to.i];
    if (first && last) new StaveTie({ first_note: first, last_note: last }).setContext(ctx).draw();
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
        ctx.fillStyle = '#000';
        ctx.textAlign = 'center';
        ctx.fillText(chord.symbol, bbox.x + bbox.w / 2, staveY + 2);
        ctx.restore();
      }
    } catch (e) { console.warn('Erro ao desenhar acorde:', e); }
  });

  return { vfNotesByMI, systemsIdx, svgEl: container.querySelector('svg'), data };
}
