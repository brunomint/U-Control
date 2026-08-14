"""Registro único de navegação do app — ver .claude/plans/harmonic-mixing-breeze.md.

Antes desta reorganização existiam 4 listas de rotas mantidas à mão em
separado (o gerador de QR code em main.py, utils.py:exibir_links(), o
grid fixo do dashboard.html, o sidebar do control.html), nenhuma batendo
exatamente com as outras — toda rota nova precisava ser adicionada em
até 4 lugares pra ficar "descobrível". NAV_ITEMS é a fonte única; os
outros três lugares agora leem daqui.

Cada item tem `contexts` (onde ele aparece):
  - "nav": barra de navegação principal (templates/_nav.html), agrupada
    por `group`. Só páginas que fazem sentido como "ir pra lá e ficar"
    entram aqui — não as telas de exibição passiva (monitor/img/
    presenter/lyrics-display/*), que continuam sem navegação própria de
    propósito (são telas de projetor, ninguém clica nelas durante o
    uso).
  - "launcher": submenu "Links" do sidebar de control.html — o operador
    abre essas telas em nova aba enquanto mantém o painel de controle
    aberto. Inclui as telas de exibição passiva, que fazem sentido como
    ALVO de lançamento mesmo sem terem nav própria.
  - "qr": gera QR code estático (main.py:gerar_qrcodes) — subconjunto
    curado, igual à lista original hardcoded (não é "todo item nav+
    launcher", só o que faz sentido escanear com celular pra abrir em
    outro aparelho).
Um item pode estar em ambos, num só, ou (raro) em nenhum dos dois — só
existindo pra outros consumidores futuros de NAV_ITEMS.

`group` (só relevante pros itens com "nav" em contexts): ao_vivo |
preparar | agenda | sistema — vira o agrupamento visual da barra.
"""

