# Bíblias incluídas no U-Control

A licença MIT do U-Control vale para o código, não para estes textos. Só
entram aqui traduções de licença aberta ou em domínio público:

| Arquivo | Tradução | Licença |
|---|---|---|
| `blivre.json` | Bíblia Livre (2018), Diego Santos, Mario Sérgio e Marco Teles | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) — [ebible.org/porbr2018](https://ebible.org/porbr2018) |
| `nbv.json` | Biblica® Open Nova Bíblia Viva (2007), © Biblica, Inc. | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) — [ebible.org/poronbv](https://ebible.org/poronbv) |
| `en_kjv.json` | King James Version (1769) | Domínio público |
| `en_bbe.json` | Bible in Basic English (1965) | Domínio público |
| `ru_synodal.json` | Tradução Sinodal russa (1876) | Domínio público |
| `zh_cuv.json` | Chinese Union Version (1919) | Domínio público |
| `ar_svd.json` | Smith & Van Dyke, árabe (1865) | Domínio público |

O crédito das traduções CC aparece no telão junto da referência
(`credit` em `books_metadata.json`), como as licenças pedem.

## Outras traduções (NVI, ACF, ARC...)

Traduções com direitos autorais não podem ser distribuídas aqui. Quem tem
o direito de usá-las coloca o arquivo `<nome>.json` (mesmo formato destes)
na pasta privada, fora do git, e o U-Control passa a mostrá-la:

- Raspberry Pi / Linux / Docker: `instance/bibles/`
- Windows (instalador): `%APPDATA%\U-Control\instance\bibles\`

O nome do arquivo precisa estar em `translations` no `books_metadata.json`
(NVI, ACF, AA, ARC e KJA já estão). Para converter um texto em USFM (como
os do ebible.org) veja `scripts/usfm_para_json.py`.
