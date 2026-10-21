// Conteúdo da página /help. Só texto: as capturas de tela antigas mostravam
// nomes de usuário reais e ensinavam uma senha padrão que não existe mais.
const HELP_SECTIONS = {
    funcionalidades: `
        <h2>Principais funcionalidades</h2>
        <p>Um computador roda o U-Control, e os outros aparelhos da mesma rede (celular, tablet, outro PC) abrem o controle ou as telas pelo navegador. Não precisa de internet durante o culto.</p>
        <ul>
            <li><strong>Controle:</strong> letras com cifra, versículos, fotos e vídeos vão para o telão com um toque.</li>
            <li><strong>Telas sincronizadas:</strong> o telão do público e o retorno de palco acompanham o Controle.</li>
            <li><strong>Preparação:</strong> monte a ordem do culto, cadastre músicas e organize as escalas antes.</li>
        </ul>
        <p>O telão pode ficar no próprio computador do U-Control (cabo HDMI, mais estável) ou em outro aparelho da rede.</p>`,

    primeiro: `
        <h2>Primeiro acesso e usuários</h2>
        <p>Numa instalação nova ainda não existe nenhum usuário: a tela de login pede para <strong>criar o primeiro</strong> (nome, senha e a senha de novo). Esse pedido some assim que o primeiro usuário é criado.</p>
        <div class="callout">Crie esse usuário logo depois de instalar: enquanto ele não existe, quem abrir a tela de login primeiro pela rede é quem cria.</div>
        <p>Depois, cada operador ganha o próprio usuário em <a href="/usuarios">Usuários</a> (menu Sistema), onde também dá para trocar senhas e remover quem não usa mais.</p>
        <p>Use senhas que não sejam fáceis de adivinhar, principalmente se o U-Control também for acessível pela internet.</p>`,

    windows: `
        <h2>Programa no Windows</h2>
        <ul>
            <li>Depois de instalado, abra pelo ícone <strong>U-Control</strong> na área de trabalho. O Controle abre no navegador e o programa fica na <strong>bandeja do Windows</strong>, ao lado do relógio.</li>
            <li>Pelo menu da bandeja você abre o <strong>Telão</strong>, a <strong>Tela pública de letras</strong> e o <strong>Retorno de palco</strong>. Com um segundo monitor ou datashow ligado, elas abrem nele, em tela cheia.</li>
            <li>O menu também mostra o endereço do U-Control na rede, para abrir no celular.</li>
            <li>Para desligar, use <strong>Sair</strong> no menu da bandeja. Fechar as janelas não desliga o programa.</li>
            <li>Músicas, fotos e configurações ficam guardadas à parte (opção <strong>Abrir pasta de dados</strong>). Instalar uma versão nova por cima não apaga nada.</li>
        </ul>`,

    celular: `
        <h2>Usar pelo celular ou outro computador</h2>
        <ul>
            <li>O aparelho precisa estar na <strong>mesma rede</strong> (Wi-Fi ou cabo) do computador do U-Control.</li>
            <li>Em <a href="/links">Links / QR</a> estão os endereços de cada tela, com QR code para apontar a câmera do celular.</li>
            <li>O endereço tem a forma <code>http://&lt;ip-do-computador&gt;:8585</code>.</li>
        </ul>`,

    telas: `
        <h2>Telas que abrem sem login</h2>
        <p>As funções de controle exigem login, para ninguém mudar o telão sem querer. Estas telas abrem sem login, para os aparelhos de exibição e para quem só acompanha:</p>
        <ul>
            <li><strong>Telão do público</strong> (<code>/img</code>) e <strong>letra para o público</strong> (<code>/lyrics/display/public</code>)</li>
            <li><strong>Retorno de palco</strong> (<code>/monitor</code>), para quem está no palco</li>
            <li><strong>Bíblia</strong> (<code>/bible/display</code>), <strong>relógio</strong> e <strong>cronômetro</strong></li>
            <li><strong>Overlay para OBS</strong> (<code>/lyrics/display/obs</code>), com fundo transparente para transmissão</li>
            <li><strong>Enviar fotos</strong> (<code>/presenter</code>): qualquer pessoa da igreja manda fotos do celular para a galeria</li>
            <li><strong>Ordem do culto</strong> (<code>/view</code>)</li>
        </ul>`,

    problemas: `
        <h2>Solução de problemas</h2>
        <h3>O celular não abre o U-Control</h3>
        <ul>
            <li>Confira se o celular está na mesma rede do computador, e não nos dados móveis.</li>
            <li>No Windows, o instalador libera o U-Control no firewall. Se outro antivírus ou firewall estiver ativo, libere a porta <code>8585</code> nele.</li>
            <li>Algumas redes de visitantes isolam os aparelhos entre si. Nesse caso, use a rede principal da igreja.</li>
        </ul>
        <h3>O vídeo toca sem som no telão</h3>
        <p>Navegadores bloqueiam som automático. As telas abertas pelo menu da bandeja (Windows), pelo <strong>Abrir no datashow</strong> do Controle ou pelo script baixado no <a href="/dashboard">Início</a> já vêm com o som liberado. Numa aba comum, toque uma vez na tela do telão.</p>
        <h3>A tela não entra em tela cheia</h3>
        <p>No Controle, use <strong>Abrir no datashow</strong> para escolher em qual tela do computador a tela pública abre.</p>
        <h3>Uma tradução da Bíblia não aparece</h3>
        <p>O U-Control traz só traduções de licença aberta (como a Bíblia Livre e a Nova Bíblia Viva). Traduções com direitos autorais, como NVI e ACF, precisam ser adicionadas por quem tem o direito de usá-las.</p>`,

    contato: `
        <h2>Contato</h2>
        <p>O U-Control é um projeto de código aberto. Para relatar um problema ou sugerir uma melhoria, abra um chamado em <a href="https://github.com/brunomint/U-Control/issues" target="_blank" rel="noopener">github.com/brunomint/U-Control/issues</a>.</p>`,
};

function loadContent(section) {
    const content = document.getElementById('content');
    content.innerHTML = HELP_SECTIONS[section] || '';
    document.querySelectorAll('.help-menu [data-section]').forEach(a => {
        a.classList.toggle('active', a.dataset.section === section);
    });
    content.scrollIntoView({ block: 'start', behavior: 'smooth' });
}
