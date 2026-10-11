// Componentes de interface compartilhados do tema único (carregado pelo
// base.html nas páginas com app_theme). Estilos em static/css/app.css.

// Aviso flutuante no canto da tela. type: 'success' (padrão) ou 'error'.
window.ucToast = function (message, type) {
    document.querySelectorAll('.uc-toast').forEach(el => el.remove());
    const isError = type === 'error';
    const el = document.createElement('div');
    el.className = 'uc-toast' + (isError ? ' error' : '');
    el.setAttribute('role', 'status');
    const icon = document.createElement('i');
    icon.className = 'fas ' + (isError ? 'fa-triangle-exclamation' : 'fa-circle-check');
    const text = document.createElement('span');
    text.textContent = message;
    el.append(icon, text);
    document.body.appendChild(el);
    setTimeout(() => el.remove(), isError ? 4500 : 3000);
};

// Campo "Tipo de culto" (templates/_tipo_culto.html): "Outro" mostra o
// campo de nome; o valor do tipo é o nome digitado (ou "Outro" se vazio).
window.ucTipoCulto = function (id) {
    const select = document.getElementById(id);
    const nome = document.getElementById(id + 'Outro');
    if (select.value === 'Outro' && nome && nome.value.trim()) return nome.value.trim();
    return select.value;
};
document.addEventListener('change', e => {
    const select = e.target.closest('select[data-outro]');
    if (!select) return;
    const nome = document.getElementById(select.dataset.outro);
    nome.hidden = select.value !== 'Outro';
    if (!nome.hidden) nome.focus();
});
