 document.addEventListener('DOMContentLoaded', function () {
    setupPanel();
    setupModeChoice();
    setupSourcePicker();
    setupPreviewScaling();
    loadUrls();
    loadDisplayState(); // Carrega estado salvo ao iniciar
    loadStagedContent(); // Carrega o que já estiver preparado, se algo estiver
    fetch('/api/countdown/config')
        .then(function(r) { return r.json(); })
        .then(function(cfg) {
            if (cfg.label) document.getElementById('countdownLabel').value = cfg.label;
        })
        .catch(function() {});
    fetch('/api/ticker')
        .then(function(r) { return r.json(); })
        .then(function(d) {
            if (d.text) document.getElementById('tickerText').value = d.text;
        })
        .catch(function() {});
});

const socket = io.connect(`${window.location.protocol}//${window.location.host}`);

// Escuta eventos WebSocket para sincronizar iframes entre PCs
socket.on('display_image', function(data) {
    console.log('📡 Recebido display_image de outro PC:', data);

    // Se a URL é uma rota (começa com /), atualiza os iframes
    if (data.image_url.startsWith('/') && !data.image_url.startsWith('/static/')) {
        updateIframes(data.image_url, '');
    } else if (document.getElementById('iframe1').getAttribute('src') !== '/img'
               || document.getElementById('iframe2').getAttribute('src') !== 'about:blank') {
        // Foto/vídeo da galeria: a prévia passa a mostrar o /img (que
        // troca a foto sozinho via WebSocket). Só recarrega se a prévia
        // estava em outra coisa — antes ela ficava parada na fonte anterior.
        updateIframes(data.image_url, '');
    }
});

// Escuta o evento para mostrar/esconder letras
socket.on('lyrics_visibility_changed', function(data) {
    const visible = data.visible;
    console.log(`👁️ Home: Letras ${visible ? 'mostradas' : 'escondidas'}`);
    
    const iframe1 = document.getElementById('iframe1');
    const iframe2 = document.getElementById('iframe2');
    
    if (!iframe1 || !iframe2) {
        console.warn('⚠️ Home: Iframes não encontrados');
        return;
    }
    
    // Verifica qual iframe tem letras (contém /lyrics/display)
    const iframe1HasLyrics = iframe1.src.includes('/lyrics/display');
    const iframe2HasLyrics = iframe2.src.includes('/lyrics/display');
    
    console.log(`  iframe1 tem letras: ${iframe1HasLyrics}`);
    console.log(`  iframe2 tem letras: ${iframe2HasLyrics}`);
    
    // Esconde/mostra apenas o iframe que tem letras
    // Usa visibility para manter o espaço e posição
    if (iframe1HasLyrics) {
        iframe1.style.visibility = visible ? 'visible' : 'hidden';
    }
    if (iframe2HasLyrics) {
        iframe2.style.visibility = visible ? 'visible' : 'hidden';
    }
});

function sendUrl(urlNumber) {
    const fixedRoutes = {
        4: "/lyrics/display",
        5: "/clock",
        6: "/img",
        7: "/bible/display",
        8: "/lyrics/display/public",
        9: "/tela-do-pc"
    };

    const urlInput = fixedRoutes[urlNumber] || document.getElementById(`url${urlNumber}`)?.value;
    if (!urlInput) return console.error("URL não definida ou vazia.");

    console.warn('⚠️ sendUrl: Mostrando apenas 1 URL. Se quiser manter 2 URLs (ex: Cifra + Relógio), use o botão "URL 1/2"');
    socket.emit('show_image', { image_url: urlInput, exclude_monitor: publicOnlyMode });
    updateIframes(urlInput, '');
}

function showTwoUrls(urlNum1, urlNum2) {
    const fixedRoutes = {
        4: "/lyrics/display",
        5: "/clock",
        6: "/img",
        7: "/bible/display",
        8: "/lyrics/display/public",
        9: "/tela-do-pc"
    };

    const url1 = fixedRoutes[urlNum1] || document.getElementById(`url${urlNum1}`)?.value;
    const url2 = fixedRoutes[urlNum2] || document.getElementById(`url${urlNum2}`)?.value;
    if (!url1 || !url2) return console.error("Uma ou ambas as URLs não foram definidas.");

    socket.emit('show_two_urls', { url1, url2, exclude_monitor: publicOnlyMode });
    // Prévia não muda: a tela dividida só aparece no monitor de palco
    // (aparece na linha "Monitor de palco" embaixo da prévia)
}

function updateIframes(url1, url2) {
    const iframe1 = document.getElementById('iframe1');
    const iframe2 = document.getElementById('iframe2');
    // Arquivos estáticos (imagens, vídeos) são exibidos via /img,
    // que sabe carregar e tocar o conteúdo correto.
    if (url1 && url1.startsWith('/static/')) url1 = '/img';
    if (url2 && url2.startsWith('/static/')) url2 = '/img';
    // src vazio carrega a própria página (/control) dentro do iframe
    // escondido — about:blank evita esse segundo painel invisível.
    iframe1.src = url1 || 'about:blank';
    iframe2.src = url2 || 'about:blank';
    iframe1.style.width = url2 ? '50%' : '100%';
    iframe2.style.width = url2 ? '50%' : '0';
}

function saveUrls() {
    const urls = {};
    [1, 2, 3].forEach(i => {
        urls[`url${i}`] = document.getElementById(`url${i}`).value.trim();
        urls[`name${i}`] = document.getElementById(`name${i}`).value.trim();
    });
    // Uma página do próprio Controle no telão mostraria o Controle pro público
    const selfPage = [1, 2, 3].find(i => /\/control(\b|$|\?)/.test(urls[`url${i}`]));
    fetch('/save_urls', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(urls)
    }).then(res => res.json())
      .then(data => {
          if (data.status !== 'success' || !window.ucToast) return;
          window.ucToast('URLs salvas.');
          if (selfPage) window.ucToast(`Atenção: a URL ${selfPage} é a página do Controle — no telão, o público veria o Controle.`, 'error');
      })
      .catch(() => window.ucToast && window.ucToast('Não deu pra salvar as URLs.', 'error'));
}

