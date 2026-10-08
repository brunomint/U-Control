# Dependências vendorizadas (self-hosted)

Bibliotecas JS/CSS de terceiros baixadas e servidas localmente, em vez de
carregadas de CDN — necessário pro U-Control funcionar sem internet (só
rede local), já que ele roda em igrejas onde isso pode ser o único acesso
disponível. Antes de 2026-08 tudo vinha de CDN (cdnjs, jsdelivr, unpkg,
code.jquery.com, fonts.googleapis.com) — nenhuma dessas 14 URLs sobrou em
nenhum template.

Versões fixadas (mesmas já em uso no projeto, sem pular versão à toa):

| Lib | Versão | Origem | Onde é usada |
|---|---|---|---|
| Socket.IO client | 4.5.4 | cdnjs | páginas com sync ao vivo (control, monitor, lyrics, etc.) |
| Font Awesome | 6.5.0 | cdnjs | ícones em várias páginas |
| jQuery | 3.6.0 | code.jquery.com | songs, bíblia, display |
| jsPDF | 2.4.0 | cdnjs | exportar ordem do culto em PDF |
| html2canvas | 1.4.1 | jsdelivr | captura de tela na agenda |
| Bootstrap | 5.3.0-alpha3 | jsdelivr | **sem uso** desde o tema único (o login passou pro `app.css`) — pode ser apagado |
| Manrope (fonte variável 400–800) | — | fonts.gstatic.com | tema único (`css/tokens.css`) — navbar e páginas com `app_theme`; só `latin`/`latin-ext` |
| Google Fonts (Roboto+Merriweather) | — | fonts.googleapis.com | páginas de bíblia — só subconjuntos `latin`/`latin-ext` baixados (suficiente pra português; cirílico/grego/vietnamita etc. removidos de propósito) |
| VexFlow | 4.2.2 (cjs), 4.2.2 (releases), 4.2.3 (cjs), 4.2.5 (esm) | jsdelivr/unpkg | renderização de partitura — **4 builds diferentes coexistindo de propósito**, ver nota abaixo |

## Nota sobre o VexFlow

O projeto usa VexFlow de 4 formas diferentes em páginas diferentes
(descoberto durante a vendorização, não unificado de propósito — trocar
build/versão é mudança de comportamento, não só de local do arquivo):

- `vexflow/4.2.2-cjs/vexflow.js` — usado por `display.html`, `edit_song.html`, `lyrics.html`.
- `vexflow/4.2.2-releases/vexflow-min.js` — usado por `view_song.html`.
- `vexflow/4.2.3-cjs/vexflow.js` — usado por `new_song.html`. **Corrigido durante a vendorização**: a URL original (`unpkg.com/vexflow@4.2.3/build/vexflow.min.js` + `css/vexflow.css`) estava retornando 404 há um tempo desconhecido — esses arquivos não existem no pacote 4.2.3. A build `cjs` real (mesmo padrão `Vex.Flow.*` usado no JS da página) foi baixada no lugar.
- `vexflow/4.2.5-esm/` — módulo ES completo (111 arquivos, com imports relativos entre si), usado só por `sheet_editor.html` via `import()` dinâmico. Precisa manter a estrutura de pastas `entry/` + `src/` intacta pros imports relativos funcionarem.

## Como atualizar uma versão

1. Confirmar a nova versão funciona (testar localmente com a CDN antes de baixar).
2. Baixar os arquivos novos pra dentro da pasta certa (nome da pasta pode incluir a versão, ex. `vexflow/4.3.0-cjs/`).
3. Atualizar o(s) `<script src>`/`<link href>` nos templates que apontam pra ela.
4. Rodar `pytest` + teste manual (handshake de socket real se for Socket.IO, visual se for CSS/fonte).
5. Atualizar esta tabela.
