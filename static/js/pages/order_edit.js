const CONFIG = JSON.parse(document.getElementById('order-edit-data').textContent);

// Variáveis globais
let draggedElement = null;
let searchTimeout = null;
let currentSearchTerm = '';
const originalDate = CONFIG.date;
const isNew = CONFIG.isNew;

// Chave do culto: o campo mostra só a data; se ela não mudou, mantém a
// chave original (YYYY-MM-DD-N quando é o 2º, 3º... culto do dia)
function orderKey() {
    const value = document.getElementById('orderDate').value;
    return value === originalDate.slice(0, 10) ? originalDate : value;
}

// Toast
function showToast(message, type = 'success') {
    window.ucToast(message, type);
}

// Busca de músicas
async function searchSongs(query) {
    const list = document.getElementById("autocompleteList");

    if (!query || query.trim().length === 0) {
        list.classList.remove('show');
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
            list.classList.add('show');
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
                list.classList.remove('show');
                document.getElementById("searchInput").value = "";
            };
            list.appendChild(item);
        });

        list.classList.add('show');
    } catch (error) {
        console.error("Erro ao buscar músicas:", error);
    }
}

function debouncedSearch(query) {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => searchSongs(query), 300);
}

// Adicionar música à lista
function addSongToList(song) {
    const songList = document.getElementById("songList");
    const songItem = document.createElement("div");
    songItem.className = "song-item";
    songItem.setAttribute("draggable", "true");
    songItem.id = `song-${Date.now()}`;

    const displayText = song.author ? `${song.title} | ${song.author}` : song.title;
    const baseUrl = song.url || (song.id ? `/lyrics/${song.id}` : "#");
    const orderDate = orderKey();
    const url = baseUrl.includes('/lyrics/') ? `${baseUrl}?order=${orderDate}` : baseUrl;

    songItem.innerHTML = `
        <span class="drag-handle" title="Arraste para reordenar" aria-hidden="true"><i class="fas fa-grip-vertical"></i></span>
        <div class="song-info">
            <a href="${url}" target="_blank">${displayText}</a>
        </div>
        <button type="button" class="subst-btn" onclick="substituirMusica(this)"><i class="fas fa-right-left"></i> Substituir</button>
        <button type="button" class="remove-btn" onclick="this.parentElement.remove()" title="Remover da ordem" aria-label="Remover da ordem"><i class="fas fa-trash-can"></i></button>
    `;

    songItem.ondragstart = (e) => {
        draggedElement = songItem;
        e.dataTransfer.effectAllowed = "move";
    };

    songList.appendChild(songItem);
    showToast('Música adicionada!');
}

// Adicionar texto livre
function addToList() {
    const input = document.getElementById("freeTextInput");
    const text = input.value.trim();

    if (!text) {
        showToast('Digite algum texto', 'error');
        return;
    }

    const songList = document.getElementById("songList");
    const item = document.createElement("div");
    item.className = "song-item text-item";
    item.setAttribute("draggable", "true");
    item.id = `text-${Date.now()}`;

    item.innerHTML = `
        <span class="drag-handle" title="Arraste para reordenar" aria-hidden="true"><i class="fas fa-grip-vertical"></i></span>
        <div class="song-info">
            <a href="#">${text}</a>
        </div>
        <button type="button" class="remove-btn" onclick="this.parentElement.remove()" title="Remover da ordem" aria-label="Remover da ordem"><i class="fas fa-trash-can"></i></button>
    `;

    item.ondragstart = (e) => {
        draggedElement = item;
        e.dataTransfer.effectAllowed = "move";
    };

    songList.appendChild(item);
    input.value = "";
    showToast('Item adicionado!');
}

// Adicionar referência bíblica
function addBibleToList() {
    const input = document.getElementById("bibleRefInput");
    const ref = input.value.trim();

    if (!ref) {
        showToast('Digite uma referência bíblica', 'error');
        return;
    }

    const songList = document.getElementById("songList");
    const item = document.createElement("div");
    item.className = "song-item bible";
    item.setAttribute("draggable", "true");
    item.id = `bible-${Date.now()}`;
    item.dataset.isBible = "true";
    item.dataset.reference = ref;

    // Gerar URL da Bíblia
    const url = `/bible?search=${encodeURIComponent(ref)}`;

    item.innerHTML = `
        <span class="drag-handle" title="Arraste para reordenar" aria-hidden="true"><i class="fas fa-grip-vertical"></i></span>
        <div class="song-info">
            <a href="${url}" target="_blank">📖 ${ref}</a>
        </div>
        <button type="button" class="remove-btn" onclick="this.parentElement.remove()" title="Remover da ordem" aria-label="Remover da ordem"><i class="fas fa-trash-can"></i></button>
    `;

    item.ondragstart = (e) => {
        draggedElement = item;
        e.dataTransfer.effectAllowed = "move";
    };

    songList.appendChild(item);
    input.value = "";
    showToast('Referência bíblica adicionada!');
}

