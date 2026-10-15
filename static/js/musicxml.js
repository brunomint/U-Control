// MusicXML ⇄ partitura do U-Control (formato canônico do sheet_render.js:
// { clef, keySig, timeSig, measures:[[nota]], ties, chords }).
//
// Exportar: o arquivo abre no MuseScore e em outros editores de partitura.
// Importar: .musicxml / .xml (texto) e .mxl (compactado). O editor do
// U-Control tem uma pauta e uma voz, então do arquivo entra a 1ª parte, a
// 1ª pauta e a 1ª voz; o resto vira aviso pra quem importou.
//
// Nota no U-Control: pitch como escrito ("F4", "F#4") e note.accidental o
// sinal desenhado (inclui 'n'); sem sinal, a armadura vale por cima.

import { normalizeSheetData } from './sheet_render.js';

const KEY_COUNT = { C: 0, G: 1, D: 2, A: 3, E: 4, B: 5, 'F#': 6, 'C#': 7, F: -1, Bb: -2, Eb: -3, Ab: -4, Db: -5, Gb: -6, Cb: -7 };
const FIFTHS_KEY = Object.fromEntries(Object.entries(KEY_COUNT).map(([k, v]) => [v, k]));
const SHARP_ORDER = ['F', 'C', 'G', 'D', 'A', 'E', 'B'];
const FLAT_ORDER = ['B', 'E', 'A', 'D', 'G', 'C', 'F'];
const ACC_ALTER = { '': 0, n: 0, '#': 1, b: -1, '##': 2, bb: -2 };
const ALTER_ACC = { 0: '', 1: '#', '-1': 'b', 2: '##', '-2': 'bb' };
const ACC_XML = { '#': 'sharp', b: 'flat', n: 'natural', '##': 'double-sharp', bb: 'flat-flat' };
const XML_ACC = { sharp: '#', flat: 'b', natural: 'n', 'double-sharp': '##', 'sharp-sharp': '##', 'flat-flat': 'bb' };
// divisions = 24 por semínima: semicolcheia pontuada (9) e tercina de
// semicolcheia (4) cabem inteiras
const DIVISIONS = 24;
const DUR_DIV = { w: 96, h: 48, q: 24, 8: 12, 16: 6 };
const DUR_TYPE = { w: 'whole', h: 'half', q: 'quarter', 8: 'eighth', 16: '16th' };
const TYPE_DUR = { whole: 'w', half: 'h', quarter: 'q', eighth: '8', '16th': '16' };

