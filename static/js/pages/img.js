const socket = io.connect(window.location.protocol + '//' + window.location.host);
let currentImageUrl = ''; // Armazena URL atual para evitar recargas desnecessárias

document.getElementById('videoEl').addEventListener('ended', function() {
    socket.emit('video_ended', {});
});
let blackoutActive = false;

// Se /img está dentro de iframe (ex: home/control.html), fica mudo para
// evitar áudio duplicado com a janela principal do telão.
const isInsideIframe = (window.self !== window.top);

function playVideo(url, opts) {
    opts = opts || {};
    const startAt = Number(opts.startAt) || 0;
    const startPaused = !!opts.paused;
    const vid = document.getElementById('videoEl');
    showVideo();
    vid.src = url;
    vid.muted = isInsideIframe;

    // Modo "carregar pausado": faz play+pause como warm-up para destravar
    // o autoplay (permite que comandos play vindos por socket toquem com som).
    // NÃO seta muted=true se falhar (causava som permanentemente desligado).
    if (startPaused) {
        vid.preload = 'auto';
        vid.addEventListener('loadedmetadata', () => {
            try { vid.currentTime = startAt || 0; } catch (_) {}
            vid.play().then(() => {
                vid.pause();
                console.log('⏸️ Vídeo carregado pausado, autoplay destravado.');
            }).catch(e => {
                console.warn('Autoplay bloqueado no warm-up (ok, video paused):', e && e.message);
            });
        }, { once: true });
        vid.load();
        if (blackoutActive) vid.style.opacity = '0';
        return;
    }

    // Modo normal: toca imediatamente (com seek se necessário)
    const seekAndPlay = () => {
        if (startAt > 0) {
            try { vid.currentTime = startAt; } catch (_) {}
        }
        vid.play().then(() => {
            console.log(isInsideIframe ? '🔇 Vídeo (iframe) mudo @' : '🎬 Vídeo tocando com som @', startAt.toFixed(2) + 's:', url);
        }).catch(e => {
            console.warn('Autoplay com som bloqueado, tentando mutado:', e);
            vid.muted = true;
            vid.play().catch(err => console.error('Falha total no autoplay:', err));
        });
    };

    if (startAt > 0) {
        vid.addEventListener('loadedmetadata', seekAndPlay, { once: true });
        vid.load();
    } else {
        vid.load();
        seekAndPlay();
    }

    if (blackoutActive) vid.style.opacity = '0';
}

socket.on('connect', function() {
    console.log('✅ Socket conectado:', socket.id);
    // Dentro do /monitor (host=monitor, ver noMonitor em monitor.js) é o
    // monitor: em "Só público" não muda junto com o telão
    socket.emit('identify', { role: new URLSearchParams(location.search).get('host') === 'monitor' ? 'monitor' : 'public' });
});
socket.on('disconnect', function() {
    console.warn('❌ Socket desconectado');
});

function showImage() {
    document.getElementById('imageUr').style.display = '';
    const vid = document.getElementById('videoEl');
    vid.pause();
    vid.style.display = 'none';
}

function showVideo() {
    document.getElementById('imageUr').style.display = 'none';
    document.getElementById('videoEl').style.display = '';
}

// Função para carregar a última mídia ao carregar a página
function loadLastImage() {
    // Primeiro verifica se há um vídeo ativo no servidor
    fetch('/video_state')
        .then(r => r.json())
        .then(state => {
            if (state.url) {
                // Retoma o vídeo na posição correta
                console.log('🎬 /img: Retomando vídeo em', state.position.toFixed(2) + 's:', state.url);
                playVideo(state.url, { startAt: state.position, paused: state.paused });
            } else {
                // Sem vídeo ativo — carrega última imagem
                _loadLastImageFallback();
            }
        })
        .catch(() => _loadLastImageFallback());
}

function _loadLastImageFallback() {
    fetch('/last_image')
        .then(response => response.json())
        .then(data => {
            if (!data.image_url) return;
            // Ignora URLs internas (rotas como /img, /clock) — só processa arquivos reais
            const url = data.image_url;
            const isStaticFile = url.startsWith('/static/') ||
                                 /\.(jpe?g|png|gif|bmp|webp|mp4|webm|mov)(\?.*)?$/i.test(url);
            if (!isStaticFile) {
                console.log('ℹ️ /last_image retornou rota interna, ignorando:', url);
                return;
            }
            // Detecta vídeo pela extensão se media_type não disser
            const isVideoByExt = /\.(mp4|webm|mov)(\?.*)?$/i.test(data.image_url);
            if (data.media_type === 'video' || isVideoByExt) {
                // Sempre carrega pausado no primeiro frame.
                // Para tocar, o operador precisa apertar play no / ou /presenter.
                playVideo(data.image_url, { paused: true });
                // Sincroniza o servidor APENAS se este /img é o telão (não iframe preview).
                // Caso contrário, cada reload do preview re-pausava o telão real.
                if (!isInsideIframe) {
                    socket.emit('toggle_video_pause', { paused: true });
                    socket.emit('seek_video', { time: 0 });
                }
            } else {
                loadImage(data.image_url, data.zoom);
            }
        })
        .catch(error => console.error('Erro ao carregar a última mídia:', error));
}

