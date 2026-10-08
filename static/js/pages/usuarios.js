// Mostrar/ocultar a senha no formulário de novo usuário
const togglePassword = document.getElementById('togglePassword');
const passwordField = document.getElementById('password');

togglePassword.addEventListener('click', function () {
    const show = passwordField.type === 'password';
    passwordField.type = show ? 'text' : 'password';
    this.setAttribute('aria-label', show ? 'Ocultar senha' : 'Mostrar senha');
    this.querySelector('i').className = show ? 'fas fa-eye-slash' : 'fas fa-eye';
});

// Cada linha tem 3 estados: normal, trocando senha e confirmando remoção.
// Só um aparece por vez; abrir uma linha fecha as outras.
function setRowState(row, state) {
    row.querySelectorAll('.row-actions').forEach(el => { el.hidden = el.dataset.state !== state; });
    if (state === 'password') row.querySelector('.pass-input').focus();
}

document.querySelectorAll('tr[data-user-row]').forEach(row => {
    row.addEventListener('click', e => {
        const btn = e.target.closest('button[data-action]');
        if (!btn) return;
        const action = btn.dataset.action;
        document.querySelectorAll('tr[data-user-row]').forEach(other => {
            if (other !== row) setRowState(other, 'idle');
        });
        setRowState(row, action === 'cancel' ? 'idle' : action);
    });
});

document.addEventListener('keydown', e => {
    if (e.key === 'Escape') document.querySelectorAll('tr[data-user-row]').forEach(row => setRowState(row, 'idle'));
});
