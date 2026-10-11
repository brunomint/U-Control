const section = window.AGENDA_SECTION;
const date = window.AGENDA_DATE;
const orderData = JSON.parse(document.getElementById('order-data').textContent || '{}');
let draggedElement = null;
let searchTimeout = null;
let currentSearchTerm = '';

function parseMusicos(text) {
    return text.split(/\n+/).map(l => l.trim()).filter(Boolean).map(l => {
        const [instrumento='', pessoa=''] = l.split(' - ');
        return { instrumento: instrumento.trim(), pessoa: pessoa.trim() };
    });
}
function parseCantores(text) {
    return text.split(/\n+/).map(l => l.trim()).filter(Boolean);
}
function buildItemListPayload() {
    const songList = document.getElementById('songList');
    const items = Array.from(songList.children);
    return items.map(item => {
        const link = item.querySelector('a');
        const title = link ? link.textContent : null;
        let url = link ? link.getAttribute('href') : null;

        if (item.dataset.isBible === "true") {
            return { isBible: true, reference: item.dataset.reference, title: title };
        }

        if (url) {
            const urlObject = new URL(url, window.location.origin);
            url = urlObject.pathname;
        }

        return url && url !== '/' && url !== '#' ? { url, title } : { anyText: title };
    });
}
function parseFuncoes(text) {
    return text.split(/\n+/).map(l => l.trim()).filter(Boolean).map(l => {
        const [nome='', pessoa=''] = l.split(' - ');
        return { nome: nome.trim(), pessoa: pessoa.trim() };
    });
}
function parseEventosForm() {
    const eventos = [];
    const blocos = document.querySelectorAll('.evento-bloco');

    blocos.forEach(bloco => {
        const titulo = bloco.querySelector('[name$="[titulo]"]')?.value.trim() || '';
        const hora = bloco.querySelector('[name$="[hora]"]')?.value.trim() || '';
        const responsavel = bloco.querySelector('[name$="[responsavel]"]')?.value.trim() || '';
        const obs = bloco.querySelector('[name$="[obs]"]')?.value.trim() || '';

        if (titulo) {
            eventos.push({ titulo, hora, responsavel, obs });
        }
    });

    return eventos;
}
async function save() {
    const btn = document.getElementById('saveBtn');
    const status = document.getElementById('status');
    btn.disabled = true; status.textContent = 'Salvando...'; status.className = 'status';
    const payload = { ...(orderData || {}) };

    if (section === 'louvor') {
        payload.tipo = document.getElementById('tipo').value;
        payload.horario_culto = document.getElementById('horario_culto').value.trim();
        payload.dirigente = document.getElementById('dirigente').value.trim();
        payload.pregador = document.getElementById('pregador').value.trim();
        payload.louvor = payload.louvor || {};
        payload.louvor.musicos = parseMusicos(document.getElementById('musicos').value);
        payload.louvor.cantores = parseCantores(document.getElementById('cantores').value);
        payload.itens = buildItemListPayload();
    } else if (section === 'midia') {
        payload.midia = {
            lider: document.getElementById('midia_lider').value.trim(),
            palco: document.getElementById('midia_palco').value.trim(),
            visual: document.getElementById('midia_visual').value.trim(),
            equipe: parseFuncoes(document.getElementById('midia_team').value),
            obs: document.getElementById('midia_obs').value.trim()
        };
    } else {
        payload.eventos = parseEventosForm();
    }

    try {
        const resp = await fetch(`/api/orders/${date}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (!resp.ok) throw new Error('Falha ao salvar');
        // Culto novo: recarrega pra aba trocar "Novo culto" pelo nome
        if (window.AGENDA_IS_NEW) { location.reload(); return; }
        status.textContent = 'Salvo com sucesso!';
        status.className = 'status ok';
    } catch (e) {
        status.textContent = 'Erro ao salvar';
        status.className = 'status err';
    } finally {
        btn.disabled = false;
    }
}
document.getElementById('saveBtn').addEventListener('click', save);

// Excluir este culto (louvor): apaga o culto, mantém os eventos do dia
document.getElementById('deleteCultoBtn')?.addEventListener('click', async () => {
    if (!confirm('Excluir este culto, com a escala e a ordem do culto? Os eventos do dia continuam.')) return;
    const resp = await fetch(`/api/cultos/${date}`, { method: 'DELETE' });
    if (resp.ok) window.location = `/agenda/${date.slice(0, 10)}/admin`;
    else ucToast('Não deu pra excluir o culto', 'error');
});

// ---- Itens (louvor) helpers ----
async function searchSongs(query) {
    const list = document.getElementById("autocompleteList");
    if (!query || query.trim().length === 0) {
        list.style.display = 'none';
        return;
    }
    currentSearchTerm = query;
    try {
        const response = await fetch(`/search?q=${encodeURIComponent(query)}`);
        const songs = await response.json();
        if (currentSearchTerm !== query) return;
        list.innerHTML = "";
        if (songs.length === 0) {
            list.innerHTML = '<div class="autocomplete-item empty">Nenhuma música encontrada</div>';
            list.style.display = 'block';
            return;
        }
        songs.forEach(song => {
            const item = document.createElement("div");
            item.className = "autocomplete-item";
            item.innerHTML = `
                <div class="song-title">${song.title}</div>
                <div class="song-author">${song.author || 'Autor desconhecido'}</div>
            `;
            item.onclick = () => {
                addSongToList(song);
                list.style.display = 'none';
                document.getElementById("searchInput").value = "";
            };
            list.appendChild(item);
        });
        list.style.display = 'block';
    } catch (error) {
        console.error("Erro ao buscar músicas:", error);
    }
}
function debouncedSearch(query) {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => searchSongs(query), 300);
}

function addSongToList(song) {
    const songList = document.getElementById("songList");
    const songItem = document.createElement("div");
    songItem.className = "song-item";
    songItem.setAttribute("draggable", "true");
    songItem.id = `song-${Date.now()}`;

    const displayText = song.author ? `${song.title} | ${song.author}` : song.title;
    const baseUrl = song.url || (song.id ? `/lyrics/${song.id}` : "#");
    const url = baseUrl.includes('/lyrics/') ? `${baseUrl}?order=${date}` : baseUrl;

    songItem.innerHTML = `
        <span class="drag-handle" aria-hidden="true"><i class="fas fa-grip-vertical"></i></span>
        <div class="song-info">
            <a href="${url}" target="_blank">${displayText}</a>
        </div>
        <button type="button" class="remove-btn" onclick="this.parentElement.remove()" title="Remover" aria-label="Remover"><i class="fas fa-trash-can"></i></button>
    `;

    songItem.ondragstart = (e) => {
        draggedElement = songItem;
        e.dataTransfer.effectAllowed = "move";
    };

    songList.appendChild(songItem);
}

function addToList() {
    const input = document.getElementById("freeTextInput");
    const text = input.value.trim();
    if (!text) return;
    const songList = document.getElementById("songList");
    const item = document.createElement("div");
    item.className = "song-item text-item";
    item.setAttribute("draggable", "true");
    item.id = `text-${Date.now()}`;

    item.innerHTML = `
        <span class="drag-handle" aria-hidden="true"><i class="fas fa-grip-vertical"></i></span>
        <div class="song-info">
            <a href="#">${text}</a>
        </div>
        <button type="button" class="remove-btn" onclick="this.parentElement.remove()" title="Remover" aria-label="Remover"><i class="fas fa-trash-can"></i></button>
    `;

    item.ondragstart = (e) => {
        draggedElement = item;
        e.dataTransfer.effectAllowed = "move";
    };

    songList.appendChild(item);
    input.value = "";
}

function addBibleToList() {
    const input = document.getElementById("bibleRefInput");
    const ref = input.value.trim();
    if (!ref) return;
    const songList = document.getElementById("songList");
    const item = document.createElement("div");
    item.className = "song-item bible";
    item.setAttribute("draggable", "true");
    item.id = `bible-${Date.now()}`;
    item.dataset.isBible = "true";
    item.dataset.reference = ref;

    const url = `/bible?search=${encodeURIComponent(ref)}`;
    item.innerHTML = `
        <div class="song-info">
            <a href="${url}" target="_blank">📖 ${ref}</a>
        </div>
        <button type="button" class="remove-btn" onclick="this.parentElement.remove()" title="Remover" aria-label="Remover"><i class="fas fa-trash-can"></i></button>
    `;

    item.ondragstart = (e) => {
        draggedElement = item;
        e.dataTransfer.effectAllowed = "move";
    };

    songList.appendChild(item);
    input.value = "";
}

function allowDrop(ev) { ev.preventDefault(); }
function drop(ev) {
    ev.preventDefault();
    if (ev.target.classList.contains("song-item") && draggedElement) {
        const target = ev.target;
        const songList = document.getElementById("songList");
        const allItems = Array.from(songList.children);
        const draggedIndex = allItems.indexOf(draggedElement);
        const targetIndex = allItems.indexOf(target);
        if (draggedIndex < targetIndex) {
            songList.insertBefore(draggedElement, target.nextSibling);
        } else {
            songList.insertBefore(draggedElement, target);
        }
    }
}

function loadExistingItens() {
    if (!orderData || !orderData.itens) return;
    orderData.itens.forEach(item => {
        if (item.isBible) {
            const songList = document.getElementById("songList");
            const elem = document.createElement("div");
            elem.className = "song-item bible";
            elem.setAttribute("draggable", "true");
            elem.id = `bible-${Date.now()}-${Math.random()}`;
            elem.dataset.isBible = "true";
            elem.dataset.reference = item.reference;
            elem.innerHTML = `
                <span class="drag-handle" aria-hidden="true"><i class="fas fa-grip-vertical"></i></span>
                <div class="song-info">
                    <a href="/bible?search=${encodeURIComponent(item.reference)}" target="_blank">${item.title || '📖 ' + item.reference}</a>
                </div>
                <button type="button" class="remove-btn" onclick="this.parentElement.remove()" title="Remover" aria-label="Remover"><i class="fas fa-trash-can"></i></button>
            `;
            elem.ondragstart = (e) => { draggedElement = elem; e.dataTransfer.effectAllowed = "move"; };
            songList.appendChild(elem);
        } else if (item.url && item.title) {
            const songList = document.getElementById("songList");
            const elem = document.createElement("div");
            elem.className = "song-item";
            elem.setAttribute("draggable", "true");
            elem.id = `song-${Date.now()}-${Math.random()}`;
            const linkUrl = item.url.includes('/lyrics/') ? `${item.url}?order=${date}` : item.url;
            elem.innerHTML = `
                <span class="drag-handle" aria-hidden="true"><i class="fas fa-grip-vertical"></i></span>
                <div class="song-info">
                    <a href="${linkUrl}" target="_blank">${item.title}</a>
                </div>
                <button type="button" class="remove-btn" onclick="this.parentElement.remove()" title="Remover" aria-label="Remover"><i class="fas fa-trash-can"></i></button>
            `;
            elem.ondragstart = (e) => { draggedElement = elem; e.dataTransfer.effectAllowed = "move"; };
            songList.appendChild(elem);
        } else if (item.anyText || item.title) {
            const songList = document.getElementById("songList");
            const elem = document.createElement("div");
            elem.className = "song-item text-item";
            elem.setAttribute("draggable", "true");
            elem.id = `text-${Date.now()}-${Math.random()}`;
            const text = item.anyText || item.title;
            elem.innerHTML = `
                <span class="drag-handle" aria-hidden="true"><i class="fas fa-grip-vertical"></i></span>
                <div class="song-info">
                    <a href="#">${text}</a>
                </div>
                <button type="button" class="remove-btn" onclick="this.parentElement.remove()" title="Remover" aria-label="Remover"><i class="fas fa-trash-can"></i></button>
            `;
            elem.ondragstart = (e) => { draggedElement = elem; e.dataTransfer.effectAllowed = "move"; };
            songList.appendChild(elem);
        }
    });
}

// Listeners para busca/enter
document.addEventListener("DOMContentLoaded", () => {
    const searchInput = document.getElementById("searchInput");
    if (searchInput) {
        searchInput.addEventListener("input", (e) => debouncedSearch(e.target.value.trim()));
        searchInput.addEventListener("keydown", (e) => { if (e.key === 'Escape') document.getElementById("autocompleteList").style.display = 'none'; });
    }
    document.addEventListener("click", (e) => {
        if (!e.target.closest(".search-box")) {
            const list = document.getElementById("autocompleteList");
            if (list) list.style.display = 'none';
        }
    });
    const freeText = document.getElementById("freeTextInput");
    const bibleInput = document.getElementById("bibleRefInput");
    if (freeText) freeText.addEventListener("keydown", (e) => { if (e.key === 'Enter') { e.preventDefault(); addToList(); } });
    if (bibleInput) bibleInput.addEventListener("keydown", (e) => { if (e.key === 'Enter') { e.preventDefault(); addBibleToList(); } });
    loadExistingItens();
});
function addEvento() {
    const container = document.getElementById('eventos-container');
    const index = container.children.length;

    container.insertAdjacentHTML('beforeend', `
        <div class="evento-bloco">
            <label>Título do evento</label>
            <input name="eventos[${index}][titulo]">

            <label>Horário</label>
            <div class="hour-presets">
                <button type="button" class="hour-btn" onclick="setHora(this,'18:40')">18:40</button>
                <button type="button" class="hour-btn" onclick="setHora(this,'19:00')">19:00</button>
                <button type="button" class="hour-btn" onclick="setHora(this,'19:30')">19:30</button>
                <button type="button" class="hour-btn" onclick="setHora(this,'20:00')">20:00</button>
            </div>
            <input name="eventos[${index}][hora]" placeholder="Ex.: 19:30">

            <label>Responsáveis</label>
            <textarea name="eventos[${index}][responsavel]"></textarea>

            <label>Observações</label>
            <textarea name="eventos[${index}][obs]"></textarea>

            <button type="button" class="uc-btn uc-btn-ghost uc-btn-sm uc-danger-text evento-remove" onclick="this.closest('.evento-bloco').remove()"><i class="fas fa-trash-can"></i> Remover evento</button>
        </div>
    `);
}
// ── MODELOS DE ESCALA ────────────────────────────────────────────
function getFieldsSnapshot() {
    if (section === 'midia') return {
        lider:  document.getElementById('midia_lider').value,
        palco:  document.getElementById('midia_palco').value,
        visual: document.getElementById('midia_visual').value,
        equipe: document.getElementById('midia_team').value,
        obs:    document.getElementById('midia_obs').value
    };
    if (section === 'louvor') return {
        dirigente: document.getElementById('dirigente').value,
        pregador:  document.getElementById('pregador').value,
        musicos:   document.getElementById('musicos').value,
        cantores:  document.getElementById('cantores').value
    };
    return {};
}

function applyTemplate(fields) {
    if (section === 'midia') {
        document.getElementById('midia_lider').value  = fields.lider  || '';
        document.getElementById('midia_palco').value  = fields.palco  || '';
        document.getElementById('midia_visual').value = fields.visual || '';
        document.getElementById('midia_team').value   = fields.equipe || '';
        document.getElementById('midia_obs').value    = fields.obs    || '';
    }
    if (section === 'louvor') {
        document.getElementById('dirigente').value = fields.dirigente || '';
        document.getElementById('pregador').value  = fields.pregador  || '';
        document.getElementById('musicos').value   = fields.musicos   || '';
        document.getElementById('cantores').value  = fields.cantores  || '';
    }
}

// ── COPIAR MÊS ────────────────────────────────────────────────────
let copiarFieldsByDow = {}; // { "0|1": {tipo, fields, seq}, "0|2": ..., } — dia da semana | nº do culto

const NOMES_DIA = ['Dom','Seg','Ter','Qua','Qui','Sex','Sáb'];
const NOMES_MES = ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez'];

function isoDate(d) {
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}

function datasDoMesPorDow(ano, mes, dow) {
    const datas = [];
    const d = new Date(ano, mes, 1);
    while (d.getMonth() === mes) {
        if (d.getDay() === dow) datas.push(new Date(d));
        d.setDate(d.getDate() + 1);
    }
    return datas;
}

function temDadosSecao(order) {
    if (section === 'louvor') return !!(order.dirigente || order.louvor);
    if (section === 'eventos') return Array.isArray(order.eventos) && order.eventos.length > 0;
    return !!order[section];
}

function extrairFields(order) {
    if (section === 'louvor') {
        return { dirigente: order.dirigente || '', pregador: order.pregador || '',
                 tipo: order.tipo || '', horario_culto: order.horario_culto || '',
                 louvor: order.louvor || {} };
    }
    return order[section];
}

function abrirModalCopiar() {
    const anoAtual = new Date().getFullYear();
    ['copiar-orig-ano','copiar-dest-ano'].forEach(id => {
        document.getElementById(id).innerHTML = [anoAtual-1, anoAtual, anoAtual+1]
            .map(y => `<option value="${y}"${y===anoAtual?' selected':''}>${y}</option>`).join('');
    });

    const [pageYear, pageMonth] = date.split('-').map(Number);
    let origMes = pageMonth - 2;
    let origAno = pageYear;
    if (origMes < 0) { origMes += 12; origAno--; }
    document.getElementById('copiar-orig-mes').value = origMes;
    document.getElementById('copiar-orig-ano').value = origAno;
    document.getElementById('copiar-dest-mes').value = pageMonth - 1;
    document.getElementById('copiar-dest-ano').value = pageYear;

    document.getElementById('copiar-result').textContent = '';

    const onChange = () => renderCopiarGrid();
    ['copiar-orig-mes','copiar-orig-ano','copiar-dest-mes','copiar-dest-ano']
        .forEach(id => { document.getElementById(id).onchange = onChange; });

    renderCopiarGrid();
    document.getElementById('modal-copiar').style.display = 'flex';
}

function fecharModalCopiar() {
    document.getElementById('modal-copiar').style.display = 'none';
}

async function renderCopiarGrid() {
    const grid = document.getElementById('copiar-grid');
    grid.innerHTML = '<div style="color:var(--uc-muted);font-size:13px;padding:8px">Carregando…</div>';
    copiarFieldsByDow = {};

    const origMes = parseInt(document.getElementById('copiar-orig-mes').value);
    const origAno = parseInt(document.getElementById('copiar-orig-ano').value);
    const destMes = parseInt(document.getElementById('copiar-dest-mes').value);
    const destAno = parseInt(document.getElementById('copiar-dest-ano').value);
    const prefixo = `${origAno}-${String(origMes+1).padStart(2,'0')}`;

    try {
        const orders = await fetch('/api/orders').then(r => r.json());

        // agrupa por dia da semana e nº do culto no dia (chave
        // YYYY-MM-DD-N), pega o primeiro de cada
        Object.entries(orders)
            .filter(([d, o]) => d.startsWith(prefixo) && temDadosSecao(o))
            .sort(([a],[b]) => a.localeCompare(b))
            .forEach(([d, o]) => {
                const dow = new Date(d.slice(0, 10) + 'T12:00:00').getDay();
                const seq = d.length > 10 ? Number(d.slice(11)) : 1;
                const grupo = `${dow}|${seq}`;
                if (!(grupo in copiarFieldsByDow)) {
                    copiarFieldsByDow[grupo] = { tipo: o.tipo || NOMES_DIA[dow], fields: extrairFields(o), seq };
                }
            });

        if (!Object.keys(copiarFieldsByDow).length) {
            grid.innerHTML = `<div style="color:var(--uc-danger);font-size:13px;padding:8px">Nenhuma escala de ${section} encontrada em ${prefixo.replace('-','/')}.</div>`;
            return;
        }

        // para cada dia da semana encontrado, gera checkboxes no mês destino
        let html = '';
        Object.entries(copiarFieldsByDow)
            .sort(([a],[b]) => a.localeCompare(b))
            .forEach(([grupo, info]) => {
                const dow = Number(grupo.split('|')[0]);
                const datas = datasDoMesPorDow(destAno, destMes, dow);
                if (!datas.length) return;
                const qual = info.seq > 1 ? ` (${info.seq}º culto do dia)` : '';
                html += `<div class="copiar-group">
                    <div class="copiar-group-title">${NOMES_DIA[dow]}s — ${info.tipo}${qual}</div>
                    <div class="copiar-group-dates">${datas.map(d => {
                        const key = info.seq > 1 ? `${isoDate(d)}-${info.seq}` : isoDate(d);
                        return `<label class="mes-check"><input type="checkbox" name="copiar-date" data-grupo="${grupo}" value="${key}" checked><span>${d.getDate()} ${NOMES_MES[d.getMonth()]}</span></label>`;
                    }).join('')}</div>
                </div>`;
            });

        grid.innerHTML = html || `<div style="color:var(--uc-muted);font-size:13px;padding:8px">Sem datas correspondentes em ${NOMES_MES[destMes]}/${destAno}.</div>`;
    } catch {
        grid.innerHTML = '<div style="color:var(--uc-danger);font-size:13px;padding:8px">Erro ao carregar dados.</div>';
    }
}

async function executarCopiar() {
    const result = document.getElementById('copiar-result');
    const btn = document.querySelector('#modal-copiar .mes-apply-btn');
    const checked = [...document.querySelectorAll('input[name=copiar-date]:checked')];
    if (!checked.length) { result.textContent = 'Selecione ao menos uma data.'; result.style.color = 'var(--uc-danger)'; return; }

    // agrupa datas selecionadas por dia da semana + culto
    const porDow = {};
    checked.forEach(el => {
        const grupo = el.dataset.grupo;
        (porDow[grupo] = porDow[grupo] || []).push(el.value);
    });

    btn.disabled = true; btn.textContent = 'Aplicando…';
    let total = 0, erro = false;

    try {
        for (const [grupo, datas] of Object.entries(porDow)) {
            const info = copiarFieldsByDow[grupo];
            if (!info) continue;
            const res = await fetch('/api/section-templates/apply-month', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ section, fields: info.fields, dates: datas })
            });
            if (res.ok) total += (await res.json()).applied;
            else erro = true;
        }
        result.textContent = erro
            ? 'Erro ao aplicar em algumas datas.'
            : `Escala copiada para ${total} data${total !== 1 ? 's' : ''}!`;
        result.style.color = erro ? 'var(--uc-danger)' : 'var(--uc-ok)';
    } catch {
        result.textContent = 'Sem conexão com o servidor.';
        result.style.color = 'var(--uc-danger)';
    }
    btn.disabled = false; btn.textContent = 'Copiar e aplicar';
}

function setHora(btn, hora) {

// 1️⃣ Tenta aplicar no contexto de EVENTOS
const blocoEvento = btn.closest('.evento-bloco');
if (blocoEvento) {
    const inputEvento = blocoEvento.querySelector('[name$="[hora]"]');
    if (inputEvento) {
        inputEvento.value = hora;
        return;
    }
}

// 2️⃣ Fallback: horário do LOUVOR
const inputCulto = document.getElementById('horario_culto');
if (inputCulto) {
    inputCulto.value = hora;
}
}
