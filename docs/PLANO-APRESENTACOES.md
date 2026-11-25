# Plano: Apresentações (diretoria, ministérios, relatórios)

Pedido do Bruno (25/11/2026): mostrar no telão, com os fundos dos temas, coisas
como os nomes da diretoria e os valores dos dízimos. Decisão: não criar uma
página por assunto; evoluir os **Avisos em slides** para **Slides** (`/slides`).

> Nome final: **Slides** ("Slides: avisos e listas"), não "Apresentações" —
> no U-Control "Apresentação" já é o PowerPoint animado (`/apresentacao`).
> Código: `slides_store.py`, `blueprints/slides.py`, `static/js/slides_render.js`,
> `templates/slides.html`. Etapa 1 feita em 25/11 (escolhas do Bruno: cada
> conjunto escolhe sozinho/na mão; cada lista escolhe as linhas por tela).

## Hoje

- `/avisos`: UMA lista de textos (`AvisosConfig`), um tema, segundos por slide,
  ordem aleatória. Passa sozinho em loop no telão do público
  (`display_public.js`, evento `avisos_exibir`).
- No Pi os avisos estão vazios e nunca foram exibidos (conferido em 25/11):
  nada a migrar além da configuração vazia.

## Etapa 1 (feita): conjuntos com nome + slide do tipo Lista

- **Várias apresentações guardadas**, cada uma com nome, tema (inclusive os
  animados), tempo por slide e um jeito de passar:
  - *sozinha* (como os avisos, em loop), ou
  - *na mão* (botões Anterior/Próximo na página e no Controle).
- **Tipos de slide:**
  - *Texto* — o aviso de hoje (mesma formatação: `**negrito**`, `{amarelo}`…).
  - *Lista* — um título ("Diretoria 2026") e linhas de duas partes
    ("Presidente" / "Fulano de Tal"). Se não couber numa tela, divide sozinho
    em várias, repetindo o título ("Diretoria 2026 · 2/3").
- **Página `/slides`** no lugar de `/avisos` (o endereço antigo leva
  para a nova). À esquerda a lista de apresentações; à direita o editor com a
  prévia ao vivo (o mesmo desenho do telão), igual ao editor de temas.
- **Os Avisos viram um conjunto chamado "Avisos"**, já criado.
- A última tela de uma lista dividida ganha linhas invisíveis: a letra fica do
  mesmo tamanho em todas as telas da lista.
- **Onde aparece:** telão do público. Palco e OBS não mostram (como hoje).
  Versão simples (lite): a lista vira texto ("Presidente: Fulano").
- Próximo/Anterior do Stream Deck passam os slides que estão na mão; exibir
  um conjunto pelo nome fica para a etapa 2, junto com Valores e Meta.

## Etapa 2 (depois)

- *Valores* — linhas "Entradas" / "R$ 12.340,00", com R$ formatado e alinhado.
- *Meta* — barra de progresso ("Reforma: R$ 31.000 de R$ 50.000 — 62%").
- **Sem campo de nome nos valores**: só totais da igreja, nunca valor por
  pessoa (dízimo é dado pessoal; no telão expõe e constrange).
- Atalhos do Stream Deck e do controle simples.

## Dados

Tabela nova `conjunto_slides` (id, nome, tema_id, segundos, automatica,
embaralhar, slides JSON). Um slide: `{"tipo": "texto", "texto": "..."}` ou
`{"tipo": "lista", "titulo": "...", "linhas": [["Presidente", "Fulano"], ...]}`.
Migração Alembic cria a tabela e copia o `avisos_config` para "Avisos".