function loadUrls() {
    fetch('/load_urls')
        .then(res => res.json())
        .then(urls => {
            [1, 2, 3].forEach(i => {
                document.getElementById(`url${i}`).value = urls[`url${i}`] || '';
                document.getElementById(`name${i}`).value = urls[`name${i}`] || '';
            });
            refreshSourceButtons();
        });
}

// Carrega o estado salvo do display ao iniciar
function loadDisplayState() {
    fetch('/get_display_state')
        .then(res => res.json())
        .then(state => {
            console.log('💾 Estado carregado do banco:', state);
            if (state.url1 || state.url2) {
                let url1 = state.url1;
                let url2 = state.url2;
                // Imagens estáticas são exibidas via /img (que carrega a última imagem salva)
                if (url1 && url1.startsWith('/static/')) url1 = '/img';
                if (url2 && url2.startsWith('/static/')) url2 = '/img';
                updateIframes(url1, url2);
            }
        })
        .catch(err => console.error('❌ Erro ao carregar estado:', err));
}









let blackoutActive = false;

function toggleBlackout() {
    socket.emit('blackout', { active: !blackoutActive });
    setBlackoutButton(!blackoutActive);
}

// O servidor guarda o estado: ao abrir o /control (identify) ou quando
// outro operador/o /presenter liga a tela preta, o botão acompanha
socket.on('connect', () => socket.emit('identify', { role: 'control' }));
socket.on('blackout', data => setBlackoutButton(!!data.active));

function setBlackoutButton(active) {
    blackoutActive = active;
    const btn = document.getElementById('blackoutBtn');
    btn.classList.toggle('active', blackoutActive);
    btn.querySelector('i').className = blackoutActive ? 'fas fa-sun' : 'fas fa-moon';
    btn.querySelector('span').textContent = blackoutActive ? 'Voltar a imagem' : 'Tela preta';
    const overlay = document.getElementById('preview-blackout');
    if (overlay) overlay.hidden = !blackoutActive;
}

// Funções do Ticker — escolhe as telas (uma, duas ou as três); cada tela
// guarda o próprio aviso, então "Mostrar"/"Tirar" só mexem nas escolhidas
const TICKER_NOMES = { public: 'Tela pública', monitor: 'Palco', obs: 'Transmissão' };
function tickerTelas() {
    return [...document.querySelectorAll('.ticker-telas button[aria-pressed="true"]')].map(b => b.dataset.tela);
}
document.querySelectorAll('.ticker-telas button').forEach(btn => btn.addEventListener('click', () => {
    btn.setAttribute('aria-pressed', String(btn.getAttribute('aria-pressed') !== 'true'));
    try { localStorage.setItem('uc_ticker_telas', JSON.stringify(tickerTelas())); } catch (e) { /* sem storage */ }
}));
try {
    const salvas = JSON.parse(localStorage.getItem('uc_ticker_telas') || 'null');
    if (Array.isArray(salvas) && salvas.length) {
        document.querySelectorAll('.ticker-telas button').forEach(b => b.setAttribute('aria-pressed', String(salvas.includes(b.dataset.tela))));
    }
} catch (e) { /* sem storage */ }

function sendTicker() {
    const text = document.getElementById('tickerText').value.trim();
    const telas = tickerTelas();
    if (!text) return window.ucToast && ucToast('Escreva o aviso primeiro.', 'error');
    if (!telas.length) return window.ucToast && ucToast('Escolha pelo menos uma tela.', 'error');
    socket.emit('set_ticker', { text: text, targets: telas });
}
function stopTicker() {
    const telas = tickerTelas();
    if (!telas.length) return window.ucToast && ucToast('Escolha de quais telas tirar.', 'error');
    socket.emit('stop_ticker', { targets: telas });
}
function clearTicker() {
    document.getElementById('tickerText').value = '';
    socket.emit('stop_ticker', { target: 'all' });
}

// O que está em cada tela agora, embaixo dos botões
function renderTickerAgora(porTela) {
    const ul = document.getElementById('tickerAgora');
    if (!ul) return;
    ul.innerHTML = '';
    Object.keys(TICKER_NOMES).forEach(t => {
        const li = document.createElement('li');
        const nome = document.createElement('strong');
        nome.textContent = TICKER_NOMES[t] + ': ';
        li.append(nome, document.createTextNode(porTela[t] ? '“' + porTela[t] + '”' : 'sem aviso'));
        ul.appendChild(li);
    });
}

// Preview do ticker no próprio /control (não depende do alvo escolhido —
// mostra o último texto mandado, pra conferir sem abrir o /monitor).
function updateControlTickerPreview(text) {
    const bar = document.getElementById('control-ticker-bar');
    const span = document.getElementById('control-ticker-text');
    if (!bar || !span) return;
    if (!text) { bar.style.display = 'none'; return; }
    span.textContent = text;
    bar.style.display = 'block';
}
// Prévia mostra o aviso da tela pública (é o que a prévia representa)
socket.on('ticker_preview_update', function (data) {
    const porTela = data.by_target || {};
    updateControlTickerPreview(porTela.public || '');
    renderTickerAgora(porTela);
});
fetch('/api/ticker').then(r => r.json()).then(d => {
    updateControlTickerPreview((d.by_target || {}).public || '');
    renderTickerAgora(d.by_target || {});
});

// ── Compartilhar Tela (WebRTC) ───────────────────────────────────────────────
// Quem assiste: static/js/screen_share_viewer.js; servidor: blueprints/screen_share.py
let _screenStream = null;
let _screenTarget = null;
let _screenPeers = {};
const _iceConfig = { iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] };
const _SHARE_ALVOS = { public: 'tela pública', monitor: 'retorno de palco', all: 'tela pública e palco' };

function _shareStatus(texto) {
    const el = document.getElementById('screenShareStatus');
    if (el) el.textContent = texto;
}

function _shareContagem() {
    if (!_screenStream) return;
    const n = Object.values(_screenPeers).filter(pc => pc.connectionState === 'connected').length;
    _shareStatus(`● Compartilhando na ${_SHARE_ALVOS[_screenTarget]} — ${n} ${n === 1 ? 'tela recebendo' : 'telas recebendo'}`);
}