// Drag and drop
function allowDrop(ev) {
    ev.preventDefault();
}

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

// Salvar ordem
async function saveOrder() {
    const date = orderKey();

    if (!date) {
        showToast('Selecione uma data', 'error');
        return;
    }

    const songList = document.getElementById("songList");
    const items = Array.from(songList.children);

    const itens = items.map(item => {
        const link = item.querySelector("a");
        const title = link ? link.textContent : null;
        // href="#" é item de texto livre — link.href resolveria pra URL da
        // própria página e o texto seria salvo como link pra /order/<data>.
        let url = link && link.getAttribute('href') !== '#' ? link.href : null;

        if (item.dataset.isBible === "true") {
            return {
                isBible: true,
                reference: item.dataset.reference,
                title: title
            };
        }

        if (url) {
            const urlObject = new URL(url, window.location.origin);
            url = urlObject.pathname;
        }

        return url && url !== '/' && url !== '#' ? { url, title } : { anyText: title };
    });

    // Carrega dados existentes para preservar campos de outras seções (louvor, mídia, eventos)
    let existing = {};
    try {
        const res = await fetch(`/api/orders/${date}`);
        if (res.ok) existing = await res.json();
    } catch(e) {}

    const orderData = {
        ...existing,
        tipo: document.getElementById("orderType").value,
        horario: document.getElementById("orderTime").value,
        dirigente: document.getElementById("orderDirigente").value,
        pregador: document.getElementById("orderPregador").value,
        tema: document.getElementById("orderTema").value,
        itens: itens
    };

    try {
        const response = await fetch(`/api/orders/${date}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(orderData)
        });

        if (response.ok) {
            showToast('Ordem salva com sucesso!', 'success');

            // Se a data mudou, redireciona para a nova
            if (date !== originalDate && !isNew) {
                // Deleta a ordem antiga
                await fetch(`/api/orders/${originalDate}`, { method: 'DELETE' });
            }
            setTimeout(() => {
                window.location.href = `/order/${date}`;
            }, 1500);
        } else {
            showToast('Erro ao salvar ordem', 'error');
        }
    } catch (error) {
        console.error("Erro:", error);
        showToast('Erro ao salvar ordem', 'error');
    }
}

// Deletar ordem
async function deleteOrder() {
    if (!confirm('Tem certeza que deseja excluir esta ordem de culto?')) {
        return;
    }

    try {
        const response = await fetch(`/api/orders/${originalDate}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            showToast('Ordem excluída!');
            setTimeout(() => {
                window.location.href = '/order';
            }, 1500);
        } else {
            showToast('Erro ao excluir ordem', 'error');
        }
    } catch (error) {
        console.error("Erro:", error);
        showToast('Erro ao excluir ordem', 'error');
    }
}

// Gerar PDF
function createPDF() {
    const { jsPDF } = window.jspdf;
    if (!jsPDF) {
        showToast('Erro ao carregar biblioteca PDF', 'error');
        return;
    }

    const doc = new jsPDF();
    const songList = document.getElementById('songList');

    const content = Array.from(songList.children)
        .map(child => {
            const link = child.querySelector('a');
            return link ? link.textContent.trim() : '';
        })
        .filter(text => text)
        .join('\n');

    if (!content) {
        showToast('Adicione itens à ordem primeiro', 'error');
        return;
    }

    const date = document.getElementById("orderDate").value;
    const tipo = document.getElementById("orderType").value;
    const dirigente = document.getElementById("orderDirigente").value;

    // Título
    doc.setFontSize(18);
    doc.setFont('helvetica', 'bold');
    doc.text('Ordem do Culto', 105, 20, { align: 'center' });

    // Metadados
    doc.setFontSize(12);
    doc.setFont('helvetica', 'normal');
    const formattedDate = new Date(date + 'T12:00:00').toLocaleDateString('pt-BR');
    doc.text(`Data: ${formattedDate} | ${tipo}`, 105, 30, { align: 'center' });
    if (dirigente) {
        doc.text(`Dirigente: ${dirigente}`, 105, 38, { align: 'center' });
    }

    // Linha separadora
    doc.setDrawColor(0, 188, 212);
    doc.line(20, 45, 190, 45);

    // Conteúdo
    doc.setFontSize(11);
    const lines = doc.splitTextToSize(content, 170);
    doc.text(lines, 20, 55);

    doc.save(`ordem_${date}.pdf`);
    showToast('PDF gerado!');
}

