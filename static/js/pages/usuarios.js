// Alternar entre mostrar/ocultar senha
const togglePassword = document.getElementById('togglePassword');
const passwordField = document.getElementById('password');

togglePassword.addEventListener('click', function () {
    // Verifica o tipo do campo de senha e alterna entre 'password' e 'text'
    const type = passwordField.type === 'password' ? 'text' : 'password';
    passwordField.type = type;

    // Alterna o ícone
    this.classList.toggle('fa-eye-slash');
});