async function startScreenShare(target) {
    _screenTarget = target || 'all';
    if (_screenStream) {  // já compartilhando: só troca o alvo
        socket.emit('screen_share_start', { target: _screenTarget });
        _shareContagem();
        return;
    }
    // O navegador só deixa capturar a tela em endereço seguro: no próprio PC
    // do U-Control (127.0.0.1 / localhost) ou por HTTPS — não pelo IP da rede
    if (!navigator.mediaDevices || !navigator.mediaDevices.getDisplayMedia) {
        _shareStatus('Este navegador não deixa compartilhar a tela por este endereço. Abra o Controle no próprio computador do U-Control (http://127.0.0.1:8585) ou pelo endereço https.');
        return;
    }
    try {
        _screenStream = await navigator.mediaDevices.getDisplayMedia({
            video: { frameRate: { ideal: 30, max: 30 }, width: { max: 1920 }, height: { max: 1080 } },
            audio: true,
        });
    } catch (e) {
        _shareStatus(e && e.name === 'NotAllowedError' ? 'Cancelado.' : 'Não deu pra capturar a tela: ' + (e && e.message || e));
        return;
    }
    const video = _screenStream.getVideoTracks()[0];
    video.onended = stopScreenShare;  // "Parar de compartilhar" do navegador
    // Letra e slide: com pouca banda, o navegador mantém o texto nítido e
    // baixa a fluidez (em vez de borrar pra manter o movimento)
    video.contentHint = 'detail';
    socket.emit('screen_share_start', { target: _screenTarget });
    _shareContagem();
}

function _fecharPeer(sid) {
    const pc = _screenPeers[sid];
    if (!pc) return;
    pc.onconnectionstatechange = null;
    pc.close();
    delete _screenPeers[sid];
}

function stopScreenShare() {
    if (_screenStream) { _screenStream.getTracks().forEach(t => t.stop()); _screenStream = null; }
    Object.keys(_screenPeers).forEach(_fecharPeer);
    socket.emit('screen_share_stop', {});
    _shareStatus('');
}

// Reconectou (Wi-Fi caiu, servidor reiniciou): avisa de novo que está
// compartilhando, senão o servidor esquece e para as telas
socket.on('connect', function () {
    if (_screenStream) socket.emit('screen_share_start', { target: _screenTarget });
});

// O Chrome segura o vídeo em ~2,5 Mbps (pensado pra internet); na rede
// local cabe bem mais, e é isso que deixa letra e slide nítidos
const _SHARE_MAX_BITRATE = 8000000;

async function _limitesVideo(sender) {
    try {
        const p = sender.getParameters();
        if (!p.encodings || !p.encodings.length) p.encodings = [{}];
        p.encodings[0].maxBitrate = _SHARE_MAX_BITRATE;
        p.degradationPreference = 'maintain-resolution';
        await sender.setParameters(p);
    } catch (e) {
        console.warn('Tela do PC: limites de vídeo não aplicados', e);
    }
}

socket.on('screen_share_request', async function(data) {
    if (!_screenStream) return;
    _fecharPeer(data.from_sid);  // tela que pediu de novo (recarregou, falhou)
    const pc = new RTCPeerConnection(_iceConfig);
    pc._pendentes = [];
    _screenPeers[data.from_sid] = pc;
    _screenStream.getTracks().forEach(t => {
        const sender = pc.addTrack(t, _screenStream);
        if (t.kind === 'video') _limitesVideo(sender);
    });
    pc.onicecandidate = e => {
        if (e.candidate) socket.emit('screen_share_ice', { target_sid: data.from_sid, candidate: e.candidate });
    };
    pc.onconnectionstatechange = () => {
        if (['failed', 'closed'].includes(pc.connectionState)) _fecharPeer(data.from_sid);
        _shareContagem();
    };
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    socket.emit('screen_share_offer', { target_sid: data.from_sid, sdp: offer });
});

socket.on('screen_share_answer', async function(data) {
    const pc = _screenPeers[data.from_sid];
    if (!pc) return;
    await pc.setRemoteDescription(new RTCSessionDescription(data.sdp));
    pc._pendentes.splice(0).forEach(c => pc.addIceCandidate(c).catch(() => {}));
});

socket.on('screen_share_ice', function(data) {
    const pc = _screenPeers[data.from_sid];
    if (!pc) return;
    const c = new RTCIceCandidate(data.candidate);
    // ICE antes da resposta chegar: guarda (antes era descartado)
    if (pc.remoteDescription) pc.addIceCandidate(c).catch(() => {});
    else pc._pendentes.push(c);
});

// Funções do Cronômetro
let _countdownPaused = false;

function showCountdownOnMonitor() {
    socket.emit('show_image', { image_url: '/countdown' });
}

function startCountdown() {
    const min = parseInt(document.getElementById('countdownMin').value) || 0;
    const sec = parseInt(document.getElementById('countdownSec').value) || 0;
    const total = min * 60 + sec;
    if (total <= 0) return;
    const label = document.getElementById('countdownLabel').value.trim();
    _countdownPaused = false;
    document.getElementById('btnCountdownPause').textContent = '⏸ Pausar';
    socket.emit('start_countdown', { duration_seconds: total, label: label });
}

function pauseResumeCountdown() {
    if (_countdownPaused) {
        socket.emit('resume_countdown', {});
        _countdownPaused = false;
        document.getElementById('btnCountdownPause').textContent = '⏸ Pausar';
    } else {
        socket.emit('pause_countdown', {});
        _countdownPaused = true;
        document.getElementById('btnCountdownPause').textContent = '▶ Retomar';
    }
}

function resetCountdown() {
    _countdownPaused = false;
    document.getElementById('btnCountdownPause').textContent = '⏸ Pausar';
    socket.emit('reset_countdown', {});
}

// Funções para Bíblia
function showBibleInIframe() {
    const iframe1 = document.getElementById('iframe1');
    const iframe2 = document.getElementById('iframe2');
    iframe1.src = '/bible';
    iframe2.src = 'about:blank';
    console.log('📖 Bíblia carregada no iframe');
}