// Função otimizada para carregar imagem (usa cache quando possível)
function loadImage(imageUrl, zoom) {
    const img = document.getElementById('imageUr');

    if (currentImageUrl === imageUrl) {
        console.log('🚀 Imagem já carregada, usando cache');
        return;
    }

    const finalUrl = imageUrl.startsWith('/static/')
        ? imageUrl + '?t=' + Date.now()
        : imageUrl;

    const tempImg = new Image();
    tempImg.onload = function() {
        showImage();
        img.src = finalUrl;
        currentImageUrl = imageUrl;
        if (window.ucZoomOnShow) window.ucZoomOnShow(img, zoom);
        if (!blackoutActive) img.style.opacity = '1';
        console.log('✅ Imagem carregada:', imageUrl);
    };
    tempImg.onerror = function() {
        console.error('❌ Erro ao carregar a imagem:', imageUrl);
    };
    tempImg.src = finalUrl;
}

// Executa a função assim que a página for carregada
document.addEventListener("DOMContentLoaded", loadLastImage);

// Pré-carrega a próxima foto do slideshow em cache do navegador, antes da
// troca de verdade — ver preload_image em control.js/blueprints/display.py.
socket.on('preload_image', function(data) {
    if (data.url) { new Image().src = data.url; }
});

// WebSocket para receber imagens em tempo real
socket.on('display_image', function(data) {
    // Ignora URLs que não são arquivos (ex: '/img', '/clock', '/lyrics/display').
    // Essas são rotas internas usadas pelo painel para iframes, não imagens.
    const url = data.image_url || '';
    const isStaticFile = url.startsWith('/static/') || /\.(jpe?g|png|gif|bmp|webp)(\?.*)?$/i.test(url);
    if (!isStaticFile) return;
    // Vídeo liberado como "foto" (preparar/liberar da galeria): carrega
    // pausado no 1º quadro, como na abertura da página (loadLastImage)
    if (/\.(mp4|webm|mov)(\?.*)?$/i.test(url)) { playVideo(url, { paused: true }); currentImageUrl = null; return; }
    if (currentImageUrl !== url) {
        loadImage(url, data.zoom);
        const img = document.getElementById('imageUr');
        img.style.transform = 'scale(1)';
        img.style.transformOrigin = '50% 50%';
    }
});

// WebSocket para receber vídeos em tempo real
socket.on('display_video', function(data) {
    playVideo(data.video_url);
});

// WebSocket para seek no vídeo (ir para tempo específico)
socket.on('video_seek', function(data) {
    const vid = document.getElementById('videoEl');
    if (!vid.src) return;
    const t = Number(data.time) || 0;
    try { vid.currentTime = t; } catch (_) {}
    console.log('⏩ Seek para', t.toFixed(2) + 's');
});

// WebSocket para reiniciar o vídeo atual
socket.on('video_restart', function() {
    const vid = document.getElementById('videoEl');
    if (!vid.src) return;
    vid.currentTime = 0;
    vid.play().catch(e => console.warn('Erro ao reiniciar vídeo:', e));
    console.log('⏮️ Vídeo reiniciado');
});

// WebSocket para pausar/retomar o vídeo atual
socket.on('video_pause', function(data) {
    const vid = document.getElementById('videoEl');
    if (!vid.src) return;
    if (data.paused) {
        vid.pause();
        console.log('⏸️ Vídeo pausado');
    } else {
        vid.play().catch(e => console.warn('Erro ao retomar:', e));
        console.log('▶️ Vídeo retomado');
    }
});

// Tela dividida (show_two_urls): para vídeo se estiver tocando
socket.on('display_two_urls', function() {
    const vid = document.getElementById('videoEl');
    if (vid.src) {
        vid.pause();
        vid.removeAttribute('src');
        vid.load();
        vid.style.display = 'none';
        document.getElementById('imageUr').style.display = '';
    }
});

// Tela preta/branca/logo (static/js/camada_neutra.js) — só aberta direto
// no datashow. Dentro de outra tela (iframe do telão ou do /monitor), a
// camada é a dela; antes o /img apagava sozinho e o /monitor ficava preto
// junto com o público.
if (!isInsideIframe) ucCamadaNeutra(socket, new URLSearchParams(location.search).get('host') === 'monitor' ? 'monitor' : 'public');

// Zoom do /presenter: translate(pan%) scale(zoom), origem no centro —
// a mesma transformação que o modal de zoom aplica na prévia. Só vale
// pra foto que está na tela: zoom de outra foto é ignorado (não troca
// a foto, pra não furar o Preparar/Liberar).
socket.on('display_image_zoom', function(data) {
    if (!data || currentImageUrl !== data.image_url) return;
    window.ucApplyZoom(document.getElementById('imageUr'), data);  // static/js/zoom_fit.js
});
