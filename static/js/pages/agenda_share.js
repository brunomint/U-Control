// Compartilhar a agenda do mês no WhatsApp (calendário de edição,
// /agenda/edit). Usa ordersData/currentMonth/monthLong/formatDateISO de
// agenda_calendar_edit.js.
//   - Copiar para WhatsApp: texto formatado (*negrito*), só os dias com algo
//   - Compartilhar imagem (menu: grade do mês, calendário clássico, lista clara, lista escura):
//     no celular abre o menu de compartilhar do aparelho; no computador
//     copia a imagem (Ctrl+V no WhatsApp Web)
//   - Salvar imagem (mesmo menu): baixa o PNG
// O "calendário clássico" imita a planilha que as igrejas mandam no WhatsApp:
// título verde, dias da semana por extenso, semanas alternando branco e
// salmão, nome de cada culto/evento em letra grande com uma cor própria.
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

    // ── Calendário clássico (planilha) ─────────────────────────────────
    // Cor fixa pros tipos de culto; os outros nomes (EBD, Orando em sua
    // casa...) pegam uma cor da paleta na ordem em que aparecem no mês, e
    // o mesmo nome tem sempre a mesma cor. Culto especial, Natal e fim de
    // ano viram faixa colorida com letra branca, como na planilha.
    const CLASSIC_FIXED = {
        'Culto Dominical': '#0070C0', 'Culto de Oração': '#C55A11', 'Culto de Jovens': '#7030A0',
        'Culto de Ensino': '#00B050', 'Culto Santa Ceia': '#C00000',
    };
    const CLASSIC_PALETTE = ['#7030A0', '#00B0F0', '#00B050', '#C55A11', '#0070C0', '#BF8F00', '#2F5597', '#548235', '#C00000',
        '#D63384', '#16A085', '#E46C0A', '#5B9BD5', '#8E44AD', '#7F6000'];
    const CLASSIC_SHORT = { Dirigente: _t('Dir'), Pregador: _t('Preg'), Resp: _t('Resp'), Obs: '' };
    function classicHighlight(rawTitle, tipo) {
        const t = rawTitle.toLowerCase();
        if (tipo === 'Culto Especial' || /natal/.test(t)) return '#E00000';
        if (/fim de ano|ano novo|réveillon|reveillon/.test(t)) return '#FFC000';
        return null;
    }
    // "Não haverá programação", "cancelado": aviso em preto, sem cor de evento
    const classicNotice = title => /^(não|nao) haver|sem programa|cancelad|recesso/i.test(title);
    const WEEKDAY_LONG = ucLocale().startsWith('pt')
        ? ['DOMINGO', 'SEGUNDA', 'TERÇA', 'QUARTA', 'QUINTA', 'SEXTA', 'SÁBADO']
        : Array.from({ length: 7 }, (x, i) => new Date(2000, 0, 2 + i).toLocaleDateString(ucLocale(), { weekday: 'long' }).toUpperCase());

    async function classicCanvas() {
        const esc = AgendaCultos.esc;
        const year = currentMonth.getFullYear();
        const month = currentMonth.getMonth();
        const last = new Date(year, month + 1, 0).getDate();
        const byDay = AgendaCultos.groupByDay(ordersData);
        const firstWeekday = new Date(year, month, 1).getDay();

        // Itens de cada dia (com o tipo de culto, pra cor) e as cores do mês.
        // Só reserva a cor fixa dos tipos de culto que aparecem neste mês.
        const colorOf = {};
        const used = new Set();
        const prefix = formatDateISO(new Date(year, month, 1)).slice(0, 8);
        Object.entries(byDay).filter(([key]) => key.startsWith(prefix))
            .forEach(([, day]) => day.cultos.forEach(c => { if (CLASSIC_FIXED[c.tipo]) used.add(CLASSIC_FIXED[c.tipo]); }));
        let next = 0;
        function color(title, tipo) {
            if (tipo && CLASSIC_FIXED[tipo]) return CLASSIC_FIXED[tipo];
            if (classicNotice(title)) return '#000000';
            const key = title.toLowerCase();
            if (!colorOf[key]) {
                const livre = CLASSIC_PALETTE.find(c => !used.has(c));
                colorOf[key] = livre || CLASSIC_PALETTE[next++ % CLASSIC_PALETTE.length];
                used.add(colorOf[key]);
            }
            return colorOf[key];
        }
        const days = {};
        for (let d = 1; d <= last; d++) {
            const day = byDay[formatDateISO(new Date(year, month, d))];
            const items = [];
            if (day) {
                day.cultos.forEach(c => items.push({ tipo: c.tipo, title: _t(c.tipo), hora: c.hora,
                    meta: [['Dirigente', c.dirigente], ['Pregador', c.pregador]] }));
                day.eventos.forEach(e => items.push({ tipo: '', title: e.titulo.trim(), hora: e.hora || '',
                    meta: [['Resp', e.responsavel], ['Obs', e.obs]] }));
                items.sort((a, b) => (a.hora || '99').localeCompare(b.hora || '99'));
            }
            days[d] = items;
        }

        // Colunas mais largas onde tem mais coisa (o domingo costuma ser a maior)
        const weight = [0, 1, 2, 3, 4, 5, 6].map(w => {
            let max = 0;
            for (let d = 1; d <= last; d++) if (new Date(year, month, d).getDay() === w) max = Math.max(max, days[d].length);
            return 1 + Math.min(1.4, max * 0.7);
        });
        const total = weight.reduce((a, b) => a + b, 0);
        const WIDTH = 1600;

        function itemHtml(it) {
            const highlight = classicHighlight(it.title, it.tipo);
            const titleColor = highlight ? '#ffffff' : color(it.title, it.tipo);
            const title = highlight
                ? `<div style="background:${highlight};color:${titleColor};font-size:34px;font-weight:800;line-height:1.05;padding:6px 6px 8px;margin:2px -8px 0;text-transform:uppercase">${esc(it.title)}</div>`
                : `<div style="color:${titleColor};font-size:${classicNotice(it.title) ? 24 : 30}px;font-weight:800;line-height:1.15;text-transform:uppercase;letter-spacing:.02em">${esc(it.title)}</div>`;
            const hora = it.hora ? `<div style="font-size:28px;font-weight:700;line-height:1.2">${esc(it.hora)}</div>` : '';
            const meta = it.meta.filter(([, v]) => v).map(([label, v]) => CLASSIC_SHORT[label]
                ? `<div style="display:flex;gap:10px;font-size:23px;line-height:1.4"><span style="flex:none">${esc(CLASSIC_SHORT[label])}:</span><span style="flex:1;text-align:center;text-transform:uppercase">${esc(v)}</span></div>`
                : `<div style="font-size:21px;line-height:1.3;text-align:center">${esc(v)}</div>`).join('');
            return `<div style="margin-bottom:6px">${title}${hora}${meta}</div>`;
        }

        const cells = [];
        for (let i = 0; i < firstWeekday; i++) cells.push(null);
        for (let d = 1; d <= last; d++) cells.push(d);
        while (cells.length % 7) cells.push(null);
        let rows = '';
        for (let r = 0; r < cells.length / 7; r++) {
            const bg = r % 2 ? '#FBE4D5' : '#ffffff';
            rows += '<tr>' + cells.slice(r * 7, r * 7 + 7).map(d => d === null
                ? `<td style="background:${bg}"></td>`
                : `<td style="background:${bg};vertical-align:top;padding:4px 10px 10px">` +
                    `<div style="text-align:right;font-size:26px;line-height:1.2">${d}</div>` +
                    `<div style="text-align:center">${days[d].map(itemHtml).join('')}</div>` +
                `</td>`).join('') + '</tr>';
        }

        const border = 'border:2px solid #000';
        const el = document.createElement('div');
        el.style.cssText = `position:fixed;left:-20000px;top:0;width:${WIDTH}px;padding:16px;box-sizing:border-box;background:#fff;color:#000;` +
            `font-family:Calibri,Carlito,'Segoe UI',Arial,sans-serif;`;
        el.innerHTML =
            `<style>.uc-classic td,.uc-classic th{${border};box-sizing:border-box}</style>` +
            `<table class="uc-classic" style="width:100%;border-collapse:collapse;table-layout:fixed;${border}">` +
                `<colgroup>${weight.map(w => `<col style="width:${(w / total * 100).toFixed(2)}%">`).join('')}</colgroup>` +
                `<tr><th colspan="7" style="background:#C6E0B4;font-size:48px;font-weight:800;padding:6px 0;text-transform:uppercase">${esc(monthTitle().replace(/ de /, ' '))}</th></tr>` +
                `<tr>${WEEKDAY_LONG.map(w => `<th style="background:#D9D9D9;font-size:30px;font-weight:600;padding:6px 2px">${esc(w)}</th>`).join('')}</tr>` +
                rows +
            `</table>`;
        document.body.appendChild(el);
        try {
            return await html2canvas(el, { backgroundColor: '#ffffff', scale: 1, useCORS: true });
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
        classic: { label: _t('calendário clássico'), make: () => classicCanvas() },
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

    async function saveImage(format) {
        try { download((await render(format).promise).canvas); }
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
    const saveMenu = document.getElementById('saveMenu');
    saveMenu.querySelectorAll('[data-save]').forEach(btn => btn.addEventListener('click', () => {
        saveMenu.open = false;
        saveImage(btn.dataset.save);
    }));
    document.addEventListener('click', (e) => { if (!saveMenu.contains(e.target)) saveMenu.open = false; });

    window.agendaShare = { buildText, listCanvas, gridCanvas, classicCanvas };
})();