function showBibleDisplay() {
    const iframe1 = document.getElementById('iframe1');
    const iframe2 = document.getElementById('iframe2');
    iframe1.src = '/bible';
    iframe2.src = '/bible/display';
    console.log('📖 Bíblia + Display carregados');
    
    // Emite evento para sincronizar com outros dispositivos
    socket.emit('display_two_urls', {
        url1: '/bible',
        url2: '/bible/display'
    });
}

// ── Modo Monitor de Palco ─────────────────────────────────────────────────
let monitorOnlyMode = false;
let publicOnlyMode = false;

// Mostra os modos nos interruptores, nas faixas da prévia e no selo.
// O servidor é a fonte da verdade (telao_status): assim o /control
// recarregado ou aberto em outro PC mostra o modo que está valendo — antes
// voltava "desligado" enquanto o servidor seguia em Só monitor, e o
// próximo clique saía como se não houvesse modo.
function renderModes() {
    const mode = monitorOnlyMode ? 'monitor' : publicOnlyMode ? 'public' : 'all';
    document.querySelectorAll('.mode-seg [data-mode]').forEach(btn => {
        btn.setAttribute('aria-pressed', String(btn.dataset.mode === mode));
    });
    document.getElementById('monitor-mode-indicator').style.display = monitorOnlyMode ? 'flex' : 'none';
    document.getElementById('public-mode-indicator').style.display = publicOnlyMode ? 'flex' : 'none';
    updateModePill();
}

// O servidor guarda um modo por máquina (cookie uc_device — ver
// display_state._device_modes): dois /control em PCs diferentes, um no
// público e outro no monitor, não trocam o modo um do outro.
function myMode(st) {
    if (st.mode) return st.mode;  // GET /api/telao-status já vem com o desta máquina
    const m = document.cookie.match(/(?:^|;\s*)uc_device=([^;]*)/);
    return (st.modes || {})[m ? decodeURIComponent(m[1]) : null] || 'all';
}

function applyServerMode(mode) {
    const was = monitorOnlyMode ? 'monitor' : publicOnlyMode ? 'public' : 'all';
    monitorOnlyMode = mode === 'monitor';
    publicOnlyMode = mode === 'public';
    // Entrou ou saiu do Só monitor: a prévia acompanha a tela que está mudando
    if (mode !== was) previewView = monitorOnlyMode ? 'monitor' : 'public';
    renderModes();
}

// "O que as ações mudam": Os dois | Só público | Só monitor — uma escolha
// só (antes eram dois interruptores que se desligavam um ao outro).
// Só público: o monitor de palco fica congelado no que já mostrava.
function setModeChoice(mode) {
    monitorOnlyMode = mode === 'monitor';
    publicOnlyMode = mode === 'public';
    // A prévia passa a mostrar a tela que vai mudar
    previewView = monitorOnlyMode ? 'monitor' : 'public';
    renderModes();
    renderPreview();
    // Manda o modo pro servidor — fonte única de verdade que _release_kind
    // usa pra QUALQUER liberação (card do /control ou banner nas próprias
    // páginas, ver display_state._device_modes). Também reseta o
    // live-follow, senão um live-follow em andamento continuaria usando o
    // modo ANTIGO até a próxima liberação explícita.
    socket.emit('set_display_mode', { exclude_monitor: publicOnlyMode, monitor_only: monitorOnlyMode });
}

function setupModeChoice() {
    document.querySelectorAll('.mode-seg [data-mode]').forEach(btn => {
        btn.addEventListener('click', () => setModeChoice(btn.dataset.mode));
    });
}

function syncMonitor() {
    fetch('/api/monitor/sync', { method: 'POST' })
        .then(r => r.ok ? r.json() : Promise.reject(r.status))
        .then(d => {
            if (!window.ucToast) return;
            if (d.monitors === 0) window.ucToast('Nenhum monitor de palco conectado agora.', 'error');
            else window.ucToast('Monitor de palco sincronizado com o público.');
        })
        .catch(e => {
            console.error('Erro ao sincronizar monitor:', e);
            if (window.ucToast) window.ucToast('Não deu pra sincronizar o monitor.', 'error');
        });
}

// ── Prévia "Telão agora" = tela pública ─────────────────────────────────
// Segue o estado do servidor (telao.py): mostra o que o público vê,
// inclusive letra/Bíblia liberadas por outras páginas (antes a prévia só
// mudava com fontes escolhidas aqui e ficava na fonte anterior). O que
// muda só no monitor (Modo monitor, tela dividida) aparece na linha de
// baixo, não na prévia.
// Qual tela a prévia mostra: 'public' ou 'monitor' (seletor acima dela)
let previewView = 'public';
let lastTelaoStatus = null;

function applyTelaoStatus(st) {
    if (!st || !st.live) return;
    lastTelaoStatus = st;
    applyServerMode(myMode(st));
    setBlackoutButton(!!st.blackout);
    renderPreview();
}