function keyAcc(letter, keySig) {
  const n = KEY_COUNT[keySig] || 0;
  if (n > 0 && SHARP_ORDER.slice(0, n).includes(letter)) return '#';
  if (n < 0 && FLAT_ORDER.slice(0, -n).includes(letter)) return 'b';
  return '';
}
function parsePitch(p) {
  p = p ? p[0].toUpperCase() + p.slice(1) : '';           // dado antigo: "c/4"
  const m = /^([A-G])(##|bb|#|b)?\/?(\d)$/.exec(p);
  return m ? { letter: m[1], acc: m[2] || '', oct: +m[3] } : null;
}
const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

// ---------- Cifras (texto) ⇄ <harmony> ----------
// O MuseScore (e outros) leem a cifra pelo TIPO (<kind>) e pelos graus
// (<degree>), não pelo texto — então "D4" precisa ir como suspensa, "F7M"
// como sétima maior etc. Entende a cifra brasileira: 4, 7(4), 7M, 7+, º,
// m7(b5), 7(9), 7(b9), 6(9), (9)...
const ALTER_OF = { b: -1, '-': -1, '#': 1, '+': 1, '': 0 };

function parseSuffix(suffix) {
  let s = (suffix || '').replace(/\s+/g, '');
  const ext = [];                                    // [{n, alter}]
  const addExt = (txt) => txt.split(/[,/]/).filter(Boolean).forEach((x) => {
    const m = /^(add)?([b#+-]?)(\d+)([+-]?)$/.exec(x);
    if (m) ext.push({ n: +m[3], alter: ALTER_OF[m[2] || m[4] || ''] });
  });
  let seventhParen = '';
  s = s.replace(/\(([^)]*)\)/g, (_, inner) => {
    // "m(7M)": a sétima maior dentro do parêntese
    inner = inner.replace(/(^|[,/])(7M|maj7|M7|7\+)(?=$|[,/])/, (__, sep) => { seventhParen = 'M'; return sep; });
    addExt(inner); return '';
  });
  let quality = 'major';
  let mm;
  if ((mm = /^(m(?!aj)|mi(?!n)|min|-)/.exec(s))) { quality = 'minor'; s = s.slice(mm[0].length); }
  else if ((mm = /^(dim|°|º)/.exec(s))) { quality = 'dim'; s = s.slice(mm[0].length); }
  else if ((mm = /^(aug|\+)(?!\d)/.exec(s))) { quality = 'aug'; s = s.slice(mm[0].length); }
  else if ((mm = /^ø/.exec(s))) { quality = 'half'; s = s.slice(1); }
  let seventh = '';
  if ((mm = /^(maj7|Maj7|M7|7M|Δ7|Δ|7\+)/.exec(s))) { seventh = 'M'; s = s.slice(mm[0].length); }
  else if ((mm = /^(maj|M)(?=\d|$)/.exec(s))) { seventh = 'M'; s = s.slice(mm[0].length); }
  else if (/^7/.test(s)) { seventh = '7'; s = s.slice(1); }
  if (!seventh && seventhParen) seventh = seventhParen;
  let sus = '';
  if ((mm = /^sus(4|2)?/.exec(s))) { sus = mm[1] || '4'; s = s.slice(mm[0].length); }
  // sobra: números soltos ("9", "4", "6", "add9", "/4", "b5", "13")
  s.split(/[/,]/).filter(Boolean).forEach((x) => addExt(x));
  if (quality === 'half') { quality = 'minor'; seventh = seventh || '7'; ext.push({ n: 5, alter: -1 }); }
  const take = (n) => { const k = ext.findIndex((e) => e.n === n && e.alter === 0); if (k < 0) return false; ext.splice(k, 1); return true; };
  if (!sus && take(4)) sus = '4';
  if (!sus && take(2)) sus = '2';
  const six = take(6);
  return { quality, seventh, sus, six, ext };
}

function kindAndDegrees(suffix) {
  const { quality, seventh, sus, six, ext } = parseSuffix(suffix);
  const deg = [];
  const pull = (n) => { const k = ext.findIndex((e) => e.n === n && e.alter === 0); if (k < 0) return false; ext.splice(k, 1); return true; };
  let kind;
  const fifthAlt = ext.find((e) => e.n === 5 && e.alter !== 0);
  if (quality === 'minor' && seventh === '7' && fifthAlt && fifthAlt.alter === -1) { ext.splice(ext.indexOf(fifthAlt), 1); kind = 'half-diminished'; }
  else if (sus === '4') { kind = 'suspended-fourth'; if (seventh) deg.push([7, seventh === 'M' ? 0 : -1, 'add']); }
  else if (sus === '2') { kind = 'suspended-second'; if (seventh) deg.push([7, seventh === 'M' ? 0 : -1, 'add']); }
  else if (quality === 'dim') kind = seventh ? 'diminished-seventh' : 'diminished';
  else if (quality === 'aug') kind = seventh ? 'augmented-seventh' : 'augmented';
  else if (quality === 'minor') {
    if (seventh === 'M') kind = 'major-minor';
    else if (seventh === '7') kind = pull(13) ? 'minor-13th' : pull(11) ? 'minor-11th' : pull(9) ? 'minor-ninth' : 'minor-seventh';
    else kind = six ? 'minor-sixth' : 'minor';
  } else {
    if (seventh === 'M') kind = pull(13) ? 'major-13th' : pull(11) ? 'major-11th' : pull(9) ? 'major-ninth' : 'major-seventh';
    else if (seventh === '7') kind = pull(13) ? 'dominant-13th' : pull(11) ? 'dominant-11th' : pull(9) ? 'dominant-ninth' : 'dominant';
    else if (six) kind = 'major-sixth';
    else if (ext.length === 1 && ext[0].n === 5 && ext[0].alter === 0) { ext.length = 0; kind = 'power'; }
    else kind = 'major';
  }
  if (six && !/sixth/.test(kind)) deg.push([6, 0, 'add']);
  ext.forEach((e) => deg.push([e.n, e.alter, e.n === 5 ? 'alter' : 'add']));
  return { kind, deg };
}

function harmonyXML(symbol) {
  const m = /^([A-G])(#|b)?(.*?)(?:\/([A-G])(#|b)?)?$/.exec((symbol || '').trim());
  if (!m) return '';
  const [, root, rAcc, suffix, bass, bAcc] = m;
  const { kind, deg } = kindAndDegrees(suffix);
  let x = `<harmony><root><root-step>${root}</root-step>${rAcc ? `<root-alter>${ACC_ALTER[rAcc]}</root-alter>` : ''}</root>`;
  x += `<kind text="${esc(suffix)}">${kind}</kind>`;
  if (bass) x += `<bass><bass-step>${bass}</bass-step>${bAcc ? `<bass-alter>${ACC_ALTER[bAcc]}</bass-alter>` : ''}</bass>`;
  deg.forEach(([n, alt, type]) => { x += `<degree><degree-value>${n}</degree-value><degree-alter>${alt}</degree-alter><degree-type>${type}</degree-type></degree>`; });
  return x + '</harmony>';
}

// Importar: tipo + graus -> cifra no padrão brasileiro (Cifra Club)
const KIND_TEXT = {
  major: '', minor: 'm', augmented: 'aug', diminished: 'º', dominant: '7', 'major-seventh': '7M',
  'minor-seventh': 'm7', 'diminished-seventh': 'º', 'augmented-seventh': '7(#5)', 'half-diminished': 'm7(b5)',
  'major-minor': 'm(7M)', 'major-sixth': '6', 'minor-sixth': 'm6', 'dominant-ninth': '7(9)', 'major-ninth': '7M(9)',
  'minor-ninth': 'm7(9)', 'dominant-11th': '7(11)', 'major-11th': '7M(11)', 'minor-11th': 'm7(11)',
  'dominant-13th': '7(13)', 'major-13th': '7M(13)', 'minor-13th': 'm7(13)', 'suspended-second': '2',
  'suspended-fourth': '4', power: '5', none: '',
};
function harmonySuffix(h) {
  const kindEl = h.querySelector('kind');
  const kind = kindEl?.textContent.trim() || 'major';
  let base = KIND_TEXT[kind] ?? '';
  const degs = [...h.querySelectorAll('degree')].map((d) => ({
    n: +d.querySelector('degree-value')?.textContent,
    alt: +(d.querySelector('degree-alter')?.textContent || 0),
    type: d.querySelector('degree-type')?.textContent?.trim(),
  }));
  const ext = [];
  degs.forEach((d) => {
    if (d.n === 7 && d.type === 'add' && kind.startsWith('suspended')) { base = (d.alt === 0 ? '7M' : '7') + `(${base})`; return; }
    const sig = d.alt < 0 ? 'b' : d.alt > 0 ? '#' : '';
    if (d.type === 'subtract') return;
    ext.push(sig + d.n);
  });
  if (!degs.length) {
    // sem graus: o texto do arquivo, se houver, é a grafia do autor
    const text = kindEl?.getAttribute('text');
    if (text && kindEl.getAttribute('use-symbols') !== 'yes') return text;
  }
  if (!ext.length) return base;
  // junta as extensões ao parêntese que já existe (7(9) + b13 -> 7(9/b13))
  return /\)$/.test(base) ? base.replace(/\)$/, '/' + ext.join('/') + ')') : `${base}(${ext.join('/')})`;
}

// ---------- Exportar ----------
export function toMusicXML(raw, { title = 'Partitura' } = {}) {
  const data = normalizeSheetData(raw);
  const [beats, beatType] = (data.timeSig || '4/4').split('/');
  const tieStart = new Set(data.ties.map((t) => `${t.from.m}:${t.from.i}`));
  const tieStop = new Set(data.ties.map((t) => `${t.to.m}:${t.to.i}`));
  const chordAt = new Map(data.chords.map((c) => [`${c.m}:${c.i}`, c.symbol]));
  const clef = data.clef === 'bass' ? '<sign>F</sign><line>4</line>' : '<sign>G</sign><line>2</line>';

  // Repetições por compasso
  const marks = data.marks || {};
  const mk = (i) => marks[String(i)] || {};
  const casas = Object.values(marks).map((o) => parseInt(o && o.volta, 10)).filter((x) => x > 0);
  const ultimaCasa = casas.length ? Math.max(...casas) : 0;
  const JUMP_WORDS = {
    FINE: ['Fine', 'fine="yes"'], DC: ['D.C.', 'dacapo="yes"'], DC_AL_FINE: ['D.C. al Fine', 'dacapo="yes"'],
    DC_AL_CODA: ['D.C. al Coda', 'dacapo="yes"'], DS: ['D.S.', 'dalsegno="segno"'], DS_AL_FINE: ['D.S. al Fine', 'dalsegno="segno"'],
    DS_AL_CODA: ['D.S. al Coda', 'dalsegno="segno"'], TO_CODA: ['To Coda', 'tocoda="coda"'],
  };
  const direction = (j) => {
    if (j === 'SEGNO_LEFT' || j === 'SEGNO_RIGHT') return '<direction placement="above"><direction-type><segno/></direction-type><sound segno="segno"/></direction>';
    if (j === 'CODA_LEFT' || j === 'CODA_RIGHT') return '<direction placement="above"><direction-type><coda/></direction-type><sound coda="coda"/></direction>';
    const w = JUMP_WORDS[j];
    return w ? `<direction placement="above"><direction-type><words>${esc(w[0])}</words></direction-type><sound ${w[1]}/></direction>` : '';
  };

  let body = '';
  data.measures.forEach((notes, m) => {
    body += `<measure number="${m + 1}">`;
    if (m === 0) {
      body += `<attributes><divisions>${DIVISIONS}</divisions><key><fifths>${KEY_COUNT[data.keySig] || 0}</fifths></key>`
        + `<time><beats>${beats}</beats><beat-type>${beatType}</beat-type></time><clef>${clef}</clef></attributes>`;
    }
    const o = mk(m);
    const casaIni = o.volta && mk(m - 1).volta !== o.volta;
    const casaFim = o.volta && mk(m + 1).volta !== o.volta;
    if (o.start || casaIni) {
      body += '<barline location="left">' + (o.start ? '<bar-style>heavy-light</bar-style>' : '')
        + (casaIni ? `<ending number="${esc(o.volta)}" type="start">${esc(o.volta)}.</ending>` : '')
        + (o.start ? '<repeat direction="forward"/>' : '') + '</barline>';
    }
    // Segno/Coda no começo do compasso; os outros (Fine, D.C., To Coda...) no fim
    const noFim = o.jump && !/^(SEGNO|CODA)/.test(o.jump);
    if (o.jump && !noFim) body += direction(o.jump);
    notes.forEach((n, i) => {
      const ref = `${m}:${i}`;
      if (chordAt.has(ref)) body += harmonyXML(chordAt.get(ref));
      const tup = n.tuplet ? { n: n.tuplet.n || 3, of: n.tuplet.of || 2 } : null;
      const dur = Math.round(DUR_DIV[n.duration] * (n.dotted ? 1.5 : 1) * (tup ? tup.of / tup.n : 1));
      const ant = notes[i - 1], prox = notes[i + 1];
      const tupStart = tup && !(ant && ant.tuplet && ant.tuplet.id === n.tuplet.id);
      const tupStop = tup && !(prox && prox.tuplet && prox.tuplet.id === n.tuplet.id);
      // Acorde: a nota principal + as de cima (<chord/>), mesma duração
      const heads = n.rest ? [null] : [{ pitch: n.pitch, accidental: n.accidental }, ...(n.extra || [])];
      heads.forEach((h, k) => {
        body += '<note>';
        if (k > 0) body += '<chord/>';
        if (!h) {
          body += '<rest/>';
        } else {
          const p = parsePitch(h.pitch) || { letter: 'C', acc: '', oct: 4 };
          const acc = h.accidental || p.acc;
          const alter = acc === '' ? ACC_ALTER[keyAcc(p.letter, data.keySig)] : ACC_ALTER[acc];
          body += `<pitch><step>${p.letter}</step>${alter ? `<alter>${alter}</alter>` : ''}<octave>${p.oct}</octave></pitch>`;
        }
        body += `<duration>${dur}</duration>`;
        if (h && tieStop.has(ref)) body += '<tie type="stop"/>';
        if (h && tieStart.has(ref)) body += '<tie type="start"/>';
        body += `<voice>1</voice><type>${DUR_TYPE[n.duration] || 'quarter'}</type>${n.dotted ? '<dot/>' : ''}`;
        if (h && h.accidental && ACC_XML[h.accidental]) body += `<accidental>${ACC_XML[h.accidental]}</accidental>`;
        if (tup) body += `<time-modification><actual-notes>${tup.n}</actual-notes><normal-notes>${tup.of}</normal-notes></time-modification>`;
        const nt = (h && tieStop.has(ref) ? '<tied type="stop"/>' : '') + (h && tieStart.has(ref) ? '<tied type="start"/>' : '')
          + (k === 0 && tupStart ? '<tuplet type="start" bracket="yes"/>' : '') + (k === 0 && tupStop ? '<tuplet type="stop"/>' : '');
        if (nt) body += `<notations>${nt}</notations>`;
        body += '</note>';
      });
    });
    if (noFim) body += direction(o.jump);
    if (o.end || casaFim) {
      const aberta = casaFim && ultimaCasa > 1 && parseInt(o.volta, 10) === ultimaCasa && !o.end;
      body += '<barline location="right">' + (o.end ? '<bar-style>light-heavy</bar-style>' : '')
        + (casaFim ? `<ending number="${esc(o.volta)}" type="${aberta ? 'discontinue' : 'stop'}"/>` : '')
        + (o.end ? `<repeat direction="backward"${o.times > 2 ? ` times="${o.times}"` : ''}/>` : '') + '</barline>';
    }
    body += '</measure>';
  });

  return '<?xml version="1.0" encoding="UTF-8"?>\n'
    + '<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">\n'
    + `<score-partwise version="4.0"><work><work-title>${esc(title)}</work-title></work>`
    + `<identification><encoding><software>U-Control</software></encoding></identification>`
    + `<part-list><score-part id="P1"><part-name>${esc(title)}</part-name></score-part></part-list>`
    + `<part id="P1">${body}</part></score-partwise>\n`;
}

// ---------- .mxl (zip) ----------
async function inflateRaw(bytes) {
  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('deflate-raw'));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}
