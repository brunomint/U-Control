// Conteúdo da página /help. Só texto: as capturas de tela antigas mostravam
// nomes de usuário reais e ensinavam uma senha padrão que não existe mais.
const HELP_SECTIONS = {
    funcionalidades: `
        <h2>Principais funcionalidades</h2>
        <p>Um computador roda o U-Control, e os outros aparelhos da mesma rede (celular, tablet, outro PC) abrem o controle ou as telas pelo navegador. Não precisa de internet durante o culto.</p>
        <ul>
            <li><strong>Controle:</strong> letras com cifra, versículos, fotos, vídeos e PowerPoint vão para o telão com um toque.</li>
            <li><strong>Telas preta, branca e logo:</strong> no Controle (e no Apresentador), cobrem o telão nos intervalos. Embaixo deles, escolha onde valem: <em>Público</em> (o padrão), <em>Palco</em> ou <em>Os dois</em>. O logo da igreja é enviado em Agenda → painel, no cartão <em>Nome e logo da igreja</em>. Toque de novo (<em>Voltar</em>) para voltar a imagem.</li>
            <li><strong>Ficha da música:</strong> no editor, o cartão <em>Ficha da música</em> guarda tom original, andamento (BPM), compasso, copyright e nº CCLI. Os três primeiros aparecem no Monitor da banda; copyright e CCLI saem em letra pequena no primeiro e no último slide do telão. Ao importar do OpenSong, OpenLP ou ChordPro, a ficha vem junto.</li>
            <li><strong>Capotraste:</strong> no Monitor, o botão <em>Capo</em> no canto mostra os acordes como o violonista vai tocar (música em Lá com capo na 2ª casa aparece em Sol). Vale só naquele aparelho.</li>
            <li><strong>Ordem no culto:</strong> no editor da música, monte a sequência (Verso 1 → Refrão → Verso 2 → Refrão) sem repetir o refrão. Ao vivo, as setas e o pedal seguem a ordem, e as teclas <kbd>1</kbd>–<kbd>9</kbd> (versos), <kbd>C</kbd> (refrão), <kbd>B</kbd> (ponte), <kbd>P</kbd> (pré-refrão), <kbd>I</kbd> (intro) e <kbd>F</kbd> (final) pulam direto.</li>
            <li><strong>Telas sincronizadas:</strong> o telão do público e o retorno de palco acompanham o Controle.</li>
            <li><strong>Preparação:</strong> monte a ordem do culto, cadastre músicas e organize as escalas antes.</li>
            <li><strong>Bíblia em duas versões</strong> ao mesmo tempo no telão.</li>
            <li><strong>Tela do PC</strong> e <strong>site no telão</strong>, comandados pelo Controle.</li>
            <li><strong>Atalhos</strong> para Stream Deck e outros botões.</li>
            <li><strong>Importar músicas</strong> de outros programas, <strong>backup</strong> e levar músicas e cultos para outro computador.</li>
        </ul>
        <p>O telão pode ficar no próprio computador do U-Control (cabo HDMI, mais estável) ou em outro aparelho da rede.</p>
        <p>O idioma das telas (português ou inglês) fica em <a href="/idioma">Sistema → Idioma · Language</a>.</p>`,

    importar: `
        <h2>Importar músicas de outro programa</h2>
        <p>Em <a href="/importar-musicas">Criar → Importar Músicas</a>, escolha um ou mais arquivos. O U-Control mostra o que encontrou antes de gravar qualquer coisa.</p>
        <ul>
            <li><strong>Holyrics:</strong> músicas exportadas em JSON.</li>
            <li><strong>OpenLP e outros:</strong> arquivos OpenLyrics (<code>.xml</code>), inclusive com cifra e a ordem das seções.</li>
            <li><strong>OpenSong:</strong> os arquivos da pasta <code>Songs</code> (eles não têm extensão) ou a pasta inteira num <code>.zip</code>, com a cifra e a ordem de apresentação.</li>
            <li><strong>ChordPro</strong> (<code>.cho</code>, <code>.chordpro</code>, <code>.pro</code>…): os acordes entre colchetes viram a linha de cifra em cima da letra.</li>
            <li><strong>Texto</strong> (<code>.txt</code>), um arquivo por música, e <strong>.zip</strong> com vários desses arquivos dentro.</li>
        </ul>
        <p>Vêm marcadas só as músicas novas. As que já existem aqui (mesmo título e autor) só são trocadas se você marcar <strong>substituir a deste computador</strong>.</p>
        <div class="callout">O formato próprio do Holyrics (<code>.muf</code>) ainda não é lido. No Holyrics, exporte as músicas em JSON.</div>`,

    biblia: `
        <h2>Bíblia em duas versões</h2>
        <p>Nas páginas da Bíblia, ao lado da tradução, escolha uma <strong>2ª versão</strong>. O telão passa a mostrar o versículo nas duas, uma embaixo da outra, cada uma com a sigla. Para voltar a uma só, escolha <strong>+ 2ª versão: nenhuma</strong>.</p>
        <p>A escolha vale para todos os Controles e continua depois de reiniciar o programa.</p>`,

    powerpoint: `
        <h2>PowerPoint e apresentações</h2>
        <ul>
            <li>No Controle, em <strong>Fotos</strong>, envie o arquivo <code>.pptx</code> (ou PDF). Ele vira uma imagem por slide, e os slides aparecem todos juntos em cerca de 1 minuto.</li>
            <li>Se a apresentação tem <strong>animações ou transições</strong>, o U-Control prepara também uma versão animada, marcada com a etiqueta <strong>Animado</strong>. Os slides comuns já podem ser usados enquanto ela fica pronta.</li>
            <li>Na versão animada, use <strong>Avançar</strong> e <strong>Voltar</strong> (ou as setas, o espaço e o pedal) para passar cada animação. Todas as telas acompanham juntas.</li>
            <li>As fontes embutidas no arquivo (como as do Canva) são usadas, e na versão animada os GIFs se mexem.</li>
            <li>Vídeos dentro dos slides são separados e aparecem na galeria para tocar no telão.</li>
        </ul>
        <div class="callout">No Windows, a conversão precisa do LibreOffice: marque a opção dele no instalador ou, se ele faltar, use <strong>Instalar LibreOffice</strong> em <a href="/atualizacao">Sistema → Atualização</a>.</div>`,

    site: `
        <h2>Tela do PC e site no telão</h2>
        <h3>Tela do PC</h3>
        <p>No computador que vai compartilhar, abra o Controle e use a ferramenta <strong>Tela do PC</strong>: o navegador pergunta o que mostrar no telão (uma janela, uma aba ou a tela inteira). A qualidade depende da rede: no cabo ou num Wi-Fi bom, o texto fica nítido.</p>
        <p><strong>O último conteúdo no ar é o que aparece:</strong> mandar uma letra, versículo ou foto para uma tela tira a Tela do PC dela (em "Só público", o palco continua com o PC). As telas preta, branca e logo só cobrem: ao tocar em Voltar, aparece o que estava por baixo, inclusive o PC.</p>
        <h3>Site no telão (Windows)</h3>
        <p>A ferramenta <strong>Site</strong> abre um site em tela cheia no monitor do telão, num navegador de verdade (Chrome ou Edge), e o Controle comanda: rolar, página abaixo e acima, setas, Enter, zoom, voltar e recarregar. Funciona também pelo celular.</p>
        <ul>
            <li>Guarde os sites que você usa sempre para abrir com um toque.</li>
            <li>O navegador do site tem um perfil próprio: um login feito nele uma vez fica salvo.</li>
            <li>Só existe na instalação Windows, porque precisa abrir uma janela no monitor do telão.</li>
        </ul>`,

    atalhos: `
        <h2>Atalhos (Stream Deck)</h2>
        <p>Em <a href="/atalhos">Sistema → Atalhos (Stream Deck)</a> estão os endereços que comandam o telão: próximo e anterior, liberar, tela preta, aviso, cronômetro, relógio e o site no telão. Qualquer botão que chame um endereço web serve: Stream Deck pelo Companion, QuickDeck e outros.</p>
        <ul>
            <li>Cada endereço leva uma <strong>chave de acesso</strong>. Se ela vazar, troque na mesma página: os endereços antigos param de funcionar.</li>
            <li><strong>Próximo</strong> e <strong>anterior</strong> seguem o que estiver no ar: o site no telão, a apresentação animada ou o que está aberto no Controle usado por último.</li>
        </ul>`,

    backup: `
        <h2>Backup e levar para outro computador</h2>
        <h3>Backup (tudo)</h3>
        <p>Em <a href="/backup">Sistema → Backup</a>, baixe um arquivo com tudo: músicas, cultos, configurações, usuários, fotos e áudios. Para restaurar, envie esse arquivo na mesma página, inclusive noutro computador com o U-Control. Antes de restaurar, o programa guarda uma cópia do que existia.</p>
        <h3>Exportar e importar (só o que escolher)</h3>
        <p>Em <a href="/pacote">Sistema → Exportar e importar</a>, escolha músicas, cultos e fotos e leve para outro U-Control. Por exemplo: preparar em casa e usar no PC da igreja. Ao importar, você vê o que vem e o que já existe aqui antes de confirmar.</p>`,

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
            <li>Pelo menu da bandeja você abre o <strong>Telão</strong> (a tela pública) e o <strong>Retorno de palco</strong>. Com um segundo monitor ou datashow ligado, elas abrem nele, em tela cheia.</li>
            <li>O menu também mostra o endereço do U-Control na rede, para abrir no celular.</li>
            <li>Enquanto o U-Control está aberto, o Windows não suspende nem apaga a tela (opção <strong>Não deixar o PC dormir com o telão aberto</strong> no menu da bandeja).</li>
            <li>Para converter PowerPoint em slides, marque a opção do LibreOffice no instalador. Se ele faltar, <strong>Sistema → Atualização</strong> mostra o botão <strong>Instalar LibreOffice</strong>.</li>
            <li>Para desligar, use <strong>Sair</strong> no menu da bandeja ou <strong>Sistema → Desligar o U-Control</strong>. Fechar as janelas não desliga o programa.</li>
            <li>Quando sai uma versão nova, o U-Control avisa. A instalação é em <strong>Sistema → Atualização</strong>.</li>
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
        <h3>O aviso não aparece numa tela</h3>
        <p>No painel <strong>Avisos</strong> do Controle, confira quais telas estão marcadas (Tela pública, Palco, Transmissão). Cada tela tem o próprio aviso: mandar para uma não muda as outras. Embaixo dos botões aparece o que está em cada tela agora.</p>
        <h3>A tela não entra em tela cheia</h3>
        <p>No Controle, use <strong>Abrir no datashow</strong> para escolher em qual tela do computador a tela pública abre.</p>
        <h3>Uma tradução da Bíblia não aparece</h3>
        <p>O U-Control traz só traduções de licença aberta (como a Bíblia Livre e a Nova Bíblia Viva). Traduções com direitos autorais, como NVI e ACF, precisam ser adicionadas por quem tem o direito de usá-las.</p>`,

    contato: `
        <h2>Contato</h2>
        <p>O U-Control é um projeto de código aberto. Para relatar um problema ou sugerir uma melhoria, abra um chamado em <a href="https://github.com/brunomint/U-Control/issues" target="_blank" rel="noopener">github.com/brunomint/U-Control/issues</a>.</p>`,
};

// Outros idiomas: o texto inteiro de cada tópico vem traduzido de
// help_<idioma>.js (texto corrido não se traduz frase por frase)
const SECOES = window.HELP_SECTIONS_I18N || HELP_SECTIONS;

function loadContent(section) {
    const content = document.getElementById('content');
    content.innerHTML = SECOES[section] || '';
    document.querySelectorAll('.help-menu [data-section]').forEach(a => {
        a.classList.toggle('active', a.dataset.section === section);
    });
    content.scrollIntoView({ block: 'start', behavior: 'smooth' });
}
