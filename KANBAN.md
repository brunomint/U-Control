# U-Control — Status do Projeto

> Software de mídia para cultos, rodando em Raspberry Pi com Flask + SocketIO.
> Atualizado em: julho/2026 (sessão 4)

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
- **Cronômetro de contagem regressiva** (`/countdown`) — texto livre, pausar/retomar/reiniciar, persiste em `countdown_config.json`
- **Slideshow automático** — imagens avançam por intervalo configurado; vídeos aguardam o fim antes de avançar (`video_ended` via SocketIO com debounce)
- **Avisos em ticker** — texto rolando na base da tela em amarelo, tamanho proporcional ao texto; exibe separadamente no público, no monitor ou em ambos via SocketIO rooms; persiste em `ticker_config.json`; botões: Exibir, Parar, Limpar
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
- **Deploy**: `scripts/deploy.py` (paramiko/SSH) — roda localmente, conecta no Pi, faz `git reset --hard` na branch, reinstala dependências, reaplica o patch do flask_socketio e reinicia o serviço via systemd (detecta o nome do serviço automaticamente). Precisa de `pip install -r requirements-dev.txt` local antes de usar. Use `--dry-run` pra ver o plano sem conectar em lugar nenhum.
- **Gunicorn com 1 worker só**: `main.py` mantém ~20 variáveis globais em memória (ticker, countdown, vídeo, cache de display, clientes socketio) sem fila de mensagens compartilhada. Rodar mais de um worker faria cada processo ter sua própria cópia desse estado, quebrando a sincronização entre painel de controle e telas — não "otimizar" aumentando `workers` em `gunicorn.conf.py` sem antes resolver isso (ex: mover o estado pra um Redis compartilhado).
