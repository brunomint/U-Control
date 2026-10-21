# U-Control

Projeção para igrejas: letras com cifra, Bíblia, fotos, vídeos e ordem
do culto no telão, controlados pelo navegador do PC, celular ou tablet.

Um computador roda o servidor, e qualquer aparelho na mesma rede abre o
controle ou as telas pelo endereço `http://<ip>:8585`. Não precisa de
internet durante o culto.

## Instalação

### Windows

Baixe o `U-Control-Setup-x.y.z.exe` na página de
[Releases](https://github.com/brunomint/U-Control/releases/latest) e
instale. O programa fica na bandeja do Windows (ao lado do relógio), e
pelo menu dela você abre o Controle e as telas (telão e retorno de
palco), que vão para o segundo monitor em tela cheia.

Os dados ficam em `%APPDATA%\U-Control`. Instalar uma versão nova por
cima não apaga nada.

### Raspberry Pi / Linux

```sh
git clone https://github.com/brunomint/U-Control.git
cd U-Control
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/python scripts/patch_flask_socketio.py
./ucontrol.sh
```

O `ucontrol.sh` aplica as migrations do banco e sobe o gunicorn (ver
`gunicorn.conf.py`); no Pi ele roda como serviço do systemd.
O `ffmpeg` (pacote do sistema) é usado para vídeos de PowerPoint e
áudio do YouTube; o LibreOffice, para converter apresentações.

### Docker

```sh
docker compose up -d
```

Dados em `docker-data/` (ver `docker-compose.yml`).

### Primeiro acesso

Numa instalação nova, a tela de login pede para criar o primeiro usuário.
Os outros se cadastram depois em **Usuários**.

## Bíblias

Vêm incluídas só traduções de licença aberta ou de domínio público, como
a Bíblia Livre e a Nova Bíblia Viva. Traduções com direitos autorais
(NVI, ACF, ARC...) podem ser adicionadas por quem tem o direito de usá-las:
veja [bibles/LICENSES.md](bibles/LICENSES.md).

## Desenvolvimento

```sh
venv/bin/pip install -r requirements-dev.txt
venv/bin/pytest
```

O instalador do Windows é montado pelo GitHub Actions
(`.github/workflows/build-windows.yml`). Uma tag `vX.Y.Z`, igual ao
arquivo `VERSION`, publica uma Release.

## Licença

[MIT](LICENSE) para o código. As Bíblias incluídas têm as licenças
listadas em [bibles/LICENSES.md](bibles/LICENSES.md).
