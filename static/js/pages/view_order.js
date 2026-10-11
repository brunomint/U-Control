const CONFIG = JSON.parse(document.getElementById('view-order-data').textContent);

const weekdays = ['Domingo', 'Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sábado'];
const months = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'];

// Format date
const dateStr = CONFIG.date;
const [year, month, day] = dateStr.split('-');
const dateObj = new Date(year, month - 1, day);

document.getElementById('orderDate').textContent = `${day} de ${months[dateObj.getMonth()]}`;
document.getElementById('orderWeekday').textContent = `${weekdays[dateObj.getDay()]} · ${year}`;

// Count stats
const items = document.querySelectorAll('.item');
let musicas = 0, biblia = 0;

items.forEach(item => {
    if (item.classList.contains('bible')) {
        biblia++;
    } else if (!item.classList.contains('text-item')) {
        musicas++;
    }
});

document.getElementById('statMusicas').textContent = musicas;
document.getElementById('statBiblia').textContent = biblia;

// Copy link
function copyLink() {
    const url = window.location.href;
    navigator.clipboard.writeText(url).then(() => {
        showToast('Link copiado para a área de transferência!');
    }).catch(() => {
        // Fallback
        const input = document.createElement('input');
        input.value = url;
        document.body.appendChild(input);
        input.select();
        document.execCommand('copy');
        document.body.removeChild(input);
        showToast('Link copiado!');
    });
}

function showToast(message, type) {
    window.ucToast(message, type);
}

// Réplica do filtro `truncate(length, killwords=True, end="...")` do Jinja2
// (leeway padrão do Jinja é 5: só corta se o texto for maior que length+leeway)
function truncateJinja(s, length, end = '...') {
    const leeway = 5;
    if (s.length <= length + leeway) return s;
    return s.slice(0, length - end.length) + end;
}

function downloadPDF() {
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF();
    let y = 20;

    doc.setFontSize(18);
    doc.text('Ordem do Culto', 105, y, { align: 'center' }); y += 8;
    doc.setFontSize(12);
    doc.text(
        document.getElementById('orderDate').textContent + ' — ' +
        document.getElementById('orderWeekday').textContent,
        105, y, { align: 'center' }
    ); y += 10;

    const o = CONFIG.order;
    if (o.tipo) { doc.text('Tipo: ' + o.tipo, 20, y); y += 7; }
    if (o.dirigente) { doc.text('Dirigente: ' + o.dirigente, 20, y); y += 7; }
    if (o.pregador) { doc.text('Pregador: ' + o.pregador, 20, y); y += 7; }
    if (o.horario) { doc.text('Horário: ' + o.horario, 20, y); y += 7; }
    if (o.tema) { doc.text('Tema: ' + o.tema, 20, y); y += 7; }
    y += 5;

    doc.setFontSize(11);
    o.itemLabels.forEach((label, i) => {
        const clean = truncateJinja(label.replace(/\\/g, ''), 80);
        doc.text((i + 1) + '. ' + clean, 20, y);
        y += 7;
        if (y > 270) { doc.addPage(); y = 20; }
    });

    doc.save('ordem-' + CONFIG.date + '.pdf');
}

function copyWhatsapp() {
    const date = document.getElementById('orderDate').textContent;
    const weekday = document.getElementById('orderWeekday').textContent;
    let text = `*Ordem do Culto — ${date}*\n_${weekday}_`;
    const o = CONFIG.order;
    if (o.tipo) text += '\n*Tipo:* ' + o.tipo;
    if (o.dirigente) text += '\n*Dirigente:* ' + o.dirigente;
    if (o.pregador) text += '\n*Pregador:* ' + o.pregador;
    if (o.horario) text += '\n*Horário:* ' + o.horario;
    if (o.tema) text += '\n*Tema:* _' + o.tema + '_';
    text += '\n\n*Programação:*\n';
    o.itemLabels.forEach((label, i) => {
        text += (i + 1) + '. ' + label + '\n';
    });
    navigator.clipboard.writeText(text)
        .then(() => showToast('Texto copiado para o WhatsApp!'))
        .catch(() => {
            const el = document.createElement('textarea');
            el.value = text; document.body.appendChild(el); el.select();
            document.execCommand('copy'); document.body.removeChild(el);
            showToast('Texto copiado!');
        });
}

// ── Itens já feitos no culto ─────────────────────────────────────────
// Quem está logado marca/desmarca; todos veem (a página busca as
// marcações a cada 10 s, então a banda e a mídia acompanham sozinhas).
const feitosUrl = `/api/orders/${CONFIG.date}/feitos`;

function aplicarFeitos(feitos) {
    const set = new Set(feitos);
    let total = 0;
    document.querySelectorAll('.item[data-item]').forEach(li => {
        const feito = set.has(li.dataset.item);
        if (feito) total++;
        li.classList.toggle('feito', feito);
        const btn = li.querySelector('button.item-check');
        if (btn) btn.setAttribute('aria-pressed', String(feito));
    });
    document.getElementById('statFeitos').textContent = total;
}

async function salvarFeito(body) {
    try {
        const resp = await fetch(feitosUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        aplicarFeitos((await resp.json()).feitos);
    } catch (e) {
        showToast('Não deu pra salvar a marcação', 'error');
        atualizarFeitos();
    }
}

async function atualizarFeitos() {
    if (document.hidden) return;
    try {
        const resp = await fetch(feitosUrl);
        if (resp.ok) aplicarFeitos((await resp.json()).feitos);
    } catch (e) { /* sem conexão: tenta de novo no próximo ciclo */ }
}

if (CONFIG.canMark) {
    document.getElementById('itemsList').addEventListener('click', e => {
        const btn = e.target.closest('button.item-check');
        if (!btn) return;
        const feito = btn.getAttribute('aria-pressed') !== 'true';
        btn.closest('.item').classList.toggle('feito', feito);  // resposta imediata
        btn.setAttribute('aria-pressed', String(feito));
        salvarFeito({ item: btn.closest('.item').dataset.item, feito });
    });
    document.getElementById('limparFeitos').addEventListener('click', () => {
        if (confirm('Desmarcar todos os itens desta ordem?')) salvarFeito({ limpar: true });
    });
}
setInterval(atualizarFeitos, 10000);
document.addEventListener('visibilitychange', atualizarFeitos);
