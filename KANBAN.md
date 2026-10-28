# U-Control — Status do Projeto

> Software de mídia para cultos, rodando em Raspberry Pi com Flask + SocketIO.
> Atualizado em: agosto/2026 (sessão 5 — migração JSON→SQL)

---

## ✅ Funcionalidades prontas

### Display / Monitor
- Exibição de imagens, vídeos e URLs na tela do monitor
- Tela dividida (duas URLs ou imagem + URL)
- Blackout (tela preta)
- Modo monitor de palco — envia conteúdo só ao `/monitor`, sem afetar o público
- Sincronização de estado ao reconectar (`/api/monitor/sync`)
- Relógio full-screen (`/clock`)
- APK Android para TVs e celulares (`/static/U-Control-Screen.apk`)
- **Cronômetro de contagem regressiva** (`/countdown`) — texto livre, pausar/retomar/reiniciar, persiste na tabela `CountdownConfig`
- **Slideshow automático** — imagens avançam por intervalo configurado; vídeos aguardam o fim antes de avançar (`video_ended` via SocketIO com debounce)
- **Avisos em ticker** — texto rolando na base da tela em amarelo, tamanho proporcional ao texto; exibe separadamente no público, no monitor ou em ambos via SocketIO rooms; persiste na tabela `TickerConfig`; botões: Exibir, Parar, Limpar
- **Importar slides PPTX** — upload de `.pptx` converte automaticamente via LibreOffice + fitz; cada slide vira JPEG na galeria, pronto para o slideshow automático
- **Exportar ordem do culto** — botões em `/view/order/<data>`: PDF (jsPDF, download direto), WhatsApp (texto formatado com negrito copiado), Imprimir, Copiar Link

### Letras de Músicas
- Cadastro, edição e exclusão de músicas
- Editor de partitura (VexFlow via `/sheet_editor`)
- Seções de letras com navegação por seção
- Presenter mode (`/presenter`) — visão do apresentador com próxima seção
- Display público (`/lyrics/display/public`) — tela da congregação
- Controle de visibilidade das letras (mostrar/esconder sem trocar de tela)
- Busca de músicas

### Bíblia
- Navegação por livros, capítulos e versículos
- Busca por texto
- Múltiplas traduções (AA, ACF, ARC, NVI e outras)
- Display de versículo em tela cheia (`/bible/display`)
- Adicionar versículo à ordem do culto

### Agenda / Ordem do Culto
- Agenda por data com seções: Louvor, Mídia, Eventos
- Edição da ordem do culto
- Visualização da ordem (`/order`)

### Galeria de Imagens
- Upload de imagens (múltiplos arquivos)
- Organização em pastas
- Exibição em tela cheia via `/img`
- Exclusão individual ou em lote

### Áudio
- Download de MP3 via YouTube
- Lista de áudios baixados
- Reprodução e exclusão

### Cifras
- Exibição de cifra com vídeo de suporte lado a lado (`/cifra_com_video`)
- Links úteis (`/links`)

### Sistema
- Login e controle de usuários
- Status do servidor em tempo real (CPU, RAM, disco)
- Deploy via script Python (paramiko/SSH → Pi)
- Servidor: gunicorn (1 worker, gthread) + threading, porta 8585
- Acesso remoto via Cloudflare Tunnel (`ucontrolibrjoaoxxiii.com`)
- Acesso local via Tailscale (`100.64.46.84`) e rede local (`192.168.0.35:8585`) — gunicorn em `0.0.0.0:8585`
- **Opção de instalar via Docker** (`Dockerfile`/`docker-compose.yml`, 2026-08-14) — forma ADICIONAL de rodar o app, não substitui o `ucontrol.sh`/systemd no Pi. `docker compose up -d` builda e sobe; `docker compose run --rm test` roda a suíte dentro do container. Mesmo padrão do projeto `fileswift` do usuário (Dockerfile multi-stage `test`/`prod`).

---

## 🔧 Melhorias identificadas (não críticas)

| Funcionalidade | Valor prático | Esforço estimado |
|---|---|---|
| ~~**Timer de sermão / countdown**~~ | ~~Alto~~ | ✅ Feito |
| ~~**Slideshow automático**~~ | ~~Médio~~ | ✅ Feito |
| ~~**Avisos em ticker**~~ | ~~Médio~~ | ✅ Feito |
| ~~**Exportar ordem do culto**~~ (PDF ou texto) | ~~Médio — compartilhar com a equipe~~ | ✅ Feito |
| ~~**Histórico do culto**~~ (o que foi exibido) | ~~Baixo — auditoria~~ | ✅ Feito |
| ~~**Importar slides**~~ (PPT/Google Slides) | ~~Baixo — URLs de apresentação já funcionam via iframe~~ | ✅ Feito |
| **Câmera ao vivo** (RTSP/webcam) | Baixo para igrejas menores | Alto |

## 📋 Próximos (fila)

Versões pequenas, de 2–3 itens cada.

