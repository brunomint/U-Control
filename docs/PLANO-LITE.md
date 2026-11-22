# Plano: modo "lite" do U-Control para aparelhos antigos

> Escrito numa conversa pelo celular e trazido para o repositório em
> 22/11/2026.
>
> **Estado (22/11/2026):** segunda conferência feita (seção 11); Fases 0,
> 0B, 1 e 1B publicadas no Pi em 22/11 (~08:20); Fase 3 feita depois, no
> branch `lite`, ainda não publicada. iPad com iOS
> 10.3.4 testado no servidor de teste (Monitor e Público funcionando). A Fase 1 já inclui a
> tela Público (que o plano chamava de Fase 2). Falta abrir nos aparelhos
> reais (item 6 da conferência).
>
> Fase 1, como ficou:
> - `/lite/` (inicial), `/lite/monitor`, `/lite/publico` e
>   `/lite/api/estado?tela=` (`lite_estado.py` lê o estado das telas
>   normais, sem guardar nada próprio);
> - `static/lite/tela.js` (pergunta a cada 1,5 s);
> - `static/lite/detectar.js` (desvio automático, no `base.html` e nas
>   telas);
> - depois do login, o aparelho simples vai para `/lite/`.
> - Cookie `uc_lite`: `1` = simples, `0` = completa sempre, sem cookie =
>   automático.
> - Partitura, vídeo e Tela do PC aparecem só como aviso.

## 1. Objetivo

Usar o U-Control em aparelhos de cerca de 2010-2011 **pelo navegador**, sem
APK (decisão tomada: um só caminho para Android e iPad):

- tablet Samsung de 10" com Android antigo (ver seção 2);
- iPad da mesma época (iPad 1 fica no iOS 5.1.1; iPad 2 vai até o iOS 9.3.5).

Papel principal: **monitor de palco** (letra/cifra grande, só leitura).
Depois: telão público lite e um controle remoto simples.

## 2. Dados dos aparelhos (preencher)

