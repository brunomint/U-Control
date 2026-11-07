# Como contribuir com o U-Control

Obrigado pelo interesse! O U-Control nasceu para resolver o telão e o
retorno de palco de uma igreja e hoje é usado nos cultos de verdade, então
toda ajuda é bem-vinda: código, tradução, documentação, testes ou só
contar como foi instalar.

🇺🇸 *English speakers are welcome too: issues and pull requests in English
are fine.*

## Por onde começar

- Veja as issues com a etiqueta
  [`good first issue`](https://github.com/brunomint/U-Control/labels/good%20first%20issue):
  são tarefas pequenas e bem descritas, boas para conhecer o projeto.
- Achou um problema ou tem uma ideia? Abra uma
  [issue](https://github.com/brunomint/U-Control/issues) antes de começar
  algo grande, para a gente conversar sobre o caminho.

## Rodar no seu computador

Precisa de Python 3.10 ou mais novo (o CI usa o 3.11).

```sh
git clone https://github.com/brunomint/U-Control.git
cd U-Control
python3 -m venv venv
venv/bin/pip install -r requirements-dev.txt
venv/bin/python scripts/patch_flask_socketio.py
venv/bin/flask --app main db upgrade
UCONTROL_DEBUG=1 venv/bin/python main.py
```

Abra `http://127.0.0.1:8585`. Na primeira vez, a tela de login pede para
criar o primeiro usuário. O banco de desenvolvimento fica em `instance/`
e não vai para o Git.

Para vídeos de PowerPoint e áudio do YouTube é preciso o `ffmpeg`; para
converter apresentações, o LibreOffice (veja o README). O resto funciona
sem eles.

Com Docker: `docker compose up -d --build` sobe o seu código, e
`docker compose run --rm test` roda os testes dentro do container.

## Testes

```sh
venv/bin/pytest
```

O GitHub Actions roda os mesmos testes em todo push e pull request. Se
você mudou um comportamento, acrescente ou ajuste um teste em `tests/`.

Rodar os testes regenera as imagens em `static/qrcodes/`. Descarte essa
mudança antes de commitar: `git checkout -- static/qrcodes`.

## Como o código é organizado

| Onde | O quê |
|---|---|
| `main.py` | Cria o app Flask e o Socket.IO e registra os blueprints |
| `blueprints/` | As rotas, separadas por área (`songs.py`, `bible.py`, `agenda.py`…) |
| `models*.py`, `migrations/` | Banco (SQLAlchemy + Flask-Migrate) |
| `*_store.py`, `telao.py`, `display_state.py` | Estado do telão e regras que não são rota |
| `templates/` | Páginas (Jinja2) |
| `static/js/pages/`, `static/css/pages/` | JS e CSS de cada página |
| `static/js/` | Módulos compartilhados (`chord_lines.js`, `sheet_render.js`…) |
| `translations/` | Tradução da interface (veja abaixo) |
| `tests/` | Testes (pytest) |

Algumas combinações para manter o projeto organizado:

- **Sem JS ou CSS grande dentro do template.** O JS de uma página vai em
  `static/js/pages/<pagina>.js` e o CSS em `static/css/pages/<pagina>.css`.
- **Nada copiado entre arquivos.** Se a mesma lógica serve a duas páginas,
  ela vira um módulo em `static/js/` (ou um `.py` compartilhado).
- **CSS e JS das páginas com `versioned_static`**, não `url_for` direto,
  para o navegador não ficar com a versão antiga em cache.
- **Mudanças pequenas e focadas.** Um pull request por assunto é mais
  fácil de revisar e de testar num culto.
- **Mexeu no banco?** Crie a migration com
  `venv/bin/flask --app main db migrate -m "o que mudou"` e confira o
  arquivo gerado.

## Tradução

O texto em português do próprio código é a chave. Em
`translations/<idioma>.json` fica `"texto em português": "tradução"`; o
que não estiver lá aparece em português. Nas páginas use
`{{ _('Salvar música') }}`, no Python `from i18n import gettext as _` e
no JS `_t('Salvar música')`. Detalhes no começo de `i18n.py`.

Letras, Bíblias e nomes cadastrados pela igreja não são traduzidos.

## Pull requests

1. Faça um fork e crie uma branch a partir do `main`.
2. Rode `venv/bin/pytest` antes de enviar.
3. Na descrição, diga o que mudou e como testar. Um print ajuda quando a
   mudança é visual.

Antes de chegar aos usuários, toda mudança é testada num culto de
verdade, então às vezes a revisão leva alguns dias. Não é desinteresse!

## Licença

Ao contribuir, você concorda que sua contribuição fica sob a
[licença MIT](LICENSE) do projeto.
