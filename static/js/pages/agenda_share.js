// Compartilhar a agenda do mês no WhatsApp (calendário de edição,
// /agenda/edit). Usa ordersData/currentMonth/monthLong/formatDateISO de
// agenda_calendar_edit.js.
//   - Copiar para WhatsApp: texto formatado (*negrito*), só os dias com algo
//   - Compartilhar imagem: no celular abre o menu de compartilhar do
//     aparelho; no computador copia a imagem (Ctrl+V no WhatsApp Web)
//   - Salvar imagem: baixa o PNG (como antes)
(function () {
    const WEEKDAY = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'];
    const isTouch = () => window.matchMedia('(pointer: coarse)').matches;
    const toast = (msg, type) => { if (window.ucToast) window.ucToast(msg, type); };

    // Itens de um dia: o culto (tipo + horário/dirigente/pregador) e os
    // eventos — mesma regra do calendário (culto primeiro, depois horário)
    function itemsForDay(o) {
        const items = [];
        if (o && o.tipo && o.tipo.trim() && (o.horario_culto || o.dirigente || o.pregador)) {
            const details = [];
            if (o.dirigente) details.push(`Dirigente: ${o.dirigente}`);
            if (o.pregador) details.push(`Pregação: ${o.pregador}`);
            items.push({ order: 0, title: o.tipo.trim(), time: o.horario_culto || '', details });
        }
        (o && Array.isArray(o.eventos) ? o.eventos : []).forEach(ev => {
            if (!ev || !ev.titulo) return;
            const details = [];
            if (ev.responsavel) details.push(`Resp.: ${ev.responsavel}`);
            if (ev.obs) details.push(`Obs.: ${ev.obs}`);
            items.push({ order: 1, title: ev.titulo.trim(), time: ev.hora || '', details });
        });
        return items.sort((a, b) => a.order - b.order || (a.time || '').localeCompare(b.time || ''));
    }

    // Dias do mês aberto que têm algo cadastrado
    function monthDays() {
        const year = currentMonth.getFullYear();
        const month = currentMonth.getMonth();
        const last = new Date(year, month + 1, 0).getDate();
        const days = [];
        for (let d = 1; d <= last; d++) {
            const date = new Date(year, month, d);
            const items = itemsForDay(ordersData[formatDateISO(date)] || {});
            if (items.length) days.push({ date, items });
        }
        return days;
    }

    const monthTitle = () => `${monthLong[currentMonth.getMonth()]} de ${currentMonth.getFullYear()}`;
    const dayLabel = (date) => `${WEEKDAY[date.getDay()]} ${String(date.getDate()).padStart(2, '0')}`;

    function buildText() {
        const days = monthDays();
        const lines = [`📅 *Agenda de ${monthTitle()}*`, ''];
        if (!days.length) lines.push('_Nenhuma data cadastrada._', '');
        days.forEach(({ date, items }) => {
            lines.push(`*${dayLabel(date)}*`);
            items.forEach(it => {
                lines.push(`• ${it.title}${it.time ? ` · ${it.time}` : ''}`);
                if (it.details.length) lines.push(`   ${it.details.join(' · ')}`);
            });
            lines.push('');
        });
        lines.push(`Calendário completo: ${location.origin}/agenda`);
        return lines.join('\n');
    }

    async function copyText() {
        const text = buildText();
        // Celular: menu de compartilhar do aparelho (WhatsApp aparece nele)
        if (isTouch() && navigator.share) {
            try { await navigator.share({ text }); return; } catch (e) { if (e.name === 'AbortError') return; }
        }
        try {
            await navigator.clipboard.writeText(text);
            toast('Agenda copiada. É só colar no WhatsApp.');
        } catch (e) {
            // Sem acesso à área de transferência (http fora do localhost)
            const ta = document.createElement('textarea');
            ta.value = text;
            ta.style.cssText = 'position:fixed;opacity:0';
            document.body.appendChild(ta);
            ta.select();
            const ok = document.execCommand('copy');
            ta.remove();
            toast(ok ? 'Agenda copiada. É só colar no WhatsApp.' : 'Não deu pra copiar o texto.', ok ? undefined : 'error');
        }
    }

    // ── Imagem ──────────────────────────────────────────────────────────
    // Grade do mês (o cartão da página), como o "Salvar imagem" de antes
    async function gridCanvas() {
        const shell = document.querySelector('.calendar-shell');
        shell.classList.add('capturing');
        try {
            return await html2canvas(shell, { backgroundColor: '#161a2b', scale: 2, useCORS: true });
        } finally {
            shell.classList.remove('capturing');
        }
    }

    // Lista vertical pro celular (opção em avaliação): só os dias com algo,
    // letra grande, 1080 px de largura. theme: 'light' | 'dark'
    const THEMES = {
        light: { bg: '#ffffff', card: '#f4f2fb', text: '#1d1a2e', muted: '#5f5a78', accent: '#5b3fd6', line: '#e4e0f3', day: '#5b3fd6' },
        dark: { bg: '#0f1220', card: '#1d2236', text: '#e9ebf4', muted: '#9198b3', accent: '#b9a8ff', line: '#2a3050', day: '#f2b84b' },
    };
    async function listCanvas(theme) {
        const t = THEMES[theme] || THEMES.light;
        const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
        const days = monthDays();
        const el = document.createElement('div');
        el.style.cssText = `position:fixed;left:-20000px;top:0;width:1080px;padding:72px 64px 56px;box-sizing:border-box;` +
            `background:${t.bg};color:${t.text};font-family:Manrope,'Segoe UI',system-ui,sans-serif;`;
        el.innerHTML =
            `<div style="font-size:30px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:${t.muted}">Agenda</div>` +
            `<div style="font-size:64px;font-weight:800;line-height:1.1;margin:6px 0 40px">${esc(monthTitle().charAt(0).toUpperCase() + monthTitle().slice(1))}</div>` +
            (days.length ? days.map(({ date, items }) =>
                `<div style="display:flex;gap:28px;padding:26px 0;border-top:2px solid ${t.line}">` +
                    `<div style="width:120px;flex:none;text-align:center">` +
                        `<div style="font-size:26px;font-weight:800;color:${t.muted};text-transform:uppercase">${WEEKDAY[date.getDay()]}</div>` +
                        `<div style="font-size:60px;font-weight:800;line-height:1;color:${t.day}">${String(date.getDate()).padStart(2, '0')}</div>` +
                    `</div>` +
                    `<div style="flex:1;display:flex;flex-direction:column;gap:14px">` +
                    items.map(it =>
                        `<div style="background:${t.card};border-radius:18px;padding:18px 22px">` +
                            `<div style="font-size:36px;font-weight:800">${esc(it.title)}${it.time ? ` <span style="color:${t.accent};font-weight:700">· ${esc(it.time)}</span>` : ''}</div>` +
                            (it.details.length ? `<div style="font-size:28px;color:${t.muted};margin-top:6px;line-height:1.35">${it.details.map(esc).join('<br>')}</div>` : '') +
                        `</div>`).join('') +
                    `</div>` +
                `</div>`).join('')
            : `<div style="font-size:36px;color:${t.muted}">Nenhuma data cadastrada.</div>`) +
            `<div style="margin-top:36px;padding-top:24px;border-top:2px solid ${t.line};font-size:26px;color:${t.muted}">Calendário completo: ${esc(location.host)}/agenda</div>`;
        document.body.appendChild(el);
        try {
            return await html2canvas(el, { backgroundColor: t.bg, scale: 1, useCORS: true });
        } finally {
            el.remove();
        }
    }

    const fileName = () => `agenda-${monthTitle().toLowerCase().replace(/\s+/g, '-')}.png`;
    const toBlob = canvas => new Promise(res => canvas.toBlob(res, 'image/png'));

    function download(canvas) {
        const link = document.createElement('a');
        link.download = fileName();
        link.href = canvas.toDataURL('image/png');
        link.click();
    }

    async function shareImage() {
        let canvas;
        try { canvas = await gridCanvas(); } catch (e) { toast('Não deu pra gerar a imagem.', 'error'); return; }
        const blob = await toBlob(canvas);
        const file = new File([blob], fileName(), { type: 'image/png' });
        // Celular: menu de compartilhar do aparelho, com a imagem
        if (isTouch() && navigator.canShare && navigator.canShare({ files: [file] })) {
            try { await navigator.share({ files: [file], title: `Agenda de ${monthTitle()}` }); return; }
            catch (e) { if (e.name === 'AbortError') return; }
        }
        // Computador: copia a imagem (Ctrl+V no WhatsApp Web)
        if (navigator.clipboard && window.ClipboardItem) {
            try {
                await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]);
                toast('Imagem copiada. Cole com Ctrl+V no WhatsApp.');
                return;
            } catch (e) { /* sem permissão: baixa */ }
        }
        download(canvas);
        toast('Imagem baixada. Anexe no WhatsApp.');
    }

    async function saveImage() {
        try { download(await gridCanvas()); }
        catch (e) { toast('Não deu pra salvar a imagem.', 'error'); }
    }

    document.getElementById('copyWhatsBtn').addEventListener('click', copyText);
    document.getElementById('shareImgBtn').addEventListener('click', shareImage);
    document.getElementById('saveImgBtn').addEventListener('click', saveImage);

    // Usado pra avaliar a imagem em lista (ainda não ligada a um botão)
    window.agendaShare = { buildText, listCanvas, gridCanvas };
})();