async function unzipEntries(buf) {
  const dv = new DataView(buf), u8 = new Uint8Array(buf);
  let eocd = -1;
  for (let i = buf.byteLength - 22; i >= Math.max(0, buf.byteLength - 66000); i--) {
    if (dv.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
  }
  if (eocd < 0) throw new Error('arquivo .mxl inválido');
  const count = dv.getUint16(eocd + 10, true);
  let p = dv.getUint32(eocd + 16, true);
  const dec = new TextDecoder();
  const entries = {};
  for (let k = 0; k < count; k++) {
    const method = dv.getUint16(p + 10, true), csize = dv.getUint32(p + 20, true);
    const nlen = dv.getUint16(p + 28, true), xlen = dv.getUint16(p + 30, true), clen = dv.getUint16(p + 32, true);
    const local = dv.getUint32(p + 42, true);
    const name = dec.decode(u8.subarray(p + 46, p + 46 + nlen));
    entries[name] = { method, csize, local };
    p += 46 + nlen + xlen + clen;
  }
  const read = async (name) => {
    const e = entries[name]; if (!e) return null;
    const start = e.local + 30 + dv.getUint16(e.local + 26, true) + dv.getUint16(e.local + 28, true);
    const raw = u8.subarray(start, start + e.csize);
    return dec.decode(e.method === 8 ? await inflateRaw(raw) : raw);
  };
  return { names: Object.keys(entries), read };
}
async function xmlTextFromFile(file) {
  const buf = await file.arrayBuffer();
  const head = new Uint8Array(buf, 0, 2);
  if (head[0] === 0x50 && head[1] === 0x4b) {                      // "PK": .mxl
    const zip = await unzipEntries(buf);
    let root = null;
    const container = await zip.read('META-INF/container.xml');
    if (container) {
      const doc = new DOMParser().parseFromString(container, 'application/xml');
      root = doc.querySelector('rootfile')?.getAttribute('full-path');
    }
    root = root || zip.names.find((n) => !n.startsWith('META-INF') && /\.(musicxml|xml)$/i.test(n));
    if (!root) throw new Error('não achei a partitura dentro do .mxl');
    return zip.read(root);
  }
  return new TextDecoder().decode(buf);
}

// ---------- Importar ----------
export function fromMusicXMLText(xml) {
  const doc = new DOMParser().parseFromString(xml, 'application/xml');
  if (doc.querySelector('parsererror')) throw new Error('o arquivo não é um MusicXML válido');
  if (doc.documentElement.nodeName === 'score-timewise') throw new Error('formato "timewise" não é suportado (exporte como MusicXML normal)');
  const parts = [...doc.querySelectorAll('score-partwise > part')];
  if (!parts.length) throw new Error('nenhuma parte encontrada no arquivo');
  const avisos = new Set();
  if (parts.length > 1) {
    const nome = doc.querySelector('part-list score-part part-name')?.textContent || 'a primeira';
    avisos.add(`O arquivo tem ${parts.length} partes (instrumentos); entrou só ${nome}.`);
  }

  const out = { clef: 'treble', keySig: 'C', timeSig: '4/4', measures: [], ties: [], chords: [], marks: {} };
  const setMark = (m, k, v) => { const o = out.marks[String(m)] || (out.marks[String(m)] = {}); o[k] = v; };
  let casaAberta = null;                                       // número da casa em andamento
  const JUMP_TEXT = [
    [/d\.?\s*s\.?.*al\s*fine|dal\s*segno.*fine/i, 'DS_AL_FINE'], [/d\.?\s*s\.?.*al\s*coda|dal\s*segno.*coda/i, 'DS_AL_CODA'],
    [/^\s*(d\.?\s*s\.?|dal\s*segno)\s*$/i, 'DS'], [/d\.?\s*c\.?.*al\s*fine|da\s*capo.*fine/i, 'DC_AL_FINE'],
    [/d\.?\s*c\.?.*al\s*coda|da\s*capo.*coda/i, 'DC_AL_CODA'], [/^\s*(d\.?\s*c\.?|da\s*capo)\s*$/i, 'DC'],
    [/to\s*coda|ao\s*coda/i, 'TO_CODA'], [/^\s*fine\s*$/i, 'FINE'],
  ];
  let divisions = 1, voz = null, keySet = false, timeSet = false, clefSet = false;
  let pendingChord = null;
  let tupletSeq = 0, tupletCount = 0;
  const openTies = new Map();                                  // altura -> {m,i}

  [...parts[0].querySelectorAll(':scope > measure')].forEach((meas) => {
    const m = out.measures.length;
    const notas = [];
    out.measures.push(notas);
    if (casaAberta) setMark(m, 'volta', casaAberta);
    for (const el of meas.children) {
      if (el.nodeName === 'barline') {
        const rp = el.querySelector('repeat')?.getAttribute('direction');
        if (rp === 'forward') setMark(m, 'start', true);
        if (rp === 'backward') {
          setMark(m, 'end', true);
          const t = +el.querySelector('repeat').getAttribute('times'); if (t > 2) setMark(m, 'times', t);
        }
        const en = el.querySelector('ending');
        if (en) {
          const num = (en.getAttribute('number') || '1').replace(/\s+/g, '');
          if (en.getAttribute('type') === 'start') casaAberta = num;
          if (casaAberta) setMark(m, 'volta', casaAberta);
          if (en.getAttribute('type') !== 'start') casaAberta = null;
        }
        continue;
      }
      if (el.nodeName === 'direction') {
        let j = null;
        if (el.querySelector('direction-type segno')) j = 'SEGNO_LEFT';
        else if (el.querySelector('direction-type coda')) j = 'CODA_LEFT';
        else {
          const w = [...el.querySelectorAll('direction-type words')].map((x) => x.textContent).join(' ');
          if (w) { const hit = JUMP_TEXT.find(([re]) => re.test(w)); if (hit) j = hit[1]; }
          if (!j) {
            const so = el.querySelector('sound');
            if (so?.getAttribute('fine')) j = 'FINE';
            else if (so?.getAttribute('tocoda')) j = 'TO_CODA';
            else if (so?.getAttribute('dacapo') === 'yes') j = 'DC';
            else if (so?.getAttribute('dalsegno')) j = 'DS';
          }
        }
        if (j) setMark(m, 'jump', j);
        continue;
      }
      if (el.nodeName === 'attributes') {
        const d = el.querySelector('divisions'); if (d) divisions = +d.textContent || 1;
        const f = el.querySelector('key fifths');
        if (f) {
          const k = FIFTHS_KEY[+f.textContent];
          if (!keySet) { if (k) out.keySig = k; keySet = true; } else if (k && k !== out.keySig) avisos.add('A armadura muda no meio da música; ficou só a primeira.');
        }
        const b = el.querySelector('time beats'), t = el.querySelector('time beat-type');
        if (b && t) {
          const ts = `${b.textContent.trim()}/${t.textContent.trim()}`;
          if (!timeSet) { out.timeSig = ts; timeSet = true; } else if (ts !== out.timeSig) avisos.add('A fórmula de compasso muda no meio da música; ficou só a primeira.');
        }
        if (el.querySelectorAll('clef').length > 1 || el.querySelector('staves')) avisos.add('O arquivo tem mais de uma pauta (ex.: piano); entrou só a de cima.');
        const c = el.querySelector('clef:not([number]), clef[number="1"]');
        if (c && !clefSet) {
          const sign = c.querySelector('sign')?.textContent;
          out.clef = sign === 'F' ? 'bass' : 'treble';
          if (sign !== 'F' && sign !== 'G') avisos.add(`Clave "${sign}" não existe no editor; ficou clave de Sol.`);
          clefSet = true;
        }
      } else if (el.nodeName === 'harmony') {
        const rs = el.querySelector('root root-step')?.textContent;
        if (rs) {
          const ra = ALTER_ACC[+(el.querySelector('root root-alter')?.textContent || 0)] || '';
          const bs = el.querySelector('bass bass-step')?.textContent;
          const ba = ALTER_ACC[+(el.querySelector('bass bass-alter')?.textContent || 0)] || '';
          pendingChord = rs + ra + harmonySuffix(el) + (bs ? `/${bs}${ba}` : '');
        }
      } else if (el.nodeName === 'note') {
        if (el.querySelector('grace')) { avisos.add('Apojaturas (notas pequenas) não foram importadas.'); continue; }
        if (el.querySelector('cue')) continue;
        const staff = el.querySelector('staff')?.textContent;
        if (staff && staff !== '1') continue;
        const v = el.querySelector('voice')?.textContent || '1';
        if (voz === null) voz = v;
        if (v !== voz) { avisos.add('O arquivo tem mais de uma voz na pauta; entrou só a primeira.'); continue; }
        if (el.querySelector('chord')) {
          // nota de cima de um acorde: soma na nota anterior
          const base = notas[notas.length - 1];
          if (base && !base.rest && !el.querySelector('rest')) {
            const step = el.querySelector('pitch step')?.textContent?.trim() || 'C';
            const alter = Math.round(+(el.querySelector('pitch alter')?.textContent || 0));
            const oct = +(el.querySelector('pitch octave')?.textContent || 4);
            const acc = ALTER_ACC[alter] || '';
            const shown = XML_ACC[el.querySelector('accidental')?.textContent?.trim()] || '';
            const pitch = (!shown && acc === keyAcc(step, out.keySig)) ? `${step}${oct}` : `${step}${acc}${oct}`;
            base.extra = [...(base.extra || []), { pitch, accidental: shown }];
          }
          continue;
        }
        const tm = el.querySelector('time-modification');
        let tuplet = null;
        if (tm) {
          const an = +tm.querySelector('actual-notes')?.textContent, nn = +tm.querySelector('normal-notes')?.textContent;
          if (an === 3 && nn === 2) {
            const comeca = el.querySelector('notations tuplet[type="start"]');
            const ant = notas[notas.length - 1];
            if (comeca || !(ant && ant.tuplet && ant.tuplet.id === tupletSeq) || tupletCount >= 3) { tupletSeq++; tupletCount = 0; }
            tupletCount++;
            tuplet = { id: tupletSeq, n: 3, of: 2 };
          } else {
            avisos.add('Quiálteras que não são tercina (ex.: quintinas) entraram com a duração mais próxima e podem sobrar no compasso.');
          }
        }
        if (el.querySelector('lyric')) avisos.add('A letra embaixo das notas não foi importada.');

        let type = el.querySelector('type')?.textContent?.trim();
        let dur = TYPE_DUR[type];
        let dotted = el.querySelectorAll('dot').length > 0;
        if (!dur && type) { avisos.add('Notas mais curtas que semicolcheia viraram semicolcheia.'); dur = '16'; }
        if (!dur) {
          // sem <type> (ex.: pausa de compasso inteiro): pela duração
          const q = (+el.querySelector('duration')?.textContent || divisions) / divisions; // em semínimas
          const opts = [['w', 4], ['h', 2], ['q', 1], ['8', 0.5], ['16', 0.25]];
          const hit = opts.flatMap(([d, v]) => [[d, v * 1.5, true], [d, v, false]]).find(([, v]) => Math.abs(v - q) < 1e-6);
          if (hit) { dur = hit[0]; dotted = hit[2]; } else { dur = 'w'; dotted = false; }
        }
        if (el.querySelectorAll('dot').length > 1) avisos.add('Pontos duplos viraram ponto simples.');

        const i = notas.length;
        if (el.querySelector('rest')) {
          notas.push({ pitch: 'B4', duration: dur, dotted, accidental: '', rest: true, ...(tuplet ? { tuplet } : {}) });
        } else {
          const step = el.querySelector('pitch step')?.textContent?.trim() || 'C';
          const alter = Math.round(+(el.querySelector('pitch alter')?.textContent || 0));
          const oct = +(el.querySelector('pitch octave')?.textContent || 4);
          const acc = ALTER_ACC[alter] || '';
          const shown = XML_ACC[el.querySelector('accidental')?.textContent?.trim()] || '';
          // Igual o editor grava: sem sinal e com a armadura dando conta,
          // só a letra ("F4" em Sol = Fá♯)
          const pitch = (!shown && acc === keyAcc(step, out.keySig)) ? `${step}${oct}` : `${step}${acc}${oct}`;
          notas.push({ pitch, duration: dur, dotted, accidental: shown, rest: false, ...(tuplet ? { tuplet } : {}) });
          const tipos = [...el.querySelectorAll('tie')].map((t) => t.getAttribute('type'));
          if (tipos.includes('stop') && openTies.has(pitch)) {
            out.ties.push({ from: openTies.get(pitch), to: { m, i } });
            openTies.delete(pitch);
          }
          if (tipos.includes('start')) openTies.set(pitch, { m, i });
        }
        if (pendingChord) { out.chords.push({ m, i, symbol: pendingChord }); pendingChord = null; }
      }
    }
  });
  while (out.measures.length > 1 && !out.measures[out.measures.length - 1].length) out.measures.pop();
  if (!out.measures.some((ms) => ms.length)) throw new Error('não achei notas na primeira parte do arquivo');
  return { data: out, avisos: [...avisos] };
}

export async function fromMusicXMLFile(file) {
  return fromMusicXMLText(await xmlTextFromFile(file));
}
