function loadContent(section) {
    const content = document.getElementById('content');
    let html = '';

    switch (section) {
        case 'funcionalidades':
    html = `
        <h2>Principais Funcionalidades</h2>
        <p>
            O <strong>U-Control</strong> pode ser instalado em um único dispositivo e controlado remotamente por outros aparelhos conectados à mesma rede local, oferecendo flexibilidade e praticidade no gerenciamento de apresentações.
        </p>
        <p>
            As telas de apresentação destinadas ao público podem ser exibidas de forma remota. Para maior segurança ou estabilidade, o computador pode ser conectado diretamente à tela utilizando um cabo HDMI.
        </p>
        <ul>
            <li><strong>Gerenciar mídia em tempo real:</strong> Controle apresentações, vídeos e imagens com precisão.</li>
            <li><strong>Sincronização de telas:</strong> Sincronize telas de controle e monitor com agilidade, garantindo apresentações impecáveis.</li>
            <li><strong>Interface amigável:</strong> Navegue facilmente por um sistema desenvolvido para simplificar seu fluxo de trabalho.</li>
            <li><strong>Controle em rede local:</strong> Instale o U-Control em uma única máquina e controle-o de outros dispositivos na mesma rede local.</li>
        </ul>`;
    break;

        case 'iniciando':
            html = `
                <h2>Iniciando o Programa</h2>
                <p>Para iniciar o programa, siga os passos abaixo:</p>
                <ul>
                    <li>Certifique-se de que o programa está instalado corretamente.</li>
                    <li>Abra o programa clicando duas vezes no ícone na área de trabalho.</li>
                    <li>Insira suas credenciais de login.</li>
                </ul>`;
            break;
        case 'credenciais':
            html = `
                <h2>Credenciais de Login</h2>
                <p>Para garantir a segurança do sistema, é fundamental que os usuários sejam previamente cadastrados com login e senha. Esse controle de acesso evita que pessoas não autorizadas tenham acesso às funções principais do programa, prevenindo interferências que possam comprometer a apresentação.
                </p>
                <p>
                    Embora o controle de acesso com login e senha seja essencial para proteger as funções principais do programa, algumas rotas podem ser acessadas remotamente sem a necessidade de autenticação. Essas rotas incluem a Tela do Apresentador de Imagens (presenter), o Monitor de Palco e a Tela do Público, garantindo maior praticidade para exibição e acompanhamento durante as apresentações.
                </p>
                <p>
                    Assim que o programa é iniciado, a seguinte página é exibida, solicitando que o usuário insira suas credenciais de acesso:
                </p>
                <div class="image-container">
                    <img src="static/imges_help/Login.png" alt="Login" class="centered-image">
                </div>
                <p>Para o primeiro acesso, utilize as seguintes credenciais:</p>
                <div style="background-color: #f0f8ff; padding: 10px; border-left: 4px solid #007bff; font-family: Arial, sans-serif;">
                    <strong>Usuário:</strong> <code>admin</code><br>
                    <strong>Senha:</strong> <code>1234</code>
                </div>
                <p>
                    Após o primeiro acesso ao sistema utilizando as credenciais padrão (<strong>Usuário: admin</strong>, <strong>Senha: 1234</strong>), recomendamos que o cadastro do usuário "admin" seja removido por questões de segurança. Isso garantirá que apenas usuários cadastrados com permissões específicas possam acessar as funcionalidades principais do programa.
                </p>
                <p>
                    Para eliminar o cadastro do admin, siga os passos abaixo:
                </p>
                <ul>
                    <li>Acesse o painel de controle do sistema clicando na opção 'Links' e em seguida 'Novo Usuário'.</li>
                        <div class="image-container">
                            <img src="static/imges_help/link_novo-usuario.png" alt="Login" class="centered-image">
                        </div>
                    <li>Na página "Usuários Registrados", localize o usuário "admin" na lista de usuários cadastrados e Selecione a opção para <strong><span style="color: red;">remover</span></strong>.</li>
                        <div class="image-container">
                            <img src="static/imges_help/remover_usuario.png" alt="Login" class="centered-image">
                        </div>
                </ul>
                <p>
                    Ao excluir o usuário "admin", o sistema estará mais seguro, garantindo que apenas pessoas autorizadas possam controlar o programa.
                </p>
                <p>
                    Na página "Usuários Registrados", você pode adicionar novos usuários ao sistema de forma simples. Preencha os campos "Nome de Usuário" e "Senha" e clique no botão "Adicionar Usuário" para concluir o cadastro.
                </p>
                        <div class="image-container">
                            <img src="static/imges_help/cadastrar_usuario.png" alt="Login" class="centered-image">
                        </div> `;
            break;
        case 'dicas':
            html = `
                <h2>3. Dicas e Truques</h2>
                <div class="highlight">
                    <p><strong>Dica:</strong> Utilize a combinação de teclas <code>Ctrl + S</code> para salvar rapidamente seu progresso.</p>
                </div>
                <p>Mais algumas dicas úteis:</p>
                <ul>
                    <li>Pressione <code>F1</code> para acessar a ajuda a qualquer momento.</li>
                    <li>Ative o modo escuro nas configurações para reduzir o cansaço visual.</li>
                </ul>`;
            break;
        case 'problemas':
            html = `
                <h2>4. Solução de Problemas</h2>
                <p>Se encontrar problemas, tente as seguintes soluções:</p>
                <ul>
                    <li>Reinicie o programa e tente novamente.</li>
                    <li>Consulte o manual na seção "FAQ".</li>
                    <li>Entre em contato com o suporte técnico pelo e-mail <a href="mailto:suporte@exemplo.com">suporte@exemplo.com</a>.</li>
                </ul>`;
            break;
        case 'contato':
            html = `
                <h2>5. Contato</h2>
                <p>Se precisar de mais ajuda, entre em contato conosco:</p>
                <ul>
                    <li><strong>Suporte:</strong> <a href="mailto:suporte@exemplo.com">suporte@exemplo.com</a></li>
                    <li><strong>Telefone:</strong> (11) 1234-5678</li>
                </ul>`;
            break;
    }

    content.innerHTML = html;
}
