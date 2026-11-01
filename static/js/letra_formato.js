// Formatar palavras na letra, só no telão do público e no overlay do OBS
// (display_public.js, display_obs.js). O palco, a visualização e a
// impressão mostram o texto sem as marcações (UcFormato.limpar; no servidor,
// letra_formato.py). Marcações:
//   **Jesus**            negrito
//   *graça*              itálico
//   {amarelo}Santo{/}    cor (nome da lista ou #rrggbb)
//   {grande}Aleluia{/}   tamanho: grande, maior, pequeno
// Dá pra combinar: {amarelo}**Jesus**{/}. Um * sozinho (marcador) fica como está.
window.UcFormato = (function () {
    const CORES = {
        amarelo: '#ffd84d', dourado: '#e6b422', vermelho: '#ff5a5a', laranja: '#ff9f40', verde: '#5cd65c',
        azul: '#59b4ff', roxo: '#b48cff', rosa: '#ff7ab8', branco: '#ffffff', preto: '#000000', cinza: '#bbbbbb',
    };
    const TAMANHOS = { grande: '1.25em', maior: '1.5em', pequeno: '0.8em' };
    const BLOCO = /\{(#[0-9a-fA-F]{6}|[a-zA-Z]+)\}([^{]*?)\{\/\}/g;   // o mais de dentro primeiro (sem { no meio)
    const NEGRITO = /\*\*(\S(?:[^\n]*?\S)?)\*\*/g;
    const ITALICO = /\*(\S(?:[^\n*]*?\S)?)\*/g;

    const conhecido = nome => /^#/.test(nome) || CORES[nome.toLowerCase()] || TAMANHOS[nome.toLowerCase()];
    const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

    function blocos(texto, troca) {
        let antes;
        do {
            antes = texto;
            texto = texto.replace(BLOCO, (m, nome, dentro) => (conhecido(nome) ? troca(nome.toLowerCase(), dentro) : m));
        } while (texto !== antes);
        return texto;
    }

    // Texto puro -> HTML seguro com a formatação (quebra de linha vira <br>)
    function html(texto) {
        let s = esc(texto || '');
        s = s.replace(NEGRITO, '<strong>$1</strong>').replace(ITALICO, '<em>$1</em>');
        s = blocos(s, (nome, dentro) => TAMANHOS[nome]
            ? `<span style="font-size:${TAMANHOS[nome]}">${dentro}</span>`
            : `<span style="color:${CORES[nome] || nome}">${dentro}</span>`);
        return s.replace(/\n/g, '<br>');
    }

    // Texto sem as marcações (palco, visualização)
    function limpar(texto) {
        if (!texto) return texto;
        return blocos(String(texto), (nome, dentro) => dentro).replace(NEGRITO, '$1').replace(ITALICO, '$1');
    }

    // Linha só com "||" divide a seção em slides menores, só no telão do
    // público e no OBS (lyrics_2.js manda a parte em payload.textoPublico);
    // o retorno de palco mostra a seção inteira, sem a linha.
    // Aceita o fim de linha do Windows (\r\n): letra colada de lá vinha com "||\r"
    const DIVISAO = /^[ \t]*\|\|[ \t\r]*$/;
    function partes(texto) {
        const blocos = [[]];
        String(texto || '').split(/\r?\n/).forEach(linha => {
            if (DIVISAO.test(linha)) blocos.push([]);
            else blocos[blocos.length - 1].push(linha);
        });
        const lista = blocos.map(b => b.join('\n').replace(/^\n+|\n+$/g, '')).filter(t => t.trim());
        return lista.length ? lista : [String(texto || '')];
    }
    function semDivisao(texto) {
        return String(texto || '').split(/\r?\n/).filter(linha => !DIVISAO.test(linha)).join('\n');
    }

    return { html, limpar, partes, semDivisao, CORES, TAMANHOS };
})();