NAV_ITEMS = [
    # ── Ao vivo ──────────────────────────────────────────────────────
    {
        "endpoint": "display.control", "label": "Controle", "icon": "fa-sliders",
        "group": "ao_vivo", "login_required": True, "contexts": ["nav", "qr"],
    },
    {
        "endpoint": "orders.order_list", "label": "Ordem do Culto", "icon": "fa-list-ol",
        "group": "ao_vivo", "login_required": True, "contexts": ["nav", "launcher", "qr"],
    },
    {
        "endpoint": "songs.list_songs", "label": "Biblioteca de Música", "icon": "fa-music",
        "group": "ao_vivo", "login_required": True, "contexts": ["nav", "launcher", "qr"],
    },
    {
        "endpoint": "bible.bible_home", "label": "Bíblia", "icon": "fa-book-bible",
        "group": "ao_vivo", "login_required": True, "contexts": ["nav", "qr"],
    },

    # ── Preparar (antes do culto) ────────────────────────────────────
    {
        "endpoint": "songs.new_song", "label": "Nova Música", "icon": "fa-plus",
        "group": "preparar", "login_required": True, "contexts": ["nav"],
    },
    {
        "endpoint": "songs.sheet_editor", "label": "Editor de Partitura", "icon": "fa-file-music",
        "group": "preparar", "login_required": True, "contexts": ["nav"],
    },
    {
        "endpoint": "orders.order_new", "label": "Nova Ordem", "icon": "fa-calendar-plus",
        "group": "preparar", "login_required": True, "contexts": ["nav"],
    },

    # ── Agenda de equipes ────────────────────────────────────────────
    {
        "endpoint": "agenda.agenda_dashboard", "label": "Agenda de Equipes", "icon": "fa-calendar-days",
        "group": "agenda", "login_required": True, "contexts": ["nav"],
    },

    # ── Sistema ──────────────────────────────────────────────────────
    {
        "endpoint": "auth.dashboard", "label": "Início", "icon": "fa-house",
        "group": "sistema", "login_required": True, "contexts": ["nav", "launcher"],
    },
    {
        "endpoint": "utils.exibir_links", "label": "Links / QR", "icon": "fa-qrcode",
        "group": "sistema", "login_required": False, "contexts": ["nav"],
    },
    {
        "endpoint": "utils.historico", "label": "Histórico", "icon": "fa-clock-rotate-left",
        "group": "sistema", "login_required": True, "contexts": ["nav"],
    },
    {
        "endpoint": "auth.visualizar_usuarios", "label": "Usuários", "icon": "fa-users",
        "group": "sistema", "login_required": True, "contexts": ["nav", "launcher"],
    },
    {
        "endpoint": "utils.help", "label": "Ajuda", "icon": "fa-circle-question",
        "group": "sistema", "login_required": False, "contexts": ["nav", "qr"],
    },

    # ── Telas de exibição passiva (só como alvo de lançamento do
    #    control.html — nunca na barra "nav", de propósito) ──────────
    {
        "endpoint": "lyrics.lyrics_display", "label": "Visualização das Canções", "icon": "fa-tv",
        "group": None, "login_required": False, "contexts": ["launcher", "qr"],
    },
    {
        "endpoint": "lyrics.lyrics_display_Public", "label": "Texto para o Público", "icon": "fa-tv",
        "group": None, "login_required": False, "contexts": ["launcher"],
    },
    {
        "endpoint": "lyrics.lyrics_display_obs", "label": "Overlay OBS (fundo transparente)", "icon": "fa-video",
        "group": None, "login_required": False, "contexts": ["launcher"],
    },
    {
        "endpoint": "display.monitor", "label": "Retorno de Palco", "icon": "fa-tv",
        "group": None, "login_required": False, "contexts": ["launcher", "qr"],
    },
    {
        "endpoint": "display.serve_image", "label": "Visualização de Imagens", "icon": "fa-image",
        "group": None, "login_required": False, "contexts": ["launcher", "qr"],
    },
    {
        "endpoint": "lyrics.presenter", "label": "Controle de Imagens", "icon": "fa-image",
        "group": None, "login_required": False, "contexts": ["launcher", "qr"],
    },
    {
        "endpoint": "utils.clock", "label": "Relógio", "icon": "fa-clock",
        "group": None, "login_required": False, "contexts": ["launcher"],
    },
    {
        "endpoint": "countdown.countdown_page", "label": "Cronômetro (tela)", "icon": "fa-hourglass-half",
        "group": None, "login_required": False, "contexts": ["launcher"],
    },
    {
        "endpoint": "bible.bible_display", "label": "Bíblia (tela)", "icon": "fa-tv",
        "group": None, "login_required": False, "contexts": ["launcher", "qr"],
    },

    # ── Página pública compartilhável (não é tela de projetor nem item
    #    de navegação — link/QR pra ordem do culto do dia) ───────────
    {
        # Registrada direto em main.py (@app.route, não blueprint) —
        # endpoint sem prefixo, é só o nome da função.
        "endpoint": "view_song_order", "label": "Visualização Pública", "icon": "fa-eye",
        "group": None, "login_required": False, "contexts": ["qr"],
    },
]

GROUP_LABELS = {
    "ao_vivo": "Ao Vivo",
    "preparar": "Preparar",
    "agenda": "Agenda",
    "sistema": "Sistema",
}

GROUP_ORDER = ["ao_vivo", "preparar", "agenda", "sistema"]


def items_for_context(context, logged_in):
    """Itens de um contexto ("nav"/"launcher"), respeitando login_required
    quando o visitante não está autenticado."""
    return [
        item for item in NAV_ITEMS
        if context in item["contexts"] and (logged_in or not item["login_required"])
    ]


def qr_endpoints():
    """Endpoints marcados pra gerar QR code (main.py:gerar_qrcodes) —
    sem noção de login, é geração de imagem estática no startup, não
    uma requisição de usuário."""
    return [item["endpoint"] for item in NAV_ITEMS if "qr" in item["contexts"]]


def grouped_nav_items(logged_in):
    """Itens de contexto "nav" agrupados na ordem de GROUP_ORDER, pronto
    pra `templates/_nav.html` iterar — cada grupo já vem com label e
    lista de itens; grupos sem nenhum item visível (ex. tudo exige login
    e o visitante está deslogado) são omitidos."""
    items = items_for_context("nav", logged_in)
    groups = []
    for key in GROUP_ORDER:
        group_items = [i for i in items if i["group"] == key]
        if group_items:
            groups.append({"key": key, "label": GROUP_LABELS[key], "links": group_items})
    return groups