function renderPreview() {
    const st = lastTelaoStatus;
    if (!st) return;
    const showMonitor = previewView === 'monitor';
    document.querySelectorAll('.preview-view-seg [data-preview]').forEach(b =>
        b.setAttribute('aria-pressed', String(b.dataset.preview === previewView)));
    document.getElementById('preview-screen-label').hidden = !showMonitor;

    // Endereços da tela escolhida (monitor sem nada diferente = o mesmo do público)
    let url1 = st.live.url || '';
    let url2 = '';
    if (showMonitor && st.monitor) {
        if (st.monitor.kind === 'split') { url1 = st.monitor.url1; url2 = st.monitor.url2; }
        else url1 = st.monitor.url || url1;
    }
    // Vista do monitor: as páginas da prévia se apresentam como monitor
    // (host=monitor, igual o /monitor faz) — senão, em "Só público", a
    // prévia do monitor mudava junto com o público
    const comoMonitor = u => {
        if (!showMonitor || !u || !u.startsWith('/')) return u;
        if (u.startsWith('/static/')) u = '/img';   // foto/vídeo do monitor: pela /img dele
        return /[?&]host=monitor\b/.test(u) ? u : u + (u.includes('?') ? '&' : '?') + 'host=monitor';
    };
    url1 = comoMonitor(url1);
    url2 = comoMonitor(url2);
    const norm = u => (u && u.startsWith('/static/') ? '/img' : (u || 'about:blank'));
    const f1 = document.getElementById('iframe1');
    const f2 = document.getElementById('iframe2');
    if (url1 && (f1.getAttribute('src') !== norm(url1) || f2.getAttribute('src') !== norm(url2))) {
        updateIframes(url1, url2);
    }
    // Cifra (vista do público): o público vê a letra e o palco a cifra —
    // acende o botão Cifra (o que o operador escolheu), não o Letra
    if (!showMonitor && st.live.kind === 'lyrics' && st.monitor && st.monitor.kind === 'cifra') {
        onAir = ['cifra'];
        refreshSourceButtons();
    }
    // A linha de baixo mostra sempre a OUTRA tela
    const note = document.getElementById('preview-monitor-note');
    if (note) {
        const other = showMonitor ? (st.monitor ? st.live : null) : st.monitor;
        note.hidden = !other;
        if (other) {
            note.innerHTML = showMonitor ? '<i class="fas fa-users"></i> Público: <b></b>' : '<i class="fas fa-tv"></i> Monitor de palco: <b></b>';
            note.querySelector('b').textContent = other.label;
        }
    }
}

document.querySelectorAll('.preview-view-seg [data-preview]').forEach(b => b.addEventListener('click', () => {
    previewView = b.dataset.preview;
    renderPreview();
}));
socket.on('telao_status', applyTelaoStatus);
socket.on('connect', () => {
    fetch('/api/telao-status').then(r => (r.ok ? r.json() : null)).then(applyTelaoStatus).catch(() => {});
});

// Intercepta sendUrl: em modo monitor, envia só ao /monitor
const _origSendUrl = sendUrl;
sendUrl = function(urlNumber) {
    if (monitorOnlyMode) {
        const fixedRoutes = { 4:'/lyrics/display', 5:'/clock', 6:'/img', 7:'/bible/display', 8:'/lyrics/display/public' };
        const url = fixedRoutes[urlNumber] || document.getElementById(`url${urlNumber}`)?.value;
        if (!url) return;
        socket.emit('show_monitor_content', { url });
        return;
    }
    _origSendUrl(urlNumber);
};

// Intercepta showTwoUrls: em modo monitor, envia tela dividida só ao /monitor
const _origShowTwoUrls = showTwoUrls;
showTwoUrls = function(urlNum1, urlNum2) {
    // "Monitor dividido" só existe no palco: em "Só público" também vai
    // direto pro monitor (antes saía com exclude_monitor — o público não
    // divide e o monitor era excluído, então o botão não fazia nada)
    if (monitorOnlyMode || publicOnlyMode) {
        const fixedRoutes = { 4:'/lyrics/display', 5:'/clock', 6:'/img', 7:'/bible/display', 8:'/lyrics/display/public' };
        const url1 = fixedRoutes[urlNum1] || document.getElementById(`url${urlNum1}`)?.value;
        const url2 = fixedRoutes[urlNum2] || document.getElementById(`url${urlNum2}`)?.value;
        if (!url1 || !url2) return;
        socket.emit('show_monitor_two_urls', { url1, url2 });
        return;
    }
    _origShowTwoUrls(urlNum1, urlNum2);
};

// ── "Preparar vs. liberar" ──────────────────────────────────────────────
// /lyrics/<id>, /bible/control, /bible/<book>/<chapter> e /presenter (fotos)
// não mudam mais a tela sozinhos — só preparam (stage_content). Aqui é onde
// aparece o que está preparado, e onde libera (release_staged_content) ou
// descarta (discard_staged_content). Ver blueprints/display.py.
const _KIND_ICONS = { lyrics: 'fa-music', bible: 'fa-book-bible', image: 'fa-image' };
const _KIND_LABELS_PT = { lyrics: 'Letra', bible: 'Bíblia', image: 'Foto' };
let _stagedItems = {}; // kind -> { label }

function renderStagedPanel() {
    const panel = document.getElementById('staged-panel');
    if (!panel) return;
    const kinds = Object.keys(_stagedItems);
    if (kinds.length === 0) {
        panel.innerHTML = '';
        return;
    }
    panel.innerHTML = kinds.map(kind => {
        const item = _stagedItems[kind];
        const icon = _KIND_ICONS[kind] || 'fa-clone';
        const kindLabel = _KIND_LABELS_PT[kind] || kind;
        return `
            <div class="staged-card" data-kind="${kind}">
                <i class="fas ${icon} staged-icon"></i>
                <div class="staged-text">
                    <span class="staged-kind">${kindLabel} preparado</span>
                    <span class="staged-label"></span>
                </div>
                <button class="btn-release" onclick="releaseStagedContent('${kind}')">Liberar</button>
                <button class="btn-discard" onclick="discardStagedContent('${kind}')">Descartar</button>
            </div>
        `;
    }).join('');
    // Texto via textContent, não montado na string acima — evita que um
    // título/referência com caractere de HTML (ex: "&") quebre o markup.
    kinds.forEach(kind => {
        const card = panel.querySelector(`.staged-card[data-kind="${kind}"] .staged-label`);
        if (card) card.textContent = _stagedItems[kind].label;
    });
}

function loadStagedContent() {
    fetch('/api/staged-content')
        .then(res => res.json())
        .then(data => {
            _stagedItems = {};
            Object.keys(data).forEach(kind => {
                _stagedItems[kind] = { label: data[kind].label };
            });
            renderStagedPanel();
        })
        .catch(err => console.error('❌ Erro ao carregar conteúdo preparado:', err));
}

function releaseStagedContent(kind) {
    // Modo Público/Monitor não precisa ser mandado aqui — o servidor já
    // sabe o desta máquina (display_state._device_modes, via set_display_mode
    // em setModeChoice) e aplica pra qualquer
    // liberação, venha daqui ou do banner nas próprias páginas.
    socket.emit('release_staged_content', { kind });
}

