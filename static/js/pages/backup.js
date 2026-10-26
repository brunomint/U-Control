// Página /backup (ver blueprints/backup.py)
(function () {
    const $ = id => document.getElementById(id);
    const arquivo = $('backup-arquivo');
    const confirmo = $('backup-confirmo');
    const restaurar = $('backup-restaurar');
    const msg = $('backup-msg');
    const barra = $('backup-progress');

    function plural(n, um, varios) { return (n === 1 ? um : varios).replace('{n}', n); }
    function resumo(r) {
        return [plural(r.musicas, _t('{n} música'), _t('{n} músicas')), plural(r.ordens, _t('{n} ordem de culto'), _t('{n} ordens de culto')),
                plural(r.usuarios, _t('{n} usuário'), _t('{n} usuários')), plural(r.arquivos, _t('{n} foto, slide ou vídeo'), _t('{n} fotos, slides e vídeos'))].join(' · ');
    }

    fetch('/api/backup/resumo').then(r => r.json())
        .then(r => { $('backup-resumo').textContent = _t('Agora: {resumo}', { resumo: resumo(r) }); })
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
        msg.textContent = _t('Enviando o backup…');
        xhr.upload.onprogress = e => {
            if (!e.lengthComputable) return;
            const pct = Math.round(e.loaded / e.total * 100);
            barra.firstElementChild.style.width = pct + '%';
            msg.textContent = pct < 100 ? _t('Enviando o backup… {pct}%', { pct }) : _t('Restaurando… não feche esta página.');
        };
        xhr.onload = () => {
            let r = {};
            try { r = JSON.parse(xhr.responseText); } catch (e) { /* resposta sem JSON */ }
            if (xhr.status === 200 && r.ok) {
                const quando = r.backup && r.backup.criado ? new Date(r.backup.criado).toLocaleString(ucLocale()) : '';
                msg.innerHTML = (quando ? _t('<strong>Restaurado</strong> o backup de {quando}', { quando }) : _t('<strong>Restaurado</strong>'))
                    + `: ${resumo(r.resumo)}.
                    <br>` + _t('<a href="/login">Entrar de novo</a> com um usuário do backup.');
            } else {
                msg.textContent = r.error || (xhr.status === 413
                    ? _t('O arquivo é grande demais para o endereço da internet. Restaure pela rede da igreja (http://<ip>:8585).')
                    : _t('Não deu pra restaurar (erro {status}).', { status: xhr.status }));
                restaurar.disabled = false;
                arquivo.disabled = confirmo.disabled = false;
                barra.hidden = true;
            }
        };
        xhr.onerror = () => {
            msg.textContent = _t('A conexão caiu durante o envio. Nada foi trocado; tente de novo.');
            arquivo.disabled = confirmo.disabled = false;
            atualizarBotao();
            barra.hidden = true;
        };
        xhr.send(dados);
    });
})();