// Carregar ordem existente
async function loadExistingOrder() {
    if (CONFIG.itens) {
        const itens = CONFIG.itens;

        itens.forEach(item => {
            if (item.isBible) {
                const songList = document.getElementById("songList");
                const elem = document.createElement("div");
                elem.className = "song-item bible";
                elem.setAttribute("draggable", "true");
                elem.id = `bible-${Date.now()}-${Math.random()}`;
                elem.dataset.isBible = "true";
                elem.dataset.reference = item.reference;

                elem.innerHTML = `
                    <span class="drag-handle" title="Arraste para reordenar" aria-hidden="true"><i class="fas fa-grip-vertical"></i></span>
                    <div class="song-info">
                        <a href="/bible?search=${encodeURIComponent(item.reference)}" target="_blank">${item.title || '📖 ' + item.reference}</a>
                    </div>
                    <button type="button" class="remove-btn" onclick="this.parentElement.remove()" title="Remover da ordem" aria-label="Remover da ordem"><i class="fas fa-trash-can"></i></button>
                `;

                elem.ondragstart = (e) => {
                    draggedElement = elem;
                    e.dataTransfer.effectAllowed = "move";
                };

                songList.appendChild(elem);
            } else if (item.url && item.title) {
                const songList = document.getElementById("songList");
                const elem = document.createElement("div");
                elem.className = "song-item";
                elem.setAttribute("draggable", "true");
                elem.id = `song-${Date.now()}-${Math.random()}`;

                // Adiciona parâmetro order se for link de lyrics
                const orderDate = orderKey();
                const linkUrl = item.url.includes('/lyrics/') ? `${item.url}?order=${orderDate}` : item.url;

                elem.innerHTML = `
                    <span class="drag-handle" title="Arraste para reordenar" aria-hidden="true"><i class="fas fa-grip-vertical"></i></span>
                    <div class="song-info">
                        <a href="${linkUrl}" target="_blank">${item.title}</a>
                    </div>
                    <button type="button" class="subst-btn" onclick="substituirMusica(this)"><i class="fas fa-right-left"></i> Substituir</button>
                    <button type="button" class="remove-btn" onclick="this.parentElement.remove()" title="Remover da ordem" aria-label="Remover da ordem"><i class="fas fa-trash-can"></i></button>
                `;

                elem.ondragstart = (e) => {
                    draggedElement = elem;
                    e.dataTransfer.effectAllowed = "move";
                };

                songList.appendChild(elem);
            } else if (item.anyText || item.title) {
                const songList = document.getElementById("songList");
                const elem = document.createElement("div");
                elem.className = "song-item text-item";
                elem.setAttribute("draggable", "true");
                elem.id = `text-${Date.now()}-${Math.random()}`;

                const text = item.anyText || item.title;
                elem.innerHTML = `
                    <span class="drag-handle" title="Arraste para reordenar" aria-hidden="true"><i class="fas fa-grip-vertical"></i></span>
                    <div class="song-info">
                        <a href="#">${text}</a>
                    </div>
                    <button type="button" class="remove-btn" onclick="this.parentElement.remove()" title="Remover da ordem" aria-label="Remover da ordem"><i class="fas fa-trash-can"></i></button>
                `;

                elem.ondragstart = (e) => {
                    draggedElement = elem;
                    e.dataTransfer.effectAllowed = "move";
                };

                songList.appendChild(elem);
            }
        });
    }
}

// Event listeners
document.addEventListener("DOMContentLoaded", loadExistingOrder);

document.getElementById("searchInput").addEventListener("input", (e) => {
    debouncedSearch(e.target.value.trim());
});

document.getElementById("searchInput").addEventListener("keydown", (e) => {
    if (e.key === 'Escape') {
        document.getElementById("autocompleteList").classList.remove('show');
    }
});

