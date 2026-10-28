// Vídeo do telão sempre no mesmo ponto em todas as telas (telão público,
// /monitor, /img). O servidor só guarda um relógio do vídeo (/video_state);
// cada tela toca o próprio arquivo. Uma tela que demora pra abrir (celular
// Android num vídeo grande) começava atrasada e ficava atrasada pra
// sempre. Agora ela se acerta: quando o vídeo começa a andar e depois a
// cada INTERVALO, compara com o relógio e, se passou de LIMITE, pula pro
// ponto certo. Só confere — nunca manda ordem pras outras telas.
window.ucVideoSync = function (video) {
    const LIMITE = 0.5;        // segundos de diferença tolerados
    const INTERVALO = 10000;   // ms entre conferências
    let ocupado = false;
    let ultimaCorrecao = 0;
    // Pular também demora (baixar aquele trecho): se depois de um pulo ainda
    // está atrás, o próximo mira mais à frente — aprende o atraso do aparelho
    let adiantamento = 0.3;
    let corrigiu = false;

    const mesmoArquivo = (a, b) => {
        try { return new URL(a, location.href).pathname === new URL(b, location.href).pathname; }
        catch (e) { return false; }
    };

    async function conferir() {
        if (ocupado || video.paused || !video.currentSrc || video.readyState < 2) return;
        ocupado = true;
        try {
            const t0 = performance.now();
            const s = await (await fetch('/video_state', { cache: 'no-store' })).json();
            const meiaVolta = (performance.now() - t0) / 2000;   // s
            // Vídeo de fundo do tema, outro vídeo, pausado no servidor: não é com ela
            if (!s.url || s.paused || !mesmoArquivo(s.url, video.currentSrc)) return;
            const esperado = s.position + meiaVolta;
            if (video.duration && esperado >= video.duration - 1) return;
            const diferenca = esperado - video.currentTime;
            if (corrigiu && Math.abs(diferenca) > LIMITE) {
                // Ainda atrás: mira mais à frente; passou do ponto: mira menos
                adiantamento = Math.max(0, Math.min(adiantamento + diferenca, 8));
            }
            corrigiu = false;
            if (Math.abs(diferenca) > LIMITE && Date.now() - ultimaCorrecao > 3000) {
                ultimaCorrecao = Date.now();
                corrigiu = true;
                // Atrasada: mira à frente pelo que o pulo costuma levar
                video.currentTime = esperado + (diferenca > 0 ? adiantamento : 0);
            }
        } catch (e) { /* rede: confere de novo depois */ }
        finally { ocupado = false; }
    }

    // Começou a andar (abriu, voltou de pausa, terminou de carregar um pulo)
    video.addEventListener('playing', () => setTimeout(conferir, 300));
    setInterval(conferir, INTERVALO);
};
