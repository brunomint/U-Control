// Página /atualizacao (ver updates.py): o que há de novo e como atualizar
// cada tipo de instalação. "Agora não" esconde o selo da barra até a
// próxima versão (mesma chave que o _nav.html lê).
(function () {
    const $ = id => document.getElementById(id);
    const COMO = {
        servidor: `<p><strong>Raspberry Pi / Linux:</strong> na pasta do U-Control, rode <code>git pull</code> e reinicie o serviço
            (quem atualiza pelo <code>scripts/deploy.py</code>, rode ele no computador de sempre).</p>`,
        docker: `<p><strong>Docker:</strong> na pasta do U-Control, rode <code>git pull</code> e <code>docker compose up -d --build</code>.</p>`,
        windows_remoto: `<p>Para instalar, use o <strong>computador onde o U-Control está rodando</strong>: abra esta página nele
            (menu da bandeja → Abrir Controle → Sistema → Atualização). Instalar fecha o programa por alguns segundos.</p>`,
    };
    let acompanhando = null;

    function botao(texto, classe, acao) {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'uc-btn ' + classe;
        b.innerHTML = texto;
        b.addEventListener('click', acao);
        $('upd-actions').appendChild(b);
        return b;
    }

    function mostrarInstalacao(inst) {
        const barra = $('upd-progress');
        if (inst.estado === 'baixando') {
            barra.hidden = false;
            barra.firstElementChild.style.width = inst.progresso + '%';
            $('upd-msg').textContent = `Baixando… ${inst.progresso}%`;
        } else if (inst.estado === 'instalando') {
            barra.hidden = false;
            barra.firstElementChild.style.width = '100%';
            $('upd-msg').textContent = 'Instalando. O Windows vai pedir permissão; o U-Control fecha e abre de novo sozinho.';
        } else if (inst.estado === 'erro') {
            barra.hidden = true;
            $('upd-msg').textContent = 'Não deu pra baixar: ' + inst.erro;
        }
        // continua acompanhando enquanto instala: é assim que a página
        // percebe o U-Control fechar e abrir de novo
        return inst.estado === 'baixando' || inst.estado === 'instalando';
    }

    async function carregar() {
        let s;
        try {
            s = await (await fetch('/api/update-status')).json();
        } catch (e) {
            $('upd-sub').textContent = 'Sem conexão com o U-Control.';
            return;
        }
        $('upd-sub').textContent = `Versão instalada: ${s.current}`;
        $('upd-card').hidden = false;
        $('upd-actions').innerHTML = '';
        if (!s.checked && s.checking) {
            // consulta ao GitHub ainda em andamento (servidor acabou de ligar)
            $('upd-title').textContent = 'Consultando o GitHub…';
            setTimeout(carregar, 2000);
            return;
        }
        if (!s.checked) {
            $('upd-title').textContent = 'Não foi possível consultar se há versão nova';
            $('upd-how').innerHTML = '<p class="uc-muted">Sem internet neste computador, ou o GitHub não respondeu. Tente de novo mais tarde.</p>';
            return;
        }
        if (!s.available) {
            $('upd-title').textContent = 'Você está na versão mais recente';
            return;
        }
        $('upd-title').textContent = `Nova versão ${s.latest} disponível`;
        if (s.notes) { $('upd-notes').textContent = s.notes; $('upd-notes').hidden = false; }

        if (s.can_install) {
            const b = botao('<i class="fas fa-download"></i> Baixar e instalar', 'uc-btn-primary', async () => {
                b.disabled = true;
                const r = await fetch('/api/update/install', { method: 'POST' });
                const dados = await r.json().catch(() => ({}));
                if (!r.ok) { $('upd-msg').textContent = dados.error || 'Não deu pra começar.'; b.disabled = false; return; }
                acompanhar();
            });
            if (mostrarInstalacao(s.install)) { b.disabled = true; acompanhar(); }
        } else {
            $('upd-how').innerHTML = COMO[s.kind === 'windows' ? 'windows_remoto' : s.kind] || '';
        }
        if (s.release_url) {
            const a = document.createElement('a');
            a.className = 'uc-btn uc-btn-secondary';
            a.href = s.release_url; a.target = '_blank'; a.rel = 'noopener';
            a.innerHTML = '<i class="fas fa-up-right-from-square"></i> Ver no GitHub';
            $('upd-actions').appendChild(a);
        }
        botao('Agora não', 'uc-btn-ghost', () => {
            try { localStorage.setItem('uc_update_dispensada', s.latest); } catch (e) { /* sem storage */ }
            location.href = '/dashboard';
        });
    }

    function acompanhar() {
        clearInterval(acompanhando);
        acompanhando = setInterval(async () => {
            try {
                const s = await (await fetch('/api/update-status')).json();
                if (!mostrarInstalacao(s.install)) clearInterval(acompanhando);
            } catch (e) {
                // servidor caiu = o instalador fechou o U-Control: vai voltar sozinho
                $('upd-msg').textContent = 'O U-Control fechou para instalar. Esta página volta quando ele abrir de novo.';
                clearInterval(acompanhando);
                esperarVoltar();
            }
        }, 1000);
    }

    function esperarVoltar() {
        setTimeout(async () => {
            try { await fetch('/api/update-status'); location.reload(); } catch (e) { esperarVoltar(); }
        }, 3000);
    }

    carregar();
})();
