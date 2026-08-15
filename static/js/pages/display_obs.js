// ── Configuração via URL params ───────────────────────────────────
const params = new URLSearchParams(location.search);
const pos    = params.get('pos')    || 'bottom';   // top | center | bottom
const size   = params.get('size')   || '8';        // número em vw
const color  = params.get('color')  || 'white';
const shadow = params.get('shadow') !== '0';       // default on

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
let blackoutActive  = false;
let lyricsHidden    = false;
let hasContent      = false;

function refreshVisibility() {
    const show = hasContent && !blackoutActive && !lyricsHidden;
    overlay.classList.toggle('visible', show);
}

// ── Utilitários ──────────────────────────────────────────────────
function setContent(html) {
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
        while (el.scrollHeight > window.innerHeight * 0.85 && fs > 2) {
            fs -= 0.2;
            el.style.fontSize = fs + 'vw';
        }
    });
}

window.addEventListener('resize', adjustFontSize);

// ── Remoção de acordes (igual ao display_public.html) ────────────
function formatLyrics(text) {
    const lines = text.split('\n');
    return lines.map(line => {
        // Remove notas privadas de palco
        if (line.trim().startsWith('//')) return '';

        const testLine = line.replace(/[\s_]+/g, ' ').trim();
        if (/^[A-G0-9#♯♭b°º\/\(\)+maijndugse\s]+$/i.test(testLine) && testLine.length > 0) {
            if (!/[a-záàâãéèêíïóôõöúçñ]{5,}/i.test(testLine)) return '';
        }
        let cleaned = line
            .replace(/\b([CDFGB])(?:[b#♭♯])?(?:\d+)?(?:m|maj|min|dim|aug|sus|add)?(?:\d+)?(?:\([^)]*\))?(?:\/[CDEFGAB](?:[b#♭♯])?)?\b(?![a-záàâãéèêíïóôõöúçñ])/gi, '')
            .replace(/\(\d+\)/g, '')
            .replace(/\s+\d+\s+/g, ' ')
            .replace(/[#♯♭°º]/g, '')
            .replace(/_/g, '')
            .replace(/\(\s*\)/g, '')
            .replace(/\[\s*\]/g, '')
            .replace(/\|\s*[A-G](?:[b#♭♯])?(?:m|maj|min|dim|aug|sus|add)?\d*(?:\([^)]*\))?(?:\/[A-G](?:[b#♭♯])?)?\s*\|/gi, '')
            .replace(/\|/g, '')
            .replace(/(^|\s)([A-G])(?=\s|$)/g, '$1')
            .replace(/\b([A-G])\/(?:[A-G](?:\d+)?(?:[b#♭♯])?)?\b/gi, '')
            .replace(/\//g, '')
            .replace(/\+/g, '')
            .replace(/\s+/g, ' ')
            .trim();
        return cleaned;
    })
    .filter(l => l !== '')
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
    setContent(formatLyrics(data.text || ''));
});

socket.on('update_bible', (data) => {
    let text = '';
    if (data.verses && Array.isArray(data.verses)) {
        text = data.verses.map(v => `<sup style="font-size:0.55em;vertical-align:super">${v.num}</sup>${v.text}`).join('<br>');
    } else if (data.text) {
        text = data.text.replace(/\n/g, '<br>');
    }
    setBibleLabels(data.reference, data.version);
    setContent(text);
});

socket.on('blackout', (data) => {
    blackoutActive = !!data.active;
    refreshVisibility();
});

socket.on('lyrics_visibility_changed', (data) => {
    lyricsHidden = !data.visible;
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
fetch('/api/ticker').then(r => r.json()).then(d => { if (d.active) updateTicker(d.text || ''); }).catch(() => {});