function discardStagedContent(kind) {
    socket.emit('discard_staged_content', { kind });
}

socket.on('content_staged', function(data) {
    _stagedItems[data.kind] = { label: data.label };
    renderStagedPanel();
});

socket.on('content_released', function(data) {
    delete _stagedItems[data.kind];
    renderStagedPanel();
});

socket.on('content_discarded', function(data) {
    delete _stagedItems[data.kind];
    renderStagedPanel();
});


// ── Layout novo (tema único): abas, prévia em escala e seletor de fontes ──
// Substitui a sidebar de submenus e os 40 botões de combinação (URL 1/2,
// Imagem/Cifra, Letra/Relógio…). As 8 fontes chamam as mesmas
// sendUrl()/showTwoUrls() de sempre, com os mesmos números de antes.

const SOURCES = [
    { id: 'letra',   num: 8, label: 'Letra',   icon: 'fa-align-left',  sub: 'texto da música', route: '/lyrics/display/public' },
    { id: 'cifra',   num: 4, label: 'Cifra',   icon: 'fa-guitar',      sub: 'cifra no palco', route: '/lyrics/display' },
    { id: 'biblia',  num: 7, label: 'Bíblia',  icon: 'fa-book-bible',  sub: 'versículo',       route: '/bible/display' },
    { id: 'imagem',  num: 6, label: 'Imagem',  icon: 'fa-image',       sub: 'galeria',         route: '/img' },
    { id: 'relogio', num: 5, label: 'Relógio', icon: 'fa-clock',       sub: 'hora atual',      route: '/clock' },
    { id: 'tela',    num: 9, label: 'Tela do PC', icon: 'fa-desktop',  sub: 'compartilhada',   route: '/tela-do-pc' },
    { id: 'url1',    num: 1, label: 'URL 1',   icon: 'fa-globe' },
    { id: 'url2',    num: 2, label: 'URL 2',   icon: 'fa-globe' },
    { id: 'url3',    num: 3, label: 'URL 3',   icon: 'fa-globe' },
];
const SOURCE_BY_ID = Object.fromEntries(SOURCES.map(src => [src.id, src]));

// Escolha em andamento no "Monitor dividido" (ferramenta no painel)
let splitPick = { left: null, right: null };
let onAir = [];                        // fontes no ar, derivadas dos iframes da prévia

function urlInputValue(src) {
    const el = src.route ? null : document.getElementById(src.id);
    return el ? el.value.trim() : '';
}

function sourceSubLabel(src) {
    if (src.route) return src.sub;
    const value = urlInputValue(src);
    if (!value) return 'vazia';
    try { return new URL(value, window.location.origin).hostname.replace(/^www\./, ''); }
    catch (e) { return value; }
}

// Descobre a fonte a partir da URL de um iframe da prévia.
function sourceFromUrl(url) {
    if (!url || url === 'about:blank') return null;
    let path = url;
    try { path = new URL(url, window.location.origin).pathname; } catch (e) { /* mantém */ }
    // URL personalizada primeiro (comparação exata), senão uma URL 1–3
    // como "/clock?x" acendia o Relógio em vez dela
    const custom = SOURCES.find(src => !src.route && urlInputValue(src) && urlInputValue(src) === url);
    if (custom) return custom.id;
    // Foto/vídeo da galeria vai pra prévia como /img (ver updateIframes)
    if (path.startsWith('/static/')) return 'imagem';
    const fixed = SOURCES.find(src => src.route && src.route === path);
    return fixed ? fixed.id : null;
}

// Nome do botão: URL 1–3 usam o nome dado na ferramenta URLs
function sourceLabel(src) {
    if (src.route) return src.label;
    const el = document.getElementById(src.id.replace('url', 'name'));
    return (el && el.value.trim()) || src.label;
}

function renderSourceButtons() {
    document.querySelectorAll('.sources').forEach(box => {
        box.innerHTML = SOURCES.map(src => `
            <button type="button" class="src-btn" data-src="${src.id}" aria-pressed="false">
                <i class="fas ${src.icon}"></i><span class="src-label"></span><small></small>
            </button>`).join('');
    });
    refreshSourceButtons();
}

function refreshSourceButtons() {
    document.querySelectorAll('.sources').forEach(box => {
        const slot = box.dataset.slot;
        box.querySelectorAll('.src-btn').forEach(btn => {
            const src = SOURCE_BY_ID[btn.dataset.src];
            btn.querySelector('.src-label').textContent = sourceLabel(src);
            btn.querySelector('small').textContent = sourceSubLabel(src);
            btn.disabled = !src.route && !urlInputValue(src);
            if (slot === 'a') {
                // Fontes da tela cheia: destaca o que está na tela pública
                const live = onAir.length === 1 && onAir[0] === src.id;
                btn.classList.toggle('on-air', live);
                btn.title = live ? 'No ar agora' : sourceLabel(src);
            } else {
                btn.setAttribute('aria-pressed', String(splitPick[slot] === src.id));
            }
        });
    });

    const ready = splitPick.left && splitPick.right && splitPick.left !== splitPick.right;
    document.getElementById('split-send').disabled = !ready;
    document.getElementById('split-desc').textContent = ready
        ? `${sourceLabel(SOURCE_BY_ID[splitPick.left])} à esquerda, ${sourceLabel(SOURCE_BY_ID[splitPick.right])} à direita.`
        : (splitPick.left && splitPick.left === splitPick.right ? 'Escolha fontes diferentes para cada lado.' : 'Escolha os dois lados e envie.');
}

function setupSourcePicker() {
    renderSourceButtons();

    document.querySelectorAll('.sources').forEach(box => {
        box.addEventListener('click', e => {
            const btn = e.target.closest('.src-btn');
            if (!btn || btn.disabled) return;
            const src = SOURCE_BY_ID[btn.dataset.src];
            if (box.dataset.slot === 'a') {
                sendUrl(src.num);
            } else {
                splitPick[box.dataset.slot] = src.id;
                refreshSourceButtons();
            }
        });
    });

    document.getElementById('split-send').addEventListener('click', () => {
        if (!(splitPick.left && splitPick.right && splitPick.left !== splitPick.right)) return;
        showTwoUrls(SOURCE_BY_ID[splitPick.left].num, SOURCE_BY_ID[splitPick.right].num);
        if (window.ucToast) window.ucToast('Monitor de palco dividido.');
    });

    ['url1', 'url2', 'url3', 'name1', 'name2', 'name3'].forEach(id =>
        document.getElementById(id).addEventListener('input', refreshSourceButtons));
}