- Android: **6.0 (Marshmallow)**; modelo **Samsung Galaxy Tab GT-P7510**
  (Galaxy Tab 10.1 Wi-Fi, de 2011; o Android 6 só pode ser ROM customizada);
  motor: **Android WebView 44** (equivale ao Chrome 44, de 2015). Dados lidos
  numa captura de tela do whatismybrowser.com, em 21/11/2026.
  - O site também disse "JavaScript is not enabled". Pode ser JS desligado
    nas configurações do navegador ou o script do próprio site falhando em
    motor antigo. Conferir nas configurações e com `/lite/diag`.
  - O que o Chrome 44 tem (de memória, conferir no `/lite/diag`): ES5,
    `Promise`, `fetch`, template strings, flexbox, WebSocket. O que não tem:
    arrow functions (Chrome 45), `const/let` em modo normal (49),
    `async/await` (55), `var(--)` (49), CSS grid (57). Isso explica o vídeo:
    o JS e o tema do app quebram por sintaxe e variáveis CSS.
  - Possível atalho: o WebView é atualizável pela Play Store ("Android System
    WebView"/Chrome), se a ROM tiver os serviços do Google. Se atualizar para
    uma versão recente, o app atual pode até funcionar. Testar antes das
    fases; o lite continua valendo para o iPad e como plano B.
- iPad: **iOS 10.3.4**, Safari 10 (lido no login do servidor de teste,
  22/11/2026: "CPU OS 10_3_4", Mobile/14G61; modelo ainda não anotado).
  O `/lite/diag` dele (relatório LITE_DIAG, tela 768x1024, densidade 2)
  só não tem `?.` e `??`: tem let/const, arrow, template string, class,
  `async/await`, `fetch`, `Promise`, variáveis CSS, flexbox e grid.
  Pelo acorn, 16 dos 76 JS do app não rodam nele (`...` em objeto, `?.`,
  `??`), entre eles o `display.js` (cifra do monitor), o `control.js` e o
  `lyrics_2.js`. Por isso o `detectar.js` testa também `...`, `?.` e `??`.
  - Não é o iPad que já usamos com o U-Control (192.168.0.4): aquele se
    apresenta como "Macintosh" no navegador, ou seja, iPadOS 13 ou mais novo,
    e roda o app normal. O iPad antigo deste plano ainda não foi conectado.
- Como obter: Configurações → Sobre o tablet; no navegador, abrir
  `/lite/diag` (Fase 0) e anotar o que a página mostrar.

Pistas vistas num vídeo do tablet Android (câmera instável, modelo exato não
confirmado): parece um Samsung Galaxy Tab 10.1; a barra de navegação (triângulo,
círculo, quadrado) indica Android 5 ou mais novo, talvez ROM customizada. Ele
abriu `http://ucontrolibrjoaoxxiii.com/dashboard` (HTTP, então TLS não foi o
bloqueio): o HTML e parte do CSS carregaram, mas o layout ficou estreito e os
blocos dinâmicos ficaram parados em "Carregando o próximo culto..." e
"Carregando status do sistema...", e os campos de `/order` vieram vazios.
Conclusão provável: o JS ES6+ não roda e o CSS moderno só funciona em parte.

## 3. Estado atual do código (v1.1.0, verificado no repositório)

- Flask 3 + Flask-SocketIO 5.6.0, `async_mode='threading'`, transports
  `['polling','websocket']` (`main.py`, ~linha 172). O servidor já aceita
  polling; o problema é o cliente.
- Front-end em ES6+ (`const`, `let`, arrow, `fetch`, `async`: mais de 4.000
  ocorrências em `static/js`) e Socket.IO client 4.5.4 em
  `static/vendor/socketio/`. Em aparelho antigo nada disso executa.
- `GET /api/current-display` (`blueprints/display.py`, ~linha 1360) devolve JSON
  com `mode` (`lyrics`, `image`, `video`, `avisos`...) e o payload atual. É a
  base do polling. Conferir se exige login (não vi `@login_required`).
- `POST /api/monitor/sync` exige login e só dispara eventos Socket.IO para o
  monitor; não serve para polling. O que o monitor mostra difere do público
  (ex.: cifra em vez da letra do público: `_url_cifra_monitor`,
  `telao.public_url()`, `display_state`). O endpoint lite precisa reproduzir
  essa regra, reaproveitando essas funções.
- Segurança: CSRF ativo (meta `csrf-token` + `static/js/csrf.js`), cookie
  SameSite=Lax (`seguranca.py`). Formulários lite precisam de `csrf_token`.
- Blueprints são registrados em `main.py` (~linhas 198-223).
- Testes: `tests/` (pytest, `pytest.ini`); rodar com `python -m pytest`.
  Ambiente de dev: ver `CONTRIBUTING.md`.

## 4. Regras do código lite

- Só ES5: `var`, `function`, `XMLHttpRequest`, `className`, `setTimeout`.
  Nada de `const/let`, arrow, template string, `fetch`, `Promise`, `async`,
  `classList`, `Array.from`, `Object.assign`, `startsWith`/`includes`,
  `forEach` em NodeList.
- CSS simples: `float`/`table`/`inline-block`; sem flexbox, grid, `vh/vw`
  críticos (usar JS para altura), variáveis CSS, `gap`.
- Sem Socket.IO, sem iframe, sem vídeo, sem VexFlow/partitura, sem fontes ou
  CDN externos. Tudo servido pelo próprio Pi.
- Nada de HTTPS obrigatório: o lite deve funcionar em `http://IP-do-Pi:8585`
  na rede local.
- Leve (iPad 1 tem pouca memória): só texto e uma imagem por vez.
- Reaproveitar a lógica de servidor existente; não duplicar regras.

## 5. Fases

### Fase 0: diagnóstico (`/lite/diag`)
- Página estática ES5, sem login, que mostra `navigator.userAgent` e testa:
  `fetch`, `Promise`, `const/let` (via `try/eval`), flexbox, grid, `WebSocket`,
  `localStorage`, `XMLHttpRequest`, `requestAnimationFrame`.
- Pronto quando: abre no tablet Android e no iPad e lista os resultados.

### Fase 0B: tema de reserva, sem variáveis CSS
Resolve o problema nº 1 da varredura (seção 10), que atinge quase todas as
páginas. Destrava `/login`, `/links` e as páginas lite.
- Criar `static/lite/lite.css`: mesmas cores e espaçamentos do `tokens.css`/
  `app.css`, mas com valores fixos. Sem `var(--)`, grid, flex, `gap`, `clamp`,
  `inset`, `:is/:has`; layout com `float`/`inline-block`/`table`.
- Aplicar nas páginas lite e, se der, em `/login` e `/links` (por exemplo uma
  flag no `base.html` que troca `tokens.css`+`app.css` por `lite.css`). Não
  alterar a aparência do app normal.
- Pronto quando: `/login`, `/links` e a futura `/lite/` ficam legíveis e
  usáveis no tablet Android e no iPad.
- Teste: pytest que varre `static/lite/*.css` e falha se achar `var(`, `grid`,
  `flex`, `gap:`, `clamp(` ou `inset:`.

### Fase 1: monitor lite (`/lite/monitor`)
- Blueprint novo `blueprints/lite.py` (registrar em `main.py`), templates em
  `templates/lite/`, JS em `static/lite/` (um único arquivo ES5).
- Endpoint `GET /lite/api/estado`: JSON pequeno com um campo `rev` (número ou
  hash) que só muda quando o conteúdo muda, mais o necessário para desenhar
  letra/cifra em texto, imagem, relógio e tela preta/branca/logo.
- Cliente: `XMLHttpRequest` a cada ~1,5 s; só redesenha se `rev` mudou; indicador
  de "sem conexão" e nova tentativa automática; sem tela branca ao falhar.
- Layout: fonte grande, ajuste de altura por JS, funciona em 16:10 (tablet
  Android) e 4:3 (iPad). Meta tags para iOS: `apple-mobile-web-app-capable`,
  `viewport`, ícone.
- **Sem login** (decidido): as páginas lite de leitura são abertas, como o
  monitor e o telão atuais. Não expor nada além do que essas telas já mostram.
- **Escolha da tela** (decidido): `/lite/` é uma página inicial com dois botões
  grandes, "Público" e "Monitor". O aparelho lembra a escolha (cookie ou
  `localStorage` com `try/catch`) e abre direto nela da próxima vez; link
  "trocar tela" no canto. Também aceitar `/lite/?tela=publico` e
  `?tela=monitor` para favoritos e atalhos.
- **Página inicial `/lite/`** (decidido em 22/11): botões grandes Monitor,
  Público, Cifras do culto e Controle (este só aparece com login, a partir
  da Fase 3). Monitor, Público e Cifras não pedem login.
- **Detecção automática** (decidido em 22/11): cada página do app normal
  começa com um script ES5 pequeno (arquivo próprio em `static/lite/`, sem
  JS inline) que testa no próprio navegador se há variáveis CSS e JS novo
  (`fetch` e `Promise`). Não se adivinha pelo nome do navegador, porque o
  iPadOS se apresenta como "Macintosh".
  - Tem tudo: segue normal.
  - Falta algo: vai para a versão simples da mesma página (`/monitor` →
    `/lite/monitor`, `/lyrics/display/public` → `/lite/?tela=publico`,
    `/view` e `/view/<id>` → cifras lite quando existirem). Sem versão
    simples (editores, admin): vai para `/lite/` com o aviso "Esta página
    precisa de um navegador mais novo".
  - Manual: `?lite=1` força a versão simples; um link "versão completa"
    (`?lite=0`) desliga o desvio naquele aparelho, caso o teste erre.
- **Depois do login**: aparelho antigo vai para `/lite/` e não para o
  `/dashboard` (o `next` do login vale se apontar para uma página lite).
- Pronto quando: monitor lite acompanha troca de seção, imagem e blackout feitos
  no `/control`, no tablet e no iPad (ou na emulação), sem erro de JS; e um
  navegador antigo que abre `/`, `/login` → entrar, `/dashboard` ou
  `/monitor` termina numa página lite que funciona.

### Fase 2: modo "Público" do lite (mesma página, `tela=publico`)
- Mesma base e mesmo endpoint, mostrando o que o telão público mostra (letra de
  `/lyrics/display/public`, avisos e relógio). Tema só no básico
  (cor/fonte/tamanho); sem vídeo de fundo. O endpoint recebe `tela=publico` ou
  `tela=monitor` e aplica a regra de cada uma.

### Fase 1B: cifras lite, sem WebSocket (`/lite/cifras`)
Leitura de cifra para os músicos, só com a lista do culto e a cifra de cada
música. Sem login, como as páginas atuais `/view` e `/view/<id>`.
- Verificado no código: `/view` (lista) e `/view/<id>` (cifra) em `main.py`
  são públicas. A cifra já vem renderizada pelo servidor (Jinja). O JS do
  navegador cuida de Tom, Capo, rolagem automática, menu, busca, player do
  YouTube e partitura (VexFlow, em `<script type="module">`, que não roda em
  navegador antigo). A lista (`view_song_order.js`) monta a ordem com `fetch`
  em `/load?date=` e `/api/orders`, que já devolvem JSON.
- **Lista** `/lite/cifras?order=AAAA-MM-DD` (padrão: ordem de hoje): HTML
  renderizado no servidor, sem JS, com link para cada música.
- **Cifra** `/lite/cifra/<id>?order=...&tom=N&capo=N`: o servidor já tem
  `chord_lines.render_cifra_html(content, semitones)` e `transpose_line`,
  então o **Tom** e o **Capo** (capo N = acordes transpostos em -N, "formas
  que o violonista toca") viram simples links `?tom=`/`?capo=`, sem JS. Conferir
  se os helpers cobrem tudo que o `chord_lines.js` faz (acordes com baixo,
  menores, seções entre colchetes).
- Rolagem automática e tamanho da fonte (A−/A+): pequeno JS ES5 opcional
  (`setInterval` com `scrollBy`); a página funciona sem ele.
- Anterior/próxima música da ordem como links no topo e no rodapé.
- Fora do lite: player do YouTube/áudio, partitura VexFlow, busca ao vivo.
  Música com partitura mostra só a cifra em texto e um aviso.
- Atualização da lista se a ordem mudar: botão "Atualizar" (recarrega a
  página); `<meta refresh>` opcional.
- Pronto quando: abrir a ordem do dia no tablet e no iPad, navegar entre as
  músicas, mudar Tom e Capo e rolar sem nenhum erro de JS.

### Fase 3: controle lite (`/lite/controle`)
- Formulários `POST` com CSRF: seção anterior/próxima, blackout, escolher
  música da ordem do culto. Cada botão chama a mesma função de serviço usada
  pelos eventos Socket.IO.

**Feita em 22/11/2026, "igual ao Stream Deck" (decisão do Bruno):**
- Anterior/Próximo e "abrir música/leitura da ordem" vão para o Controle
  aberto num PC (`atalhos._navegar`, `atalhos.abrir_no_controle`, que pede
  `atalho_abrir` ao `control.js`). O servidor não monta estrofe sozinho.
  Sem Controle aberto, a página avisa.
- Tela preta/branca/logo, esconder/mostrar a letra e relógio chamam os
  handlers de socket do Controle (`lite_controle._rodar`), com login e a
  regra de quem cuida de cada tela. "Minhas telas" (Público, Palco, Os dois,
  Nenhuma) e "Assumir". Recusa aparece no alto (`g.uc_recusa`, em
  `extensions.py`). Liberar funciona igual ao do Stream Deck.
- Sem tempo real, o aparelho não "segura" a tela: `destinos.dono` larga a
  tela de quem não tem aparelho conectado. Ele mexe numa tela livre, ou
  numa tela da mesma pessoa logada noutro aparelho.
- O detector manda `/control`, `/presenter` e `/lyrics/<id>` para lá.

### Fase 4: acabamento
- Menu/QR "versão simples", favorito fixo, README e Ajuda em português.

## 6. Testes

- `tests/test_lite.py` (pytest, cliente de teste do Flask): `/lite/diag`,
  `/lite/monitor` e `/lite/api/estado` respondem 200; `rev` muda quando o estado
  muda; POSTs da Fase 3 exigem CSRF.
- Teste que varre `static/lite/*.js` e falha se achar sintaxe proibida pela
  regra de ES5 (seção 4), sem depender de rede.
- Manual: emular Chrome/Safari antigo, depois no tablet e no iPad reais; testar
  também com o Wi-Fi caindo e voltando.

## 7. Ajustes nos aparelhos (fora do código)

- iPad: Ajustes → Geral → Bloqueio automático → Nunca; "Adicionar à Tela de
  Início" para tela cheia; Acesso Guiado para travar na página.
- Android: tempo de tela longo ou "Manter ativo" (opções do desenvolvedor);
  atalho na tela inicial ou tela cheia do navegador. Se houver Play Store,
  tentar atualizar o WebView/navegador antes de tudo.
- Em rede local, usar `http://IP-do-Pi:8585/lite/...`.

## 8. Fora do escopo (por enquanto)

APK próprio, motor de navegador embutido, vídeo sincronizado, partitura,
temas animados e transições.

## 9. Perguntas em aberto

1. Versões do Android, WebView/Chrome e iOS (seção 2). Não bloqueia a Fase 0
   nem a Fase 1; o código já nasce em ES5.
2. ~~Login no lite~~: decidido, sem login.
3. ~~Público ou monitor~~: decidido, o aparelho escolhe na página inicial.
4. ~~Cifra no monitor~~: não é decisão. O monitor atual já mostra a cifra da
   mesma música e seção (`_url_cifra_monitor` em `blueprints/display.py`); o
   modo Monitor do lite reproduz isso, e o modo Público mostra a letra.
5. **Os helpers do servidor cobrem tudo o que o `chord_lines.js` faz hoje?**
   (`chord_lines.py`: `render_cifra_html`, `render_cifra_html_pares`,
   `transpose_line`, `transpose_chord`, `split_bracket_subsections`.) Comparar
   com `static/js/chord_lines.js` e conferir, por exemplo: acordes com baixo
   (`C/E`), menores e sufixos (`m7`, `sus4`, `dim`), bemóis e sustenidos
   conforme a tonalidade, seções entre colchetes (`[Refrão]`), linhas de
   acordes versus linhas de letra, e o Capo. Se faltar algo, corrigir no
   Python (e cobrir com teste) antes de fazer a Fase 1B. Esta dúvida bloqueia
   a Fase 1B.

   **Resposta (22/11/2026):** a detecção de linha de cifra era igual, mas a
   transposição do Python não mantinha cada acorde na coluna da sílaba
   quando o nome mudava de tamanho (Bm7 → F#m7). O `transpose_line` foi
   corrigido igual ao `transposeLine` do JS. Comparação nas 3.198 seções
   reais do backup `data_backup_pre_sql/songs.json` + casos difíceis, em
   todos os tons: 0 diferenças. `tests/test_lite.py`
   (`test_transposicao_igual_ao_js`) compara com o JS usando o node. Isso
   também corrige o alinhamento da cifra transposta no PDF de impressão.

   **Fase 1B feita:**
   - `/lite/cifras?order=` (sem JS; sem `order`, o próximo culto) e
     `/lite/cifra/<id>?order=&tom=&capo=` (`lite_cifras.py`).
   - As seções saem de `chord_lines.secoes_cifra`, a mesma montagem do PDF
     (tirada de `main.py`, saída idêntica nas músicas reais).
   - Tom (−½, +½, original e a grade dos 12 tons) e Capo (0 a 9) são
     links.
   - `static/lite/cifra.js` (opcional) faz A−/A+ e a rolagem automática.
   - O detector manda `/view`, `/view/<id>` e `/view/order/<data>` para lá.

## 10. Anexo: varredura das páginas (21/11/2026, v1.1.0)

Método: script que, para cada um dos 50 templates, juntou `extends`/`include`,
listou os `.js`/`.css` carregados e contou sintaxe/recursos modernos (arrow,
`const/let`, template string, `async`, módulos ES, `fetch`, Socket.IO,
`var(--)`, grid, flex). Contagens são aproximadas; os números servem para
comparar páginas, não como medida exata. Não rodei nada num aparelho antigo.

### Problemas comuns a quase todas as páginas
1. **Tema do app**: 42 dos 50 templates estendem `base.html`, que carrega
   `tokens.css`/`app.css` (mais de 90 usos de `var(--...)`, além de grid e
   flex). Engines antigas ignoram variáveis CSS: cores e layout quebram. Bate
   com o vídeo do tablet.
2. **JS do `base.html`** (`csrf.js`, `ui.js`, `i18n.js`) usa ES6/`async`: um
   erro de sintaxe derruba o arquivo inteiro.
3. **`_nav.html`** carrega `telao_bar.js` (ES6 + `window.io()`): a barra "No ar"
   some em aparelho antigo.
Conclusão: nenhuma página funciona 100% hoje num navegador realmente antigo.
Um tema de reserva (CSS sem variáveis) para o lite resolve o item 1.

### A. Quase prontas (poucos ajustes)
- `/view/<id>/print`: página/PDF gerado no servidor, sem JS e fora do
  `base.html`. Conferir no PC o que ela devolve (o docstring diz PDF via
  WeasyPrint). Pode servir de cifra imprimível já na Fase 0.
- `/login`: formulário `POST`, sem JS próprio; precisa só do CSS de reserva.
- `/links`: QR codes renderizados no servidor; JS só no botão "Copiar".

### B. Leitura com pouco JS (viram lite com esforço pequeno)
- `/view` (lista) e `/view/<id>` (cifra): ver Fase 1B.
- `/view/order/<date>`: ordem do culto; HTML vem pronto do servidor, JS só para
  marcar itens, PDF (jsPDF) e atualização ao vivo.
- `/clock` (`relogio.js` ~10 linhas) e `/countdown` (~70 linhas, Socket.IO):
  fáceis de portar para ES5.
- `/help`; páginas da Bíblia de leitura (`/bible`, livro, capítulo): conteúdo
  server-side provável, mas conferir o JS de cada uma.

### C. Precisam de versão lite própria (tempo real ou JS pesado)
`/monitor` (~700 linhas de JS, Socket.IO, iframes), `/lyrics/display/public`
(~1.300), `/lyrics/display` (~1.800), `/lyrics/display/obs`, `/img`,
`/bible/display`, `/presenter`, `/control` (~1.800), `/lyrics/<id>` (~3.500).
Cobertas pelas Fases 1, 2 e 3.

### D. Não vale adaptar (usar no PC)
Editores e administração: `edit_song`, `new_song`, `sheet_editor` (módulo ES e
VexFlow), `temas`, `avisos`, `importar_musicas`, `backup`, `pacote`,
`atualizacao`, `usuarios`, `registro_tela`, `agenda*`, `order_edit`,
`atalhos`, `idioma`, `desligar`, `historico`, `list_songs`, `order_list`,
`dashboard`, `bible_control*`, `apresentacao`, `tela_do_pc`.

### Ordem sugerida das fases
Fase 0 (diagnóstico) → Fase 0B (CSS de reserva) → Fase 1B (cifras lite, depois
de resolver a pergunta 5) → Fase 1/2 (monitor e público) → Fase 3 (controle) →
Fase 4.

### Segunda conferência pedida (fazer antes de implementar)
A varredura acima foi feita só lendo o código, com contagens aproximadas.
Antes de começar as fases, conferir:
1. **Refazer a varredura com ferramentas de verdade**: checar a sintaxe dos JS
   com um parser em modo ES5 (por exemplo `acorn --ecma5`) e os CSS com
   `browserslist`/`doiuse` apontando para Android 4.4/5 e iOS 5/9. Comparar
   com as listas A/B/C/D e corrigir o que mudar. Marcar na lista possíveis
   falsos positivos (por exemplo páginas contadas com Socket.IO só por vir do
   `_nav.html`).
2. **`/view/<id>/print`**: ver o que a rota devolve (PDF ou HTML) e se abre no
   tablet e no iPad.
3. **Páginas marcadas "conferir"**: `/bible`, livro e capítulo, `/help` e
   `/view/order/<date>`: ver se o conteúdo vem do servidor e quanto do JS é
   indispensável.
4. **Erro de sintaxe ou de execução?** Confirmar se o JS do `base.html`
   (`ui.js`, `csrf.js`, `i18n.js`) e o `telao_bar.js` do `_nav.html` quebram a
   página inteira ou só uma barra. Isso muda o quanto o tema precisa ser
   isolado.
5. **Tema alternável**: confirmar que dá para trocar `tokens.css`+`app.css` por
   `lite.css` sem afetar o app normal.
6. **Nos aparelhos reais**: abrir `/lite/diag`, `/login`, `/links` e
   `/view` no tablet Android e no iPad, e anotar na seção 2 as versões e o que
   falhou.
7. **Atualizar este anexo** com o resultado da conferência.

## 11. Resultado da segunda conferência (22/11/2026)

Varredura refeita com ferramentas (script em node, guardado fora do repo):
para cada página, os `extends`/`include` são seguidos e cada `.js` é lido
pelo **acorn em modo ES5**; cada `.css` passa pelo **doiuse** com os alvos
`chrome 44, ios_saf 9.3, ios_saf 5.0-5.1`. Foram 49 páginas (fora as
parciais `_*.html` e o `base.html`) e 73 arquivos JS.

1. **Varredura.**
   - **Nenhum dos 73 arquivos JS é ES5.** 36 deles nem são ES2015 (usam
     `async`, `?.`, etc.), entre eles o `csrf.js`, que vem em toda página do
     `base.html`. O Chrome 44 do tablet entende só parte do ES2015 (sem arrow
     e sem `let/const` fora do modo estrito), então para ele dá no mesmo:
     todos falham.
   - **Todas as páginas com JS carregam pelo menos um arquivo que falha.**
     A única página sem nenhum JS é `/view/<id>/print`.
   - **CSS:** as 40 páginas com o tema do app (`app_theme`) usam `var(--)`
     (de 97 a 289 usos por página, somando `app.css`, `nav.css` e o CSS
     próprio), além de grid, flex e `gap`. As telas de projetor (`/monitor`,
     `/lyrics/display/public`, `/img`, `/countdown`, `/clock`,
     `/bible/display`) quase não usam variáveis, mas dependem de flexbox e
     `vh`. Flexbox e `vh` funcionam no Chrome 44 e no iOS 9, não no iOS 5.
   - **Falsos positivos da primeira varredura:** o Socket.IO só aparece em
     muitas páginas porque o `_nav.html` carrega o `telao_bar.js`. Os módulos
     ES (`type="module"`) estão só no `view_song` e no `sheet_editor`. As
     listas A/B/C/D continuam valendo, com a mudança do item 3.
2. **`/view/<id>/print`** devolve **PDF** (`application/pdf`, WeasyPrint),
   não HTML. O Safari do iPad abre PDF na própria página. O navegador e o
   WebView do Android não mostram PDF: o arquivo é baixado e precisa de um
   app de PDF. Ainda não foi aberto nos aparelhos.
3. **Páginas marcadas "conferir":**
   - `/bible`, livro e capítulo: a lista de livros, os capítulos e os
     versículos vêm prontos do servidor. Só a busca e o toque no versículo
     precisam de JS. **Leitura funciona.**
   - `/view/order/<date>`: os itens vêm do servidor. A data do cabeçalho e
     os contadores ficam vazios sem JS. **Leitura funciona.**
   - `/help`: o conteúdo de cada tópico está **dentro do JS** (`help.js`, em
     template strings). Sem JS só aparece a página de boas-vindas. **Sai da
     lista B e vai para a C** (precisa de versão própria ou de mover o texto
     para o servidor).
4. **Erro de sintaxe derruba o quê?** Só o arquivo onde está: cada
   `<script>` é independente. O HTML continua aparecendo. Formulários com
   `csrf_token` no HTML (como o `/login`) funcionam sem JS. Os scripts
   seguintes rodam, mas dão erro ao chamar o que o arquivo quebrado
   definiria (por exemplo `ucToast`, `_t`). Então o que realmente quebra a
   página é o **CSS** (tema); o JS quebrado só tira as partes dinâmicas.
   Isso foi tirado da regra dos navegadores e do código, sem testar num
   aparelho.
5. **Tema alternável: feito (Fase 0B).**
   - Abrir qualquer página com `?lite=1` grava o cookie `uc_lite` no
     aparelho; `?lite=0` desfaz.
   - Com o cookie, as páginas que já usam o tema do app trocam
     `tokens.css`+`app.css`+`ui.js` por `static/lite/lite.css`, deixam de
     carregar o CSS próprio da página (que usa variáveis e grid) e a barra
     do alto vira `templates/lite/_nav.html` (só links).
   - Sem o cookie, nada muda: `tests/test_lite.py` confere que o `/login`
     normal sai igual.
   - O tema simples só vale nas páginas que o `lite.css` cobre: `/login`,
     `/links` e as `/lite/` (`PAGINAS_SIMPLES` em `blueprints/lite.py`). As
     outras ficam no tema normal mesmo com o cookie: sem o CSS próprio
     elas ficavam sem layout (visto no PC em 22/11).
6. **Nos aparelhos reais:** pendente. Abrir `http://IP-do-Pi:8585/lite/diag`
   no tablet e no iPad e tocar em "Mandar o resultado ao U-Control": o
   resultado aparece no log do Pi
   (`journalctl -u ucontrol-gunicorn | grep LITE_DIAG`). Depois abrir
   `/login?lite=1` e `/links`.

### O que a Fase 0/0B criou

- `blueprints/lite.py`: `/lite/diag`, `/lite/diag/relatorio` (GET, grava uma
  linha `LITE_DIAG` no log com no máximo 2.000 caracteres) e o cookie
  `uc_lite`.
- `templates/lite/diag.html`, `templates/lite/_nav.html`,
  `static/lite/diag.js` (ES5, conferido com o acorn) e `static/lite/lite.css`.
- `tests/test_lite.py`:
  - testa o diagnóstico, o relatório e a troca de tema;
  - varre `static/lite/*.css` e `static/lite/*.js` atrás do que a seção 4
    proíbe.
  - A varredura procura propriedades (`display: grid`, `gap:`…) e não a
    palavra solta "grid", porque a classe `.links-grid` precisa continuar
    existindo.