document.addEventListener("click", (e) => {
    if (!e.target.closest(".search-box")) {
        document.getElementById("autocompleteList").classList.remove('show');
    }
});

// Enter para adicionar texto/bíblia
document.getElementById("freeTextInput").addEventListener("keydown", (e) => {
    if (e.key === 'Enter') addToList();
});

document.getElementById("bibleRefInput").addEventListener("keydown", (e) => {
    if (e.key === 'Enter') addBibleToList();
});

// ── SUBSTITUIR MÚSICA ────────────────────────────────────────
function substituirMusica(btn) {
    const item = btn.closest('.song-item');
    const songInfo = item.querySelector('.song-info');
    const existing = item.querySelector('.inline-search');
    if (existing) { existing.remove(); songInfo.style.display = ''; return; }

    const searchDiv = document.createElement('div');
    searchDiv.className = 'inline-search';
    searchDiv.innerHTML = `
        <div class="inline-search-wrap">
            <input type="text" class="inline-search-input" placeholder="Buscar música substituta...">
            <button type="button" class="inline-cancel-btn" aria-label="Cancelar substituição" onclick="this.closest('.inline-search').remove(); this.closest('.song-item').querySelector('.song-info').style.display=''">✕</button>
        </div>
        <div class="inline-ac"></div>`;

    songInfo.style.display = 'none';
    item.appendChild(searchDiv);

    const input = searchDiv.querySelector('.inline-search-input');
    const ac = searchDiv.querySelector('.inline-ac');
    input.focus();

    let searchTimer;
    input.addEventListener('input', () => {
        clearTimeout(searchTimer);
        const q = input.value.trim();
        if (!q) { ac.classList.remove('show'); return; }
        searchTimer = setTimeout(async () => {
            const res = await fetch(`/search?q=${encodeURIComponent(q)}`);
            const songs = await res.json();
            if (!songs.length) {
                ac.innerHTML = '<div class="inline-ac-item empty">Nenhuma música encontrada</div>';
                ac.classList.add('show'); return;
            }
            ac.innerHTML = songs.map(s => {
                const t = s.author ? `${s.title} | ${s.author}` : s.title;
                return `<div class="inline-ac-item" data-url="/lyrics/${s.id}" data-title="${t.replace(/"/g,'&quot;')}">${t}</div>`;
            }).join('');
            ac.classList.add('show');
            ac.querySelectorAll('.inline-ac-item').forEach(it => {
                it.onclick = () => {
                    const orderDate = orderKey();
                    const url = `${it.dataset.url}?order=${orderDate}`;
                    const link = item.querySelector('.song-info a');
                    link.href = url;
                    link.textContent = it.dataset.title;
                    songInfo.style.display = '';
                    searchDiv.remove();
                };
            });
        }, 280);
    });
}

// ── MODELOS REUTILIZÁVEIS ─────────────────────────────────────
function getOrderItems() {
    const songList = document.getElementById("songList");
    return Array.from(songList.children).map(item => {
        const link = item.querySelector("a");
        const title = link ? link.textContent.trim() : null;
        if (item.dataset.isBible === "true") {
            return { isBible: true, reference: item.dataset.reference, title };
        }
        let url = link && link.getAttribute('href') !== '#' ? link.href : null;
        if (url) url = new URL(url, window.location.origin).pathname;
        return url ? { url, title } : { anyText: title };
    });
}

function abrirModalTemplates() {
    document.getElementById('modal-templates').style.display = 'flex';
    document.getElementById('tpl-nome').value = '';
    renderTemplateList();
}

function fecharModalTemplates() {
    document.getElementById('modal-templates').style.display = 'none';
}

async function renderTemplateList() {
    const res = await fetch('/api/templates');
    const tpls = await res.json();
    const names = Object.keys(tpls);
    const el = document.getElementById('tpl-list');
    if (!names.length) {
        el.innerHTML = '<div class="tpl-empty">Nenhum modelo salvo ainda.</div>';
        return;
    }
    el.innerHTML = names.map(n => `
        <div class="tpl-item">
            <span>${n}</span>
            <button class="tpl-load-btn" data-name="${n.replace(/"/g,'&quot;')}" onclick="carregarModelo(this.dataset.name)">Carregar</button>
            <button class="tpl-del-btn"  data-name="${n.replace(/"/g,'&quot;')}" onclick="deletarModelo(this.dataset.name)">✕</button>
        </div>`).join('');
}