// Toda troca de tela (daqui, de outro PC via socket ou do estado salvo)
// passa por updateIframes — o destaque "no ar" acompanha a prévia.
const _origUpdateIframes = updateIframes;
updateIframes = function (url1, url2) {
    _origUpdateIframes(url1, url2);
    onAir = [sourceFromUrl(url1), url2 ? sourceFromUrl(url2) : null].filter(Boolean);
    if (url2 && onAir.length < 2) onAir = [];  // combinação que não reconhecemos: não destaca nada
    refreshSourceButtons();
};

// A prévia renderiza as telas em 1280×720 e reduz pra caber no card.
function setupPreviewScaling() {
    const wrap = document.getElementById('iframe-container-wrap');
    const stage = document.getElementById('preview-stage');
    if (!wrap || !stage) return;
    const fit = () => stage.style.setProperty('--preview-scale', wrap.clientWidth / 1280);
    fit();
    if (window.ResizeObserver) new ResizeObserver(fit).observe(wrap);
    else window.addEventListener('resize', fit);
}

function updateModePill() {
    const pill = document.getElementById('mode-pill');
    if (!pill) return;
    if (monitorOnlyMode) pill.innerHTML = '<span class="dot"></span>Só monitor';
    else if (publicOnlyMode) pill.innerHTML = '<span class="dot"></span>Só público';
    else pill.innerHTML = '<span class="dot"></span>Público e monitor';
}

// ── Painel ──────────────────────────────────────────────────────────────
// Páginas de comando (música, Bíblia, fotos) e ferramentas abertas ao lado
// do Controle, sem trocar de aba. As páginas carregam em iframe e escondem
// o próprio menu (html.uc-embed, ver _nav.html); cada uma é criada na
// primeira vez que a aba é aberta e fica viva ao trocar de aba (não perde
// a música ou o capítulo aberto). Estado (aberto, expandido, aba) fica
// salvo neste navegador.
const PANEL_PAGES = { musica: 'Música', biblia: 'Bíblia', fotos: 'Fotos', ordem: 'Ordem do culto' };
const PANEL_TOOLS = {
    timer: 'Cronômetro', ticker: 'Avisos', split: 'Monitor dividido',
    urls: 'URLs', share: 'Tela do PC', links: 'Abrir telas',
};
const panelState = { open: true, expanded: false, view: 'musica' };
const panelFrames = {};

function panelSave() {
    try { localStorage.setItem('uc-control-panel', JSON.stringify(panelState)); } catch (e) { /* sem storage */ }
}

function panelIsMobile() { return window.matchMedia('(max-width: 900px)').matches; }

function panelApply() {
    const ctl = document.getElementById('ctl');
    ctl.classList.toggle('panel-open', panelState.open);
    ctl.classList.toggle('panel-closed', !panelState.open);
    ctl.classList.toggle('panel-expanded', panelState.open && panelState.expanded && !panelIsMobile());
    document.body.classList.toggle('panel-sheet-open', panelState.open && panelIsMobile());
    const exp = document.getElementById('panel-expand');
    exp.title = panelState.expanded ? 'Recolher ao lado do Controle' : 'Expandir';
    exp.setAttribute('aria-label', exp.title);
    exp.querySelector('i').className = panelState.expanded ? 'fas fa-compress' : 'fas fa-expand';
    panelSave();
}

function panelFrameUrl(page) {
    if (page === 'biblia') return Promise.resolve('/bible');
    if (page === 'fotos') return Promise.resolve('/presenter');
    // Música: a que está (ou esteve por último) no telão, senão a 1ª do
    // próximo culto (/api/painel/musica)
    return fetch('/api/painel/musica').then(r => r.json()).then(d => {
        if (!d.song_id) return null;
        return `/lyrics/${d.song_id}` + (d.order_date ? `?order=${d.order_date}` : '');
    }).catch(() => null);
}

function panelOpenPage(page, url) {
    const pane = document.querySelector(`.panel-pane[data-pane="${page}"]`);
    if (!pane) return;
    const load = (src) => {
        if (!src) {
            pane.innerHTML = '<div class="panel-empty"><i class="fas fa-music"></i><p>Nenhuma música no próximo culto.</p>' +
                '<p class="uc-muted">Abra uma pela aba <b>Ordem do culto</b> ou pela lista de Músicas.</p></div>';
            return;
        }
        let frame = panelFrames[page];
        if (!frame) {
            pane.innerHTML = '';
            frame = document.createElement('iframe');
            frame.className = 'panel-frame';
            frame.title = PANEL_PAGES[page];
            frame.addEventListener('load', () => {
                // Página nova dentro do painel: herda o "sem conexão" atual
                try { frame.contentDocument.body.classList.toggle('uc-offline', !!window.__ucOffline); } catch (e) { /* outra origem */ }
            });
            pane.appendChild(frame);
            panelFrames[page] = frame;
        }
        if (src !== frame.getAttribute('src')) frame.setAttribute('src', src);
        // Mesmo src, mas a página saiu dela por um link: volta (o atributo
        // não muda quando o iframe navega sozinho)
        else if (!panelFrameNaPagina(page)) frame.contentWindow.location.replace(src);
    };
    if (url) load(url);
    else if (!panelFrames[page] || !panelFrameNaPagina(page)) panelFrameUrl(page).then(load);
}

// A página dentro da aba ainda é dela? (ex.: a aba Música foi parar numa
// página da Bíblia por um link) — senão clicar na aba volta pra página dela
const PANEL_PREFIX = { musica: '/lyrics/', biblia: '/bible', fotos: '/presenter' };
function panelFrameNaPagina(page) {
    const frame = panelFrames[page];
    try {
        return frame.contentWindow.location.pathname.startsWith(PANEL_PREFIX[page] || '/');
    } catch (e) { return true; /* outra origem: não mexe */ }
}

