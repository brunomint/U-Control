// Compartilhar a agenda do mês no WhatsApp (calendário de edição,
// /agenda/edit). Usa ordersData/currentMonth/monthLong/formatDateISO de
// agenda_calendar_edit.js.
//   - Copiar para WhatsApp: texto formatado (*negrito*), só os dias com algo
//   - Compartilhar imagem (menu: grade do mês, lista clara, lista escura):
//     no celular abre o menu de compartilhar do aparelho; no computador
//     copia a imagem (Ctrl+V no WhatsApp Web)
//   - Salvar imagem: baixa o PNG (como antes)
(function () {
    const WEEKDAY = ucLocale().startsWith('pt') ? ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb']
        : Array.from({ length: 7 }, (x, i) => new Date(2000, 0, 2 + i).toLocaleDateString(ucLocale(), { weekday: 'short' }));
    const isTouch = () => window.matchMedia('(pointer: coarse)').matches;
    const toast = (msg, type) => { if (window.ucToast) window.ucToast(msg, type); };

    // Itens de um dia: os cultos (tipo + horário/dirigente/pregador) e os
    // eventos, na ordem do horário — mesma regra do calendário
    // (AgendaCultos, static/js/agenda_cultos.js)
    const SHARE_LABEL = { Dirigente: _t('Dirigente'), Pregador: _t('Pregação'), Resp: _t('Resp.'), Obs: _t('Obs.') };
    function itemsForDay(day) {
        return AgendaCultos.dayItems(day).map(it => ({
            title: it.titulo,
            time: it.hora,
            details: it.meta.filter(([, v]) => v).map(([label, v]) => `${SHARE_LABEL[label] || label}: ${v}`),
        }));
    }

    // Dias do mês aberto que têm algo cadastrado
    function monthDays() {
        const year = currentMonth.getFullYear();
        const month = currentMonth.getMonth();
        const last = new Date(year, month + 1, 0).getDate();
        const byDay = AgendaCultos.groupByDay(ordersData);
        const days = [];
        for (let d = 1; d <= last; d++) {
            const date = new Date(year, month, d);
            const items = itemsForDay(byDay[formatDateISO(date)]);
            if (items.length) days.push({ date, items });
        }
        return days;
    }

    const monthTitle = () => _t('{mes} de {ano}', { mes: monthLong[currentMonth.getMonth()], ano: currentMonth.getFullYear() });
    const dayLabel = (date) => `${WEEKDAY[date.getDay()]} ${String(date.getDate()).padStart(2, '0')}`;

    function buildText() {
        const days = monthDays();
        const lines = [_t('📅 *Agenda de {mes}*', { mes: monthTitle() }), ''];
        if (!days.length) lines.push(_t('_Nenhuma data cadastrada._'), '');
        days.forEach(({ date, items }) => {
            lines.push(`*${dayLabel(date)}*`);
            items.forEach(it => {
                lines.push(`• ${it.title}${it.time ? ` · ${it.time}` : ''}`);
                if (it.details.length) lines.push(`   ${it.details.join(' · ')}`);
            });
            lines.push('');
        });
        lines.push(_t('Calendário completo: {link}', { link: `${location.origin}/agenda` }));
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
            toast(_t('Agenda copiada. É só colar no WhatsApp.'));
        } catch (e) {
            // Sem acesso à área de transferência (http fora do localhost)
            const ta = document.createElement('textarea');
            ta.value = text;
            ta.style.cssText = 'position:fixed;opacity:0';
            document.body.appendChild(ta);
            ta.select();
            const ok = document.execCommand('copy');
            ta.remove();
            toast(ok ? _t('Agenda copiada. É só colar no WhatsApp.') : _t('Não deu pra copiar o texto.'), ok ? undefined : 'error');
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

    // Lista vertical pro celular: só os dias com algo,
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
            `<div style="font-size:30px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:${t.muted}">${esc(_t('Agenda'))}</div>` +
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
            : `<div style="font-size:36px;color:${t.muted}">${esc(_t('Nenhuma data cadastrada.'))}</div>`) +
            `<div style="margin-top:36px;padding-top:24px;border-top:2px solid ${t.line};font-size:26px;color:${t.muted}">${esc(_t('Calendário completo: {link}', { link: `${location.host}/agenda` }))}</div>`;
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

    // Formatos: grade do mês ou lista vertical (clara/escura). O navegador
    // só deixa copiar/compartilhar logo após o clique, e gerar a imagem
    // leva 1–2 s — por isso as três começam a ser geradas quando o menu
    // abre e ficam guardadas (por mês) pro clique.
    const FORMATS = {
        grid: { label: _t('grade'), make: () => gridCanvas() },
        light: { label: _t('lista clara'), make: () => listCanvas('light') },
        dark: { label: _t('lista escura'), make: () => listCanvas('dark') },
    };
    const cache = new Map();
    const monthKey = () => `${currentMonth.getFullYear()}-${currentMonth.getMonth()}`;

    function render(format) {
        const key = `${format}|${monthKey()}`;
        if (!cache.has(key)) {
            const entry = { ready: false };
            entry.promise = (async () => {
                const canvas = await FORMATS[format].make();
                const blob = await toBlob(canvas);
                entry.ready = true;
                entry.canvas = canvas;
                entry.blob = blob;
                return entry;
            })();
            entry.promise.catch(() => cache.delete(key));
            cache.set(key, entry);
        }
        return cache.get(key);
    }

    // Gera uma de cada vez (a grade usa a própria página, não dá pra
    // misturar com outra captura ao mesmo tempo)
    async function prepareAll() {
        for (const format of Object.keys(FORMATS)) {
            try { await render(format).promise; } catch (e) { /* tenta de novo no clique */ }
        }
    }

    async function shareImage(format) {
        const entry = render(format);
        const name = fileName();
        // Celular: menu de compartilhar do aparelho, com a imagem
        if (isTouch() && navigator.share) {
            try {
                const { blob } = await entry.promise;
                const file = new File([blob], name, { type: 'image/png' });
                if (navigator.canShare && navigator.canShare({ files: [file] })) {
                    await navigator.share({ files: [file], title: _t('Agenda de {mes}', { mes: monthTitle() }) });
                    return;
                }
            } catch (e) {
                if (e.name === 'AbortError') return;
                if (e.name === 'NotAllowedError' && !entry.ready) {
                    toast(_t('A imagem ainda estava sendo preparada. Toque de novo.'), 'error');
                    return;
                }
            }
        }
        // Computador: copia a imagem (Ctrl+V no WhatsApp Web). A promessa
        // vai direto pro ClipboardItem, assim a cópia vale mesmo se a
        // imagem terminar de ser gerada depois do clique.
        if (navigator.clipboard && window.ClipboardItem) {
            try {
                await navigator.clipboard.write([new ClipboardItem({ 'image/png': entry.promise.then(r => r.blob) })]);
                toast(_t('Imagem ({formato}) copiada. Cole com Ctrl+V no WhatsApp.', { formato: FORMATS[format].label }));
                return;
            } catch (e) { /* sem permissão: baixa */ }
        }
        try {
            download((await entry.promise).canvas);
            toast(_t('Imagem baixada. Anexe no WhatsApp.'));
        } catch (e) {
            toast(_t('Não deu pra gerar a imagem.'), 'error');
        }
    }

    async function saveImage() {
        try { download(await gridCanvas()); }
        catch (e) { toast(_t('Não deu pra salvar a imagem.'), 'error'); }
    }

    document.getElementById('copyWhatsBtn').addEventListener('click', copyText);
    const menu = document.getElementById('shareMenu');
    menu.addEventListener('toggle', () => { if (menu.open) prepareAll(); });
    menu.querySelectorAll('[data-format]').forEach(btn => btn.addEventListener('click', () => {
        menu.open = false;
        shareImage(btn.dataset.format);
    }));
    document.addEventListener('click', (e) => { if (!menu.contains(e.target)) menu.open = false; });
    document.getElementById('saveImgBtn').addEventListener('click', saveImage);

    window.agendaShare = { buildText, listCanvas, gridCanvas };
})();
