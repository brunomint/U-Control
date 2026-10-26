// Agenda com vários cultos no mesmo dia — usado pelos dois calendários
// (agenda_calendar.js, agenda_calendar_edit.js) e pelo compartilhar
// (agenda_share.js). /api/orders devolve um culto
// por chave: "YYYY-MM-DD" (1º culto do dia, e onde ficam os eventos do
// dia) ou "YYYY-MM-DD-N" (2º, 3º... culto). Ver orders_store.py.
window.AgendaCultos = (function () {
    const keyDate = key => key.slice(0, 10);
    const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
    const byTime = (a, b) => (a.hora || '99').localeCompare(b.hora || '99');
    // meta guarda a chave (Dirigente, Pregador...), que o agenda_share.js
    // também usa; o texto mostrado é traduzido aqui
    const metaLabel = label => ({ Dirigente: _t('Dirigente'), Pregador: _t('Pregador'), Resp: _t('Resp'), Obs: _t('Obs') }[label] || label);

    // Mesmo critério de sempre pra um culto aparecer no calendário
    function hasCulto(o) {
        return !!(o && o.tipo && o.tipo.trim() && o.tipo !== 'Nenhum' && (o.horario_culto || o.dirigente || o.pregador));
    }

    // { "2026-10-04": { cultos: [{key, tipo, hora, dirigente, pregador}], eventos: [...] } }
    function groupByDay(orders) {
        const days = {};
        for (const [key, o] of Object.entries(orders || {})) {
            const day = days[keyDate(key)] = days[keyDate(key)] || { cultos: [], eventos: [] };
            if (hasCulto(o)) {
                day.cultos.push({ key, tipo: o.tipo.trim(), hora: o.horario_culto || '', dirigente: o.dirigente || '', pregador: o.pregador || '' });
            }
            if (Array.isArray(o.eventos)) day.eventos.push(...o.eventos.filter(e => e && e.titulo));
        }
        for (const day of Object.values(days)) day.cultos.sort(byTime);
        return days;
    }

    // Cultos e eventos de um dia juntos, na ordem do horário
    function dayItems(day) {
        if (!day) return [];
        return [
            ...day.cultos.map(c => ({ kind: 'culto', titulo: c.tipo, hora: c.hora,
                meta: [['Dirigente', c.dirigente], ['Pregador', c.pregador]] })),
            ...day.eventos.map(e => ({ kind: 'evento', titulo: e.titulo.trim(), hora: e.hora || '',
                meta: [['Resp', e.responsavel], ['Obs', e.obs]] })),
        ].sort(byTime);
    }

    // Miolo do quadrinho do dia no calendário. Um item: com detalhes (como
    // sempre foi). Dois ou mais: uma linha por item, hora na frente.
    function dayCellInner(dayNumber, day) {
        const items = dayItems(day);
        const nCultos = day ? day.cultos.length : 0;
        const count = nCultos > 1 ? `<span class="day-count">${_t('{n} cultos', { n: nCultos })}</span>` : '';
        const top = `<div class="day-top"><div class="day-date">${dayNumber}</div>${count}</div>`;
        if (!items.length) {
            return `${top}<div class="day-body"><div class="info-line muted">${_t('Sem eventos')}</div></div>`;
        }
        const pill = it => it.kind === 'culto' ? 'tipo-pill' : 'eventos-pill';
        if (items.length === 1) {
            const it = items[0];
            const timeCls = it.kind === 'culto' ? 'time-pill-tipo' : 'time-pill-eventos';
            const meta = it.meta.filter(([, v]) => v).map(([label, v]) =>
                `<div class="meta-line"><span class="meta-label">${metaLabel(label)}:</span><span class="meta-value">${esc(v)}</span></div>`).join('');
            return `${top}<div class="day-body"><div class="day-item">
                    <span class="pill ${pill(it)}">${esc(it.titulo)}</span>
                    ${it.hora ? `<span class="pill ${timeCls}">${esc(it.hora)}</span>` : ''}
                    ${meta}
                </div></div>`;
        }
        const visible = items.slice(0, 4);
        const hidden = items.length - visible.length;
        const rows = visible.map(it =>
            `<div class="day-row"><span class="row-time">${esc(it.hora)}</span><span class="pill ${pill(it)}">${esc(it.titulo)}</span></div>`).join('');
        return `${top}<div class="day-body">${rows}</div>
            <div class="day-footer"><span class="tag">${hidden ? `+${hidden} · ` : ''}${_t('Mais detalhes')}</span></div>`;
    }

    return { keyDate, groupByDay, dayItems, dayCellInner, esc };
})();