// url: abrir esta página na aba (ex.: música clicada na Ordem do culto)
// em vez da padrão
function panelShow(view, url) {
    panelState.view = view;
    const isPage = view in PANEL_PAGES;
    document.querySelectorAll('.panel-tab').forEach(t => t.setAttribute('aria-selected', String(t.dataset.page === view)));
    document.querySelectorAll('.panel-pane').forEach(p => {
        p.hidden = (p.dataset.pane || p.dataset.panel) !== view;
    });
    const title = document.getElementById('panel-tool-title');
    title.hidden = isPage;
    title.textContent = isPage ? '' : PANEL_TOOLS[view] || '';
    document.querySelectorAll('[data-open-tool], [data-open-page]').forEach(b =>
        b.classList.toggle('active', (b.dataset.openTool || b.dataset.openPage) === view));
    document.getElementById('panel-newtab').hidden = !isPage || view === 'ordem';
    if (view === 'ordem') panelLoadOrder();
    else if (isPage) panelOpenPage(view, url);
    panelSave();
}

function panelLoadOrder() {
    const list = document.getElementById('ordem-list');
    fetch('/api/culto/proximo').then(r => r.json()).then(d => {
        list.innerHTML = '';
        if (d.status === 'none' || !d.itens) {
            list.innerHTML = '<li class="ordem-empty">Nenhum culto com ordem cadastrada.</li>';
            return;
        }
        const when = d.date ? d.date.slice(0, 10).split('-').reverse().slice(0, 2).join('/') : '';
        const label = [d.tipo, when, d.horario].filter(Boolean).join(' · ');
        document.getElementById('ordem-title').textContent = 'Ordem do culto' + (label ? ` · ${label}` : '');
        if (!d.itens.length) {
            list.innerHTML = `<li class="ordem-empty">Esta ordem ainda não tem itens. <a href="/order/${d.date}" target="_blank" rel="noopener">Montar a ordem</a></li>`;
            return;
        }
        const KIND = { song: 'Música', bible: 'Bíblia', text: 'Momento' };
        d.itens.forEach((item, i) => {
            const li = document.createElement('li');
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'ordem-item kind-' + item.kind;
            btn.disabled = !item.url;
            btn.innerHTML = '<span class="n"></span><span class="t"></span><span class="k"></span>';
            btn.querySelector('.n').textContent = String(i + 1).padStart(2, '0');
            btn.querySelector('.t').textContent = item.title + (item.artist ? ` · ${item.artist}` : '');
            btn.querySelector('.k').textContent = KIND[item.kind] || '';
            btn.addEventListener('click', () => {
                if (item.kind === 'song') {
                    const url = item.url + (d.date ? (item.url.includes('?') ? '&' : '?') + `order=${d.date}` : '');
                    panelShow('musica', url);
                } else if (item.kind === 'bible') {
                    panelShow('biblia', item.url);
                }
            });
            li.appendChild(btn);
            list.appendChild(li);
        });
    }).catch(() => { list.innerHTML = '<li class="ordem-empty">Não deu pra carregar a ordem do culto.</li>'; });
}

function setupPanel() {
    try { Object.assign(panelState, JSON.parse(localStorage.getItem('uc-control-panel') || '{}')); } catch (e) { /* sem storage */ }
    if (!(panelState.view in PANEL_PAGES) && !(panelState.view in PANEL_TOOLS)) panelState.view = 'musica';
    // No celular o painel começa fechado (cobre a tela inteira)
    if (panelIsMobile()) panelState.open = false;

    document.querySelectorAll('.panel-tab').forEach(t => t.addEventListener('click', () => panelShow(t.dataset.page)));
    document.querySelectorAll('[data-open-tool]').forEach(b => b.addEventListener('click', () => {
        panelState.open = true;
        panelApply();
        panelShow(b.dataset.openTool);
    }));
    document.querySelectorAll('[data-open-page]').forEach(b => b.addEventListener('click', () => {
        panelState.open = true;
        panelApply();
        panelShow(b.dataset.openPage);
    }));
    document.getElementById('panel-close').addEventListener('click', () => { panelState.open = false; panelApply(); });
    document.getElementById('panel-back').addEventListener('click', () => { panelState.open = false; panelApply(); });
    document.getElementById('panel-reopen').addEventListener('click', () => { panelState.open = true; panelApply(); panelShow(panelState.view); });
    document.getElementById('panel-expand').addEventListener('click', () => { panelState.expanded = !panelState.expanded; panelApply(); });
    // "Abrir em nova aba": a página como está agora no painel
    document.getElementById('panel-newtab').addEventListener('click', (e) => {
        const frame = panelFrames[panelState.view];
        let href = frame && frame.getAttribute('src');
        try { href = frame.contentWindow.location.href; } catch (err) { /* usa o src */ }
        if (!href) { e.preventDefault(); return; }
        e.currentTarget.href = href;
    });
    window.addEventListener('resize', panelApply);

    // Setas (e pedal: PageUp/PageDown) com o foco no Controle passam a
    // música ou o versículo aberto no painel — sem precisar clicar dentro
    // dele antes. Repassa a tecla pra página do painel, que já sabe o que
    // fazer com ela (lyrics_2.js, bible_chapter.js; presenter.js passa o
    // PowerPoint animado que estiver no ar).
    document.addEventListener('keydown', (e) => {
        if (!['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'PageUp', 'PageDown'].includes(e.key)) return;
        if (e.target.closest('input, textarea, select, [contenteditable="true"]')) return;
        if (!panelState.open || !['musica', 'biblia', 'fotos'].includes(panelState.view)) return;
        const frame = panelFrames[panelState.view];
        let doc = null;
        try { doc = frame && frame.contentDocument; } catch (err) { /* outra origem */ }
        if (!doc || !doc.body) return;
        e.preventDefault();
        doc.body.dispatchEvent(new KeyboardEvent('keydown', { key: e.key, bubbles: true, cancelable: true }));
    });

    panelApply();
    if (panelState.open) panelShow(panelState.view);
}