async function salvarComoModelo() {
    const name = document.getElementById('tpl-nome').value.trim();
    if (!name) { showToast('Digite um nome para o modelo.'); return; }
    const items = getOrderItems();
    if (!items.length) { showToast('A lista está vazia.'); return; }
    await fetch('/api/templates', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, items })
    });
    document.getElementById('tpl-nome').value = '';
    showToast('Modelo salvo!');
    renderTemplateList();
}

async function carregarModelo(name) {
    if (!confirm(`Substituir a lista atual pelo modelo "${name}"?`)) return;
    const res = await fetch('/api/templates');
    const tpls = await res.json();
    const items = tpls[name];
    if (!items) return;
    document.getElementById('songList').innerHTML = '';
    items.forEach(item => {
        if (item.isBible) {
            addBibleItemToList(item.reference, item.title);
        } else if (item.url) {
            addSongItemToList(item.url, item.title);
        } else if (item.anyText) {
            addTextItemToList(item.anyText);
        }
    });
    fecharModalTemplates();
    showToast(`Modelo "${name}" carregado.`);
}

async function deletarModelo(name) {
    if (!confirm(`Excluir o modelo "${name}"?`)) return;
    await fetch(`/api/templates/${encodeURIComponent(name)}`, { method: 'DELETE' });
    renderTemplateList();
}

function addSongItemToList(url, title) {
    const songList = document.getElementById("songList");
    const item = document.createElement("div");
    item.className = "song-item";
    item.setAttribute("draggable", "true");
    item.id = `song-${Date.now()}`;
    const orderDate = orderKey();
    const fullUrl = url.includes('/lyrics/') ? `${url}?order=${orderDate}` : url;
    item.innerHTML = `
        <span class="drag-handle" title="Arraste para reordenar" aria-hidden="true"><i class="fas fa-grip-vertical"></i></span>
        <div class="song-info">
            <a href="${fullUrl}" target="_blank">${title || ''}</a>
        </div>
        <button type="button" class="subst-btn" onclick="substituirMusica(this)"><i class="fas fa-right-left"></i> Substituir</button>
        <button type="button" class="remove-btn" onclick="this.parentElement.remove()" title="Remover da ordem" aria-label="Remover da ordem"><i class="fas fa-trash-can"></i></button>`;
    item.ondragstart = (e) => { draggedElement = item; e.dataTransfer.effectAllowed = "move"; };
    songList.appendChild(item);
}

function addBibleItemToList(reference, title) {
    const songList = document.getElementById("songList");
    const item = document.createElement("div");
    item.className = "song-item bible";
    item.setAttribute("draggable", "true");
    item.id = `bible-${Date.now()}`;
    item.dataset.isBible = "true";
    item.dataset.reference = reference;
    const url = `/bible?search=${encodeURIComponent(reference)}`;
    item.innerHTML = `
        <span class="drag-handle" title="Arraste para reordenar" aria-hidden="true"><i class="fas fa-grip-vertical"></i></span>
        <div class="song-info">
            <a href="${url}" target="_blank">📖 ${title || reference}</a>
        </div>
        <button type="button" class="remove-btn" onclick="this.parentElement.remove()" title="Remover da ordem" aria-label="Remover da ordem"><i class="fas fa-trash-can"></i></button>`;
    item.ondragstart = (e) => { draggedElement = item; e.dataTransfer.effectAllowed = "move"; };
    songList.appendChild(item);
}

function addTextItemToList(text) {
    const songList = document.getElementById("songList");
    const item = document.createElement("div");
    item.className = "song-item text-item";
    item.setAttribute("draggable", "true");
    item.id = `text-${Date.now()}-${Math.random()}`;
    item.innerHTML = `
        <span class="drag-handle" title="Arraste para reordenar" aria-hidden="true"><i class="fas fa-grip-vertical"></i></span>
        <div class="song-info">
            <a href="#"></a>
        </div>
        <button type="button" class="remove-btn" onclick="this.parentElement.remove()" title="Remover da ordem" aria-label="Remover da ordem"><i class="fas fa-trash-can"></i></button>`;
    item.querySelector('a').textContent = text;
    item.ondragstart = (e) => { draggedElement = item; e.dataTransfer.effectAllowed = "move"; };
    songList.appendChild(item);
}
