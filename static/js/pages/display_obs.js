// ── Configuração via URL params ───────────────────────────────────
const params = new URLSearchParams(location.search);
const pos    = params.get('pos')    || 'bottom';   // top | center | bottom
const size   = params.get('size')   || '8';        // número em vw
const color  = params.get('color')  || 'white';
const shadow = params.get('shadow') !== '0';       // default on
// Quanto da altura do vídeo a letra pode ocupar (%): embaixo ou em cima, uma
// faixa (35%), para a câmera continuar aparecendo; no centro, quase tudo.
// A fonte diminui até a letra caber. ?altura=85 volta ao jeito antigo.
const altura = Math.min(95, Math.max(10, parseFloat(params.get('altura')) || (pos === 'center' ? 85 : 35)));

const overlay = document.getElementById('overlay');
const root    = document.documentElement;

root.style.setProperty('--txt-size',  size + 'vw');
root.style.setProperty('--txt-color', color);

if (pos === 'top') {
    root.style.setProperty('--v-align', 'flex-start');
    root.style.setProperty('--v-pad',   '8vh');
} else if (pos === 'center') {
    root.style.setProperty('--v-align', 'center');
    root.style.setProperty('--v-pad',   '0');
} else {
    root.style.setProperty('--v-align', 'flex-end');
    root.style.setProperty('--v-pad',   '8vh');
}

if (shadow) {
    document.getElementById('section-text').classList.add('with-shadow');
}

// ── Estado de visibilidade ───────────────────────────────────────
let lyricsHidden    = false;
let hasContent      = false;

function refreshVisibility() {
    const show = hasContent && !lyricsHidden;
    overlay.classList.toggle('visible', show);
}

// ── Utilitários ──────────────────────────────────────────────────
// Introdução/solo (parte sem letra): o nome da música numa legenda pequena
// no pé da tela, por alguns segundos — a câmera mostra a banda tocando e
// uma capa grande taparia a imagem
const LEGENDA_MS = 8000;
let legendaTimer = null;

function esconderLegenda() {
    clearTimeout(legendaTimer);
    document.getElementById('legenda').classList.remove('visivel');
}

function mostrarLegenda(musica, autor) {
    esconderLegenda();
    if (!musica || lyricsHidden) return;
    document.getElementById('legenda-musica').textContent = musica;
    document.getElementById('legenda-autor').textContent = autor || '';
    document.getElementById('legenda').classList.add('visivel');
    legendaTimer = setTimeout(esconderLegenda, LEGENDA_MS);
}

function setContent(html) {
    esconderLegenda();
    document.getElementById('section-text').innerHTML = html;
    hasContent = !!html;
    adjustFontSize();
    refreshVisibility();
}

function adjustFontSize() {
    requestAnimationFrame(() => {
        const el  = document.getElementById('section-text');
        let fs = parseFloat(size);
        el.style.fontSize = fs + 'vw';
        while (el.scrollHeight > window.innerHeight * altura / 100 && fs > 1) {
            fs -= 0.1;
            el.style.fontSize = fs + 'vw';
        }
    });
}

window.addEventListener('resize', adjustFontSize);

// ── Só a letra (mesma regra do telão do público, display_public.js) ──
// Tira a linha de cifra inteira (ChordLines.stripChordLines). Antes caçava
// acorde palavra por palavra e apagava "E" e "A" da letra ("A graça de
// Deus" saía "graça de Deus"). Sem as marcações de formatação, notas de
// palco (//), "___" de alinhamento e sinais de repetição (/: :/).
function escapar(texto) {
    return texto.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function formatLyrics(text) {
    const letra = ChordLines.stripChordLines(
        UcFormato.semRepeticao(UcFormato.semDivisao(UcFormato.limpar(text))));
    return letra.split('\n')
        .filter(line => !line.trim().startsWith('//'))
        .map(line => line.replace(/_+/g, '').trim())
        .filter(line => line !== '')
        .map(escapar)
        .join('<br>');
}

// ── SocketIO ─────────────────────────────────────────────────────
const socket = io();
socket.on('connect', () => socket.emit('identify', { role: 'obs_overlay' }));

function setBibleLabels(reference, version) {
    const refEl = document.getElementById('bible-reference');
    const versionEl = document.getElementById('bible-version');
    if (reference) {
        refEl.textContent = reference;
        refEl.style.display = 'block';
    } else {
        refEl.style.display = 'none';
    }
    if (version) {
        versionEl.textContent = version;
        versionEl.style.display = 'block';
    } else {
        versionEl.style.display = 'none';
    }
}

socket.on('update_lyrics', (data) => {
    setBibleLabels(null, null); // referência/versão são só de Bíblia
    const letra = formatLyrics(data.textoPublico || data.text || '');   // divisão "||": só a parte
    setContent(letra);
    if (!letra) mostrarLegenda(data.musica, data.autor);
});

socket.on('update_bible', (data) => {
    const versos = vs => vs.map(v => `<sup style="font-size:0.55em;vertical-align:super">${v.num}</sup>${v.text}`).join('<br>');
    let text = '';
    if (data.verses && Array.isArray(data.verses)) {
        text = versos(data.verses);
    } else if (data.text) {
        text = data.text.replace(/\n/g, '<br>');
    }
    // Segunda versão (blueprints/bible.py: com_segunda_versao) logo embaixo
    const duas = Array.isArray(data.verses2) && data.verses2.length;
    if (duas) text += `<br><span style="opacity:.8">${versos(data.verses2)}</span>`;
    setBibleLabels(data.reference, duas ? [data.version_abbrev || data.version, data.version2_abbrev].filter(Boolean).join(' · ') : data.version);
    setContent(text);
});

socket.on('lyrics_visibility_changed', (data) => {
    lyricsHidden = !data.visible;
    if (lyricsHidden) esconderLegenda();
    refreshVisibility();
});

// ── Ticker ───────────────────────────────────────────────────────
function updateTicker(text) {
    const bar  = document.getElementById('ticker-bar');
    const span = document.getElementById('ticker-text');
    if (!text) { bar.style.display = 'none'; return; }
    span.textContent = text;
    span.style.animationDuration = Math.max(10, text.length * 0.3) + 's';
    bar.style.display = 'block';
}
socket.on('ticker_update', (data) => updateTicker(data.text || ''));
fetch('/api/ticker').then(r => r.json()).then(d => updateTicker((d.by_target || {}).obs || '')).catch(() => {});
