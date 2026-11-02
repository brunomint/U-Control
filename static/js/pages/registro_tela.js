// Registro da tela (registro_tela.html): toca o áudio do culto ao lado do que
// passou no telão e mede o atraso entre os dois. O MP3 é aberto direto do
// computador; nada do áudio vai para o servidor.
(function () {
    const CHAVE_MEDICOES = 'registroTelaMedicoes';
    const VOLTA_AO_PULAR = 4;   // segundos antes da troca, pra dar tempo de ouvir

    const $ = (id) => document.getElementById(id);
    const audio = $('rt-audio');
    const campoInicio = $('rt-inicio');
    const campoAtraso = $('rt-atraso');

    let eventos = [];
    let inicioMs = null;
    let medicoes = lerMedicoes();
    let nomeArquivo = '';
    let urlAudio = null;
    let linhaAtual = -1;

    function lerMedicoes() {
        try {
            return JSON.parse(localStorage.getItem(CHAVE_MEDICOES)) || {};
        } catch (e) {
            return {};
        }
    }

    function salvarMedicoes() {
        try {
            localStorage.setItem(CHAVE_MEDICOES, JSON.stringify(medicoes));
        } catch (e) { /* sem armazenamento: vale até fechar a página */ }
    }

    function doisDigitos(n) {
        return String(n).padStart(2, '0');
    }

    function tempoAudio(segundos) {
        const s = Math.max(0, Math.round(segundos));
        const h = Math.floor(s / 3600);
        const m = doisDigitos(Math.floor(s / 60) % 60);
        return (h ? h + ':' : '') + m + ':' + doisDigitos(s % 60);
    }

    function horaDoDia(ms) {
        const d = new Date(ms);
        return [d.getHours(), d.getMinutes(), d.getSeconds()].map(doisDigitos).join(':');
    }

    function paraCampoData(data) {
        return `${data.getFullYear()}-${doisDigitos(data.getMonth() + 1)}-${doisDigitos(data.getDate())}`;
    }

    function atraso() {
        return Number(campoAtraso.value);
    }

    function segundosNoAudio(evento) {
        return (evento.ts - inicioMs) / 1000 + atraso();
    }

    function descrever(evento) {
        switch (evento.tipo) {
            case 'letra': return { titulo: evento.titulo, texto: evento.texto };
            case 'biblia': return { titulo: evento.titulo || _t('Bíblia'), texto: evento.texto };
            case 'avisos': return { titulo: _t('Avisos'), texto: evento.texto };
            case 'video': return {
                titulo: _t('Exibição de vídeo'),
                texto: evento.titulo ? `${_t('Neste momento houve a exibição de um vídeo')}: ${evento.titulo}`
                                     : _t('Neste momento houve a exibição de um vídeo'),
            };
            case 'foto': return { titulo: _t('Imagem'), texto: evento.titulo };
            case 'neutra': return { titulo: _t('Tela neutra'), texto: evento.titulo };
            case 'oculto': return { titulo: _t('Texto escondido'), texto: evento.titulo };
            case 'vazio': return { titulo: _t('Tela vazia'), texto: '' };
            default: return { titulo: _t('Outra tela'), texto: evento.titulo };
        }
    }

    function mostrarNaTela(evento) {
        const d = evento ? descrever(evento) : { titulo: '', texto: '' };
        $('rt-tela-titulo').textContent = d.titulo;
        $('rt-tela-texto').textContent = d.texto;
    }

    function indiceNoTempo(segundos) {
        if (inicioMs === null) return -1;
        let achado = -1;
        for (let i = 0; i < eventos.length && segundosNoAudio(eventos[i]) <= segundos; i++) achado = i;
        return achado;
    }

    function atualizarTela() {
        const i = indiceNoTempo(audio.currentTime);
        if (i === linhaAtual) return;
        linhaAtual = i;
        mostrarNaTela(eventos[i]);
        $('rt-eventos').querySelectorAll('.rt-evento').forEach((linha, n) => {
            linha.classList.toggle('atual', n === i);
        });
    }

    function renderizarEventos() {
        const lista = $('rt-eventos');
        lista.replaceChildren(...eventos.map((evento) => {
            const d = descrever(evento);
            const botao = document.createElement('button');
            botao.type = 'button';
            botao.className = 'rt-evento';
            const hora = document.createElement('span');
            hora.className = 'rt-hora';
            hora.textContent = horaDoDia(evento.ts);
            const noAudio = document.createElement('span');
            noAudio.className = 'rt-no-audio';
            noAudio.textContent = inicioMs === null ? '' : tempoAudio(segundosNoAudio(evento));
            const nome = document.createElement('span');
            nome.className = 'rt-nome';
            nome.textContent = d.titulo || d.texto || '';
            botao.append(hora, noAudio, nome);
            botao.addEventListener('click', () => {
                if (inicioMs === null || !audio.src) return;
                audio.currentTime = Math.max(0, segundosNoAudio(evento) - VOLTA_AO_PULAR);
                audio.play();
            });
            const item = document.createElement('li');
            item.append(botao);
            return item;
        }));
        $('rt-total').textContent = eventos.length ? `(${eventos.length})` : '';
        $('rt-vazio').hidden = eventos.length > 0;
        linhaAtual = -2;
        atualizarTela();
    }

    function conferirHorario() {
        const aviso = $('rt-aviso');
        const fim = inicioMs === null || !audio.duration ? null : inicioMs + audio.duration * 1000;
        const encontrou = fim === null || eventos.some((e) => e.ts >= inicioMs && e.ts <= fim);
        aviso.hidden = encontrou;
        aviso.textContent = encontrou ? '' :
            _t('Nenhuma troca de tela no horário deste áudio. Confira o dia e o início da gravação.');
    }

    async function carregarEventos() {
        if (!$('rt-dia').value) return;
        const resposta = await fetch(`/api/registro-tela?dia=${encodeURIComponent($('rt-dia').value)}`);
        eventos = resposta.ok ? (await resposta.json()).eventos : [];
        renderizarEventos();
        conferirHorario();
    }

    // culto_20261102_193012.mp3 (recorder.py do site)
    function inicioDoNome(nome) {
        const m = /(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})/.exec(nome);
        if (!m) return null;
        return new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]);
    }

    function definirInicio(data) {
        inicioMs = data ? data.getTime() : null;
        $('rt-medir').disabled = inicioMs === null;
        renderizarEventos();
        conferirHorario();
    }

    function abrirArquivo(arquivo) {
        if (!arquivo) return;
        if (urlAudio) URL.revokeObjectURL(urlAudio);
        urlAudio = URL.createObjectURL(arquivo);
        audio.src = urlAudio;
        nomeArquivo = arquivo.name;
        const data = inicioDoNome(arquivo.name);
        if (data) {
            campoInicio.value = `${paraCampoData(data)}T${[data.getHours(), data.getMinutes(), data.getSeconds()].map(doisDigitos).join(':')}`;
            $('rt-dia').value = paraCampoData(data);
            definirInicio(data);
            carregarEventos();
        }
        renderizarMedicoes();
    }

    function mostrarAtraso() {
        $('rt-atraso-valor').textContent = `${atraso().toFixed(1)} s`;
    }

    function renderizarMedicoes() {
        const lista = medicoes[nomeArquivo] || [];
        $('rt-medicoes').hidden = lista.length === 0;
        $('rt-lista-medicoes').replaceChildren(...lista.map((m) => {
            const item = document.createElement('li');
            item.textContent = `${tempoAudio(m.noAudio)} → ${m.atraso.toFixed(1)} s`;
            return item;
        }));
        if (lista.length) {
            const valores = lista.map((m) => m.atraso);
            const media = valores.reduce((a, b) => a + b, 0) / valores.length;
            const variacao = Math.max(...valores) - Math.min(...valores);
            $('rt-resumo').textContent = _t('Média: {media} s · variação: {variacao} s', {
                media: media.toFixed(1), variacao: variacao.toFixed(1),
            });
        }
    }

    $('rt-dia').addEventListener('change', carregarEventos);
    $('rt-arquivo').addEventListener('change', (e) => abrirArquivo(e.target.files[0]));
    campoInicio.addEventListener('change', () => {
        definirInicio(campoInicio.value ? new Date(campoInicio.value) : null);
    });
    campoAtraso.addEventListener('input', () => {
        mostrarAtraso();
        renderizarEventos();
    });
    audio.addEventListener('timeupdate', atualizarTela);
    audio.addEventListener('seeked', atualizarTela);
    audio.addEventListener('loadedmetadata', conferirHorario);
    $('rt-medir').addEventListener('click', () => {
        (medicoes[nomeArquivo] = medicoes[nomeArquivo] || []).push({ noAudio: audio.currentTime, atraso: atraso() });
        medicoes[nomeArquivo].sort((a, b) => a.noAudio - b.noAudio);
        salvarMedicoes();
        renderizarMedicoes();
    });
    $('rt-limpar-medicoes').addEventListener('click', () => {
        delete medicoes[nomeArquivo];
        salvarMedicoes();
        renderizarMedicoes();
    });

    $('rt-dia').value = paraCampoData(new Date());
    mostrarAtraso();
    carregarEventos();
}());
