const CONFIG = JSON.parse(document.getElementById('view-order-data').textContent);

const weekdays = ['Domingo', 'Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sábado'];
const months = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'];

// Format date
const dateStr = CONFIG.date;
const [year, month, day] = dateStr.split('-');
const dateObj = new Date(year, month - 1, day);

document.getElementById('orderDate').textContent = `${day} de ${months[dateObj.getMonth()]}`;
document.getElementById('orderWeekday').textContent = `${weekdays[dateObj.getDay()]} • ${year}`;

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

function showToast(message) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.classList.add('show');
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
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
