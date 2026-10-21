// "Tela do PC" (WebRTC), lado de quem assiste: tela pública, retorno de
// palco e /tela-do-pc (fonte do monitor dividido). Antes era uma cópia em
// cada página; ver blueprints/screen_share.py pro lado do servidor.
//
//   ucScreenShareViewer(socket, video, { role: 'public' | 'monitor' | 'any', onChange })
//
// - Apresenta-se ao servidor a cada (re)conexão: tela que abre ou volta no
//   meio de um compartilhamento recebe sozinha.
// - Conexão que falha tenta de novo; o vídeo sem som liberado toca mudo em
//   vez de ficar preto.
// - Dentro de iframe (prévia do Controle, metade do monitor dividido) não
//   assiste: cada tela assistindo é mais um vídeo que o PC do operador
//   codifica, e a tela de fora já mostra. Exceção: /tela-do-pc (role
//   'any'), que existe justamente pra ser uma metade do monitor dividido.
window.ucScreenShareViewer = function (socket, video, opts) {
    opts = opts || {};
    const role = opts.role || 'public';
    const onChange = opts.onChange || function () {};
    if (window.top !== window.self && role !== 'any') return;

    const ICE = { iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] };
    let pc = null;
    let de = null;
    let tentativa = null;
    // ICE que chega antes do setRemoteDescription terminar era descartado
    // (addIceCandidate falha) e a conexão às vezes não fechava
    let pendentes = [];

    function mostrar(ligado) {
        video.style.display = ligado ? 'block' : 'none';
        if (!ligado) video.srcObject = null;
        onChange(ligado);
    }
    function fechar() {
        if (!pc) return;
        pc.onconnectionstatechange = null;
        pc.close();
        pc = null;
    }
    function pedir(sid) {
        de = sid;
        socket.emit('screen_share_request', { broadcaster_sid: sid });
    }
    function tocar() {
        const p = video.play();
        if (p && p.catch) p.catch(function () { video.muted = true; video.play().catch(function () {}); });
    }

    socket.on('connect', function () { socket.emit('screen_share_hello', { role: role }); });
    if (socket.connected) socket.emit('screen_share_hello', { role: role });

    socket.on('screen_share_start', function (data) {
        // Controle que reconectou anuncia de novo: se o vídeo está passando, segue
        if (pc && (pc.connectionState === 'connected' || pc.connectionState === 'connecting')) return;
        clearTimeout(tentativa);
        pedir(data.from_sid);
    });

    socket.on('screen_share_offer', async function (data) {
        fechar();
        de = data.from_sid;
        pendentes = [];
        const conexao = pc = new RTCPeerConnection(ICE);
        conexao.onicecandidate = function (e) {
            if (e.candidate) socket.emit('screen_share_ice', { target_sid: data.from_sid, candidate: e.candidate });
        };
        conexao.ontrack = function (e) {
            video.srcObject = e.streams[0];
            mostrar(true);
            tocar();
        };
        conexao.onconnectionstatechange = function () {
            if (conexao.connectionState !== 'failed') return;
            fechar();
            mostrar(false);
            clearTimeout(tentativa);
            tentativa = setTimeout(function () { if (de) pedir(de); }, 3000);
        };
        await conexao.setRemoteDescription(new RTCSessionDescription(data.sdp));
        pendentes.splice(0).forEach(function (c) { conexao.addIceCandidate(c).catch(function () {}); });
        const answer = await conexao.createAnswer();
        await conexao.setLocalDescription(answer);
        socket.emit('screen_share_answer', { target_sid: data.from_sid, sdp: answer });
    });

    socket.on('screen_share_ice', function (data) {
        if (!pc || data.from_sid !== de) return;
        const c = new RTCIceCandidate(data.candidate);
        if (pc.remoteDescription) pc.addIceCandidate(c).catch(function () {});
        else pendentes.push(c);
    });

    socket.on('screen_share_stop', function () {
        clearTimeout(tentativa);
        de = null;
        fechar();
        mostrar(false);
    });
};
