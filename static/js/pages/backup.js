// Página /backup (ver blueprints/backup.py)
(function () {
    const $ = id => document.getElementById(id);
    const arquivo = $('backup-arquivo');
    const confirmo = $('backup-confirmo');
    const restaurar = $('backup-restaurar');
    const msg = $('backup-msg');
    const barra = $('backup-progress');

    function plural(n, um, varios) { return `${n} ${n === 1 ? um : varios}`; }
    function resumo(r) {
        return [plural(r.musicas, 'música', 'músicas'), plural(r.ordens, 'ordem de culto', 'ordens de culto'),
                plural(r.usuarios, 'usuário', 'usuários'), plural(r.arquivos, 'foto, slide ou vídeo', 'fotos, slides e vídeos')].join(' · ');
    }

    fetch('/api/backup/resumo').then(r => r.json())
        .then(r => { $('backup-resumo').textContent = 'Agora: ' + resumo(r); })
        .catch(() => {});

    // O download é um link comum (o navegador mostra o progresso); só avisa
    // que pode demorar, porque o servidor monta o .zip antes de mandar
    $('backup-baixar').addEventListener('click', () => {
        $('backup-baixando').hidden = false;
        setTimeout(() => { $('backup-baixando').hidden = true; }, 60000);
    });

    function atualizarBotao() {
        restaurar.disabled = !(arquivo.files.length && confirmo.checked);
    }
    arquivo.addEventListener('change', atualizarBotao);
    confirmo.addEventListener('change', atualizarBotao);

    restaurar.addEventListener('click', () => {
        const dados = new FormData();
        dados.append('arquivo', arquivo.files[0]);
        // XMLHttpRequest e não fetch: mostra o progresso do envio (backup com
        // fotos passa fácil de 100 MB)
        const xhr = new XMLHttpRequest();
        xhr.open('POST', '/api/backup/restaurar');
        const token = document.querySelector('meta[name="csrf-token"]');
        if (token) xhr.setRequestHeader('X-CSRFToken', token.content);
        restaurar.disabled = arquivo.disabled = confirmo.disabled = true;
        barra.hidden = false;
        msg.textContent = 'Enviando o backup…';
        xhr.upload.onprogress = e => {
            if (!e.lengthComputable) return;
            const pct = Math.round(e.loaded / e.total * 100);
            barra.firstElementChild.style.width = pct + '%';
            msg.textContent = pct < 100 ? `Enviando o backup… ${pct}%` : 'Restaurando… não feche esta página.';
        };
        xhr.onload = () => {
            let r = {};
            try { r = JSON.parse(xhr.responseText); } catch (e) { /* resposta sem JSON */ }
            if (xhr.status === 200 && r.ok) {
                const quando = r.backup && r.backup.criado ? new Date(r.backup.criado).toLocaleString('pt-BR') : '';
                msg.innerHTML = `<strong>Restaurado</strong>${quando ? ' o backup de ' + quando : ''}: ${resumo(r.resumo)}.
                    <br><a href="/login">Entrar de novo</a> com um usuário do backup.`;
            } else {
                msg.textContent = r.error || (xhr.status === 413
                    ? 'O arquivo é grande demais para o endereço da internet. Restaure pela rede da igreja (http://<ip>:8585).'
                    : `Não deu pra restaurar (erro ${xhr.status}).`);
                restaurar.disabled = false;
                arquivo.disabled = confirmo.disabled = false;
                barra.hidden = true;
            }
        };
        xhr.onerror = () => {
            msg.textContent = 'A conexão caiu durante o envio. Nada foi trocado; tente de novo.';
            arquivo.disabled = confirmo.disabled = false;
            atualizarBotao();
            barra.hidden = true;
        };
        xhr.send(dados);
    });
})();