- [x] **Problemas achados no uso da 1.0.9**: botões Preta/Branca/Logo
      ligavam sozinhos (conflito de `data-tela` com o aviso e o "Abrir no
      datashow") — corrigido, e agora dá pra escolher Público/Palco/Os dois.
      Falta lançar (1.0.10).
- [ ] **Aposentar o eventlet** (o projeto está só em manutenção e desencoraja
      uso novo). No `gunicorn.conf.py`: `worker_class = "gthread"` e
      `threads = 100`; depois tirar `eventlet` do `requirements.txt`. Testado
      em 2026-10-27, só localmente: o travamento de agosto era o gunicorn
      com 1 thread (o padrão), que a primeira conexão do Socket.IO ocupava.
      Com 100 threads, 5 telas abertas e WebSocket de verdade funcionaram.
      Ir numa versão só com isso, fácil de desfazer no Pi.
- [ ] **Capotraste só no `/view/<id>`**, ao lado do botão Tom (pedido em
      2026-10-28). Tirar do monitor (`static/js/capo.js` + gancho no
      `display.js`): o monitor costuma ser uma TV no palco vista por todos
      (o capo do violonista mudaria os acordes do tecladista), e ninguém
      toca nela. Tela pública não tem acordes. Reaproveitar o `capo.js`
      (localStorage `ucCapo`, por aparelho).
- [ ] **Quebra de slide com `||`** dentro da seção (ideia do OpenSong).

---

## 🏗️ Arquitetura resumida

```
Raspberry Pi
├── Flask + Flask-SocketIO (async_mode=threading)
├── Gunicorn — porta 8585
├── SQLite — banco de dados local
└── Cloudflare Tunnel → ucontrolibrjoaoxxiii.com

Clientes
├── /control      — painel do operador
├── /monitor      — tela do palco (TV/monitor de palco)
├── /lyrics/display/public — projeção para a congregação
├── /presenter    — visão do apresentador
└── APK Android   — acesso às telas acima via WebView
```

---

## Observações técnicas

- **Flask 3.x / Flask-SocketIO 5.6.0**: incompatibilidade com `RequestContext.session` resolvida com patch direto em `venv/lib/.../flask_socketio/__init__.py` no Pi (`ctx.session` → `ctx._session`).
- **X-Frame-Options**: URLs externas com esse header não carregam em iframes de browsers; o APK Android (WebView) ignora esse header e funciona normalmente. URLs do Horlyrics permitem embedding.
- **Caminho real do projeto no Pi**: `/home/piano-25/14.3_calendario_U-Control` (usuário SSH `piano-25`, acessível via Tailscale em `100.64.46.84`) — o `ucontrol.sh` é a fonte da verdade pra esse caminho; uma versão antiga desta seção citava `/home/pi/U-Control`, que estava desatualizada/errada.
- **Banco de dados**: SQLite em `ucontrol.db` dentro do caminho acima. Desde 2026-08-07 o schema é versionado com Flask-Migrate/Alembic (`migrations/`) — pra adicionar/mudar coluna, gerar migration com `flask --app main db migrate -m "..."` e commitar o arquivo gerado em `migrations/versions/`. `ucontrol.sh` já roda `flask --app main db upgrade` antes de subir o gunicorn, então basta dar deploy normalmente pra aplicar.
  **Rollout no Pi pela primeira vez:** o hack antigo de `ALTER TABLE ... ADD COLUMN media_type` já rodava em produção há um tempo, então a coluna provavelmente já existe lá — rodar `flask db upgrade` direto pode falhar com "coluna já existe". Antes de rodar pela primeira vez: `sqlite3 ucontrol.db ".schema display_state"` — se `media_type` já aparecer, rode `flask --app main db stamp head` uma única vez (marca o banco como já migrado, sem recriar nada); só depois disso `upgrade` funciona normalmente pras próximas migrations. Esse passo é manual e único — **não** faz parte do `scripts/deploy.py`.
- **Migração JSON → SQL (2026-08-08/09, Fase 5.X):** `songs.json`, `orders.json`, `order_templates.json`, `section_templates.json`, `order_of_service.json`, `display_log.json`, `settings.json`, `countdown_config.json`, `ticker_config.json`, `image_paths.json` e `urls.json` pararam de ser lidos/escritos pelo app — tudo migrou pra tabelas SQL (`Song`/`SongSection`/`SheetData`, `Order`/`OrderItem`/`EventoItem`/`OrderTemplate`/`SectionTemplate`, `DisplayLog`, `Setting`, `CountdownConfig`, `TickerConfig`, `ImagePath`, `SavedUrls`). Os 11 arquivos originais foram movidos pra `data_backup_pre_sql/` (não apagados — rede de segurança até o rollout no Pi ser validado por um tempo em uso real). `order_of_service.json` (sistema antigo, sem data) foi unificado na tabela `Order` — os botões "adicionar à ordem" da tela de bíblia e o fallback `/save`+`/load` agora miram sempre a ordem de **hoje**.
  **Rollout no Pi ainda pendente (nunca fizemos, `main` só foi testado localmente):** além do `flask db upgrade` de sempre (que cria as tabelas novas, vazias), é preciso rodar os scripts de importação uma vez contra os arquivos JSON reais do Pi (`scripts/import_*.py` — cada um lê seu(s) arquivo(s) e escreve no banco; todos com `--force` só se precisar reimportar). Sem isso, as tabelas ficam vazias e o app vai parecer ter perdido todos os dados (músicas, ordens, histórico etc.) mesmo com o schema certo. Ordem sugerida: `import_display_log.py`, `import_configs.py`, `import_countdown_ticker.py`, `import_songs.py`, `import_orders.py`. Cada script só lê o JSON de origem (nunca apaga/modifica) e aborta sem duplicar se a tabela já tiver linha.
- **Deploy**: `scripts/deploy.py` (paramiko/SSH) — roda localmente, conecta no Pi, faz `git reset --hard` na branch, reinstala dependências, reaplica o patch do flask_socketio e reinicia o serviço via systemd (detecta o nome do serviço automaticamente). Precisa de `pip install -r requirements-dev.txt` local antes de usar. Use `--dry-run` pra ver o plano sem conectar em lugar nenhum.
- **Gunicorn com 1 worker só**: `main.py` mantém ~20 variáveis globais em memória (ticker, countdown, vídeo, cache de display, clientes socketio) sem fila de mensagens compartilhada. Rodar mais de um worker faria cada processo ter sua própria cópia desse estado, quebrando a sincronização entre painel de controle e telas — não "otimizar" aumentando `workers` em `gunicorn.conf.py` sem antes resolver isso (ex: mover o estado pra um Redis compartilhado).
- **`/api/orders` é consumida pelo site da igreja**: o projeto separado `site-igreja` (`app.py:239-256`, função `_buscar_api_ucontrol()`) busca `GET https://ucontrolibrjoaoxxiii.com/api/orders` a cada 15 min (cache em `CacheAPI`) pra montar a agenda pública em ibrjoaoxxii.org (`/agenda` → `get_proximos_cultos()`/`get_eventos()`). Por isso `/api/orders` (`blueprints/orders.py:72`) é **de propósito** sem `@login_required` — não adicionar login nela sem antes ajustar o `site-igreja`, ou a agenda pública do site quebra. Nenhuma outra rota do U-Control é consumida pelo site hoje (confirmado grepando `app.py` de lá; as outras chamadas HTTP de lá são pro Icecast/rádio, sem relação).
- **Reforço de segurança (2026-08-14):** proteção CSRF (Flask-WTF, `extensions.py:csrf`), rate limiting de tentativas de login (`blueprints/auth.py`) e correção de XSS na letra pública (`view_song.html`), inspirados no projeto `fileswift` do usuário. **Rollout no Pi pendente:** `requirements.txt` ganhou `Flask-WTF`/`WTForms` — o app **não sobe sem isso instalado**, porque `csrf.init_app(app)` roda incondicionalmente em `create_app()`. Rodar `pip install -r requirements.txt` no Pi *antes* do próximo restart do serviço (o `scripts/deploy.py` já reinstala dependências como parte do fluxo normal, então um deploy via script cobre isso sozinho — só fica perigoso se alguém reiniciar o serviço manualmente sem passar pelo script).
- **Docker (2026-08-14) — achados testando de verdade com `docker build`/`docker run`:**
  - `SQLALCHEMY_DATABASE_URI = 'sqlite:///users.db'` é caminho relativo, e o Flask-SQLAlchemy resolve isso contra `app.instance_path`, não contra a raiz do projeto — o banco de verdade mora em `instance/users.db`, não em `users.db` solto. Só descoberto testando o container com volume; vale saber pra qualquer script/ferramenta que precise achar o `.db` direto (ex.: backup manual).
  - `init_countdown_state()`/`init_ticker_state()` (chamados dentro de `create_app()`, antes de qualquer request) quebravam com banco genuinamente vazio (`OperationalError: no such table`) — porque `flask --app main db upgrade` importa `main.py` pra achar o `app`, e isso já executa `create_app()` (que tenta ler as tabelas) *antes* do `upgrade` em si rodar. No Pi nunca apareceu porque o banco de lá sempre teve essas tabelas de antes. Corrigido com `try/except OperationalError` nos dois (`blueprints/countdown.py`, `blueprints/ticker.py`) — tolera tabela ainda não existir, fica com o estado default.
  - `yt-dlp` (usado por `blueprints/cifras.py` via `python3 -m yt_dlp`) não estava em `requirements.txt` — só apareceu como bug ao testar a imagem (`No module named yt_dlp`). Adicionado agora; precisa também de `ffmpeg` instalado no sistema (não é pacote pip) pra converter pra mp3 — a imagem Docker já instala os dois (`libreoffice` + `ffmpeg`, via apt, pro PPTX da galeria e pro áudio).
  - `network_mode: host` no compose é necessário pro mDNS (zeroconf, `ucontrol.local`) funcionar — rede bridge padrão do Docker não deixa multicast passar. Como consequência, a porta já sai em `0.0.0.0:8585` do host direto, sem precisar mudar nada no Cloudflare Tunnel nem no Tailscale.
