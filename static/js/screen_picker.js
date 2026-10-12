// "Abrir no datashow" do Controle: escolhe em qual tela do PC (ex.: a do
// datashow) a tela pública ou o retorno de palco abre, como o Holyrics.
//
// Com a Window Management API (Chrome/Edge, página https ou localhost) a
// lista mostra as telas de verdade e abre a janela já nelas. Sem ela
// (U-Control aberto pelo IP, http) dá pra escolher "tela à direita/à
// esquerda" e baixar o atalho — o script abre o Chrome em tela cheia
// naquela posição (blueprints/utils.py, download_monitor_launcher).
// A escolha fica guardada neste PC (localStorage).
(function () {
    const modal = document.getElementById('modal-datashow');
    if (!modal) return;
    const list = document.getElementById('datashowList');
    const aviso = document.getElementById('datashowAviso');
    const baixar = document.getElementById('datashowBaixar');
    const cheiaBtn = document.getElementById('datashowCheia');
    let janela = null;      // janela aberta por abrirAgora
    const TELAS = { publico: '/lyrics/display/public', palco: '/monitor' };
    const KEY = 'uc_datashow';
    let tela = 'publico';
    let escolhida = null;   // { left, top, width, height, label }

    const ler = () => { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) { return {}; } };
    const gravar = (v) => { try { localStorage.setItem(KEY, JSON.stringify(v)); } catch (e) { /* sem storage: só não lembra */ } };
    const mesma = (a, b) => a && b && a.left === b.left && a.top === b.top && a.width === b.width && a.height === b.height;

    function escolher(s) {
        escolhida = s;
        const salvo = ler();
        salvo[tela] = s;
        gravar(salvo);
        list.querySelectorAll('[data-i]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.i === String(s.i))));
        baixar.disabled = false;
    }

    // s.abre: dá pra abrir a janela já nessa tela (com a lista de telas
    // do navegador; sem ela, só "Esta tela")
    function render(opcoes) {
        const salvo = ler()[tela];
        list.innerHTML = '';
        opcoes.forEach((s, i) => {
            s.i = i;
            const b = document.createElement('button');
            b.type = 'button';
            b.className = 'datashow-opcao';
            b.dataset.i = i;
            b.innerHTML = `<i class="fas ${s.icon}"></i><span class="grow"><b></b><small></small></span>` +
                (s.abre ? '<span class="uc-pill uc-pill-muted">Abrir</span>' : '');
            b.querySelector('b').textContent = s.label;
            b.querySelector('small').textContent = s.detalhe;
            b.addEventListener('click', () => {
                escolher(s);
                if (s.abre) abrirAgora(s);
            });
            list.appendChild(b);
            if (mesma(s, salvo)) escolher(s);
        });
    }

    function abrirAgora(s) {
        const feat = `popup,fullscreen,left=${s.left},top=${s.top},width=${s.width},height=${s.height}`;
        janela = window.open(`${TELAS[tela]}?tela_cheia=1`, `uc_${tela}`, feat);
        if (!janela) {
            aviso.textContent = 'O navegador bloqueou a janela. Libere pop-ups para este endereço e tente de novo.';
            return;
        }
        // Abrir a janela gasta o clique; a tela cheia precisa de outro, aqui
        // no Controle mesmo (o navegador empresta o clique pra janela —
        // postMessage com delegate, ver tela_cheia.js). Liga quando ela carregar.
        cheiaBtn.hidden = false;
        cheiaBtn.disabled = true;
        aviso.textContent = `Abrindo em ${s.label}…`;
    }

    window.addEventListener('message', e => {
        if (e.origin !== location.origin || !e.data || e.source !== janela) return;
        if (e.data.uc === 'tela_pronta') {
            cheiaBtn.disabled = false;
            aviso.textContent = 'Janela aberta. Agora toque em "Pôr em tela cheia".';
        } else if (e.data.uc === 'tela_cheia_ok') {
            cheiaBtn.hidden = true;
            aviso.textContent = '';
            ucToast('Tela pública em tela cheia.');
            fecharDatashow();
        } else if (e.data.uc === 'tela_cheia_falhou') {
            aviso.textContent = 'O navegador não deixou pôr em tela cheia daqui. Clique uma vez na janela da tela pública (ou aperte F11 nela).';
        }
    });

    cheiaBtn.addEventListener('click', () => {
        if (!janela || janela.closed) { cheiaBtn.hidden = true; return; }
        try {
            janela.postMessage({ uc: 'tela_cheia' }, { targetOrigin: location.origin, delegate: 'fullscreen' });
        } catch (e) {
            janela.postMessage({ uc: 'tela_cheia' }, location.origin);  // navegador sem delegação: a janela tenta e avisa
        }
    });

    async function carregar() {
        aviso.textContent = '';
        cheiaBtn.hidden = true;
        escolhida = null;
        baixar.disabled = true;
        if ('getScreenDetails' in window && window.isSecureContext) {
            try {
                list.innerHTML = '';
                aviso.textContent = 'Permita "gerenciar janelas" no aviso do navegador, perto da barra de endereço (só na primeira vez).';
                const det = await window.getScreenDetails();
                aviso.textContent = '';
                const opcoes = det.screens.map((sc, i) => ({
                    left: sc.availLeft, top: sc.availTop, width: sc.availWidth, height: sc.availHeight,
                    label: `Tela ${i + 1}${sc.isPrimary ? ' · principal' : ''}`,
                    detalhe: `${sc.width}×${sc.height}${sc.label ? ' · ' + sc.label : ''}`,
                    icon: sc.isPrimary ? 'fa-laptop' : 'fa-display', abre: true,
                }));
                render(opcoes);
                if (opcoes.length === 1) aviso.textContent = 'Só uma tela ligada neste PC. Ligue o datashow (modo "Estender") e abra de novo.';
                return;
            } catch (e) {
                aviso.textContent = 'Sem permissão para ver as telas. Clique no cadeado da barra de endereço e permita "Gerenciamento de janelas".';
            }
        } else {
            aviso.textContent = window.isSecureContext
                ? 'Este navegador não lista as telas (só Chrome e Edge). Escolha a posição e baixe o atalho.'
                : 'Pelo IP da rede o navegador não deixa listar as telas. Escolha onde está o datashow e baixe o atalho: ele abre direto em tela cheia lá.';
        }
        // Sem a API: posição relativa à tela deste PC
        const w = window.screen.width, h = window.screen.height;
        render([
            { left: w + 50, top: 50, width: 0, height: 0, label: 'Tela à direita', detalhe: 'Datashow à direita desta tela (o mais comum)', icon: 'fa-arrow-right' },
            { left: -200, top: 50, width: 0, height: 0, label: 'Tela à esquerda', detalhe: 'Datashow à esquerda desta tela', icon: 'fa-arrow-left' },
            { left: window.screen.availLeft || 0, top: window.screen.availTop || 0, width: window.screen.availWidth, height: window.screen.availHeight,
              label: 'Esta tela', detalhe: `${w}×${h}`, icon: 'fa-laptop', abre: true },
        ]);
    }

    modal.querySelectorAll('[data-tela]').forEach(b => b.addEventListener('click', () => {
        tela = b.dataset.tela;
        modal.querySelectorAll('[data-tela]').forEach(o => o.setAttribute('aria-pressed', String(o === b)));
        carregar();
    }));

    baixar.addEventListener('click', () => {
        if (!escolhida) return;
        location.href = `/download-monitor-launcher/windows?tela=${tela}&x=${escolhida.left + 10}&y=${escolhida.top + 10}`;
    });

    window.abrirDatashow = function () {
        modal.style.display = 'flex';
        carregar();
    };
    window.fecharDatashow = function () { modal.style.display = 'none'; };
})();
