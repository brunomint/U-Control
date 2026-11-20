# App U-Control Equipe (Android)

Status: **etapa 1 no celular do Bruno (20/11); etapa 2 (salvos e playlists) pronta para testar (20/11/2026)**. Código em `android-equipe/`, rota do servidor em `blueprints/app_equipe.py`.

## Para quem é

Músicos, dirigentes e operadores, no celular de cada um. O app do telão (`static/U-Control-Screen.apk`, código em `site-igreja/android-webview`) **continua separado e sem mudanças**: ele roda nas TVs, e uma novidade para os músicos nunca pode derrubar o telão.

Os dois apps têm identificação diferente no Android (`com.ucontrol.equipe` e `com.suaigreja.webview`) e podem ficar no mesmo aparelho.

## Como o app funciona

É um "navegador embutido": mostra as páginas que o U-Control já tem, sem barra de endereço. O que muda no U-Control aparece no app na hora, sem lançar versão nova do app. A parte do Android cuida do que o navegador sozinho não faz:

- **Achar a igreja:** primeiro o endereço salvo; senão, procura na rede do Wi-Fi (testa a porta 8585 e confirma em `/api/identidade`); senão, a pessoa digita o IP ou o site. O mesmo servidor no cabo e no Wi-Fi aparece uma vez só (campo `id`).
- **Arquivos:** escolher foto, baixar PDF (inclusive os que a página gera, como o PDF da ordem), imprimir pela impressão do Android.
- **Tela acesa** enquanto uma cifra (`/view…`) está aberta.
- **Links de fora** (YouTube, WhatsApp) abrem no app certo.

## Decisões do Bruno (19/11)

| Pergunta | Decisão |
|---|---|
| Um app ou dois? | **Dois.** O do telão fica como está. |
| Login para os músicos? | **Não.** Ler cifras é aberto, como o /view. Para avisos, a pessoa toca no próprio nome uma vez. |
| Avisos com o app fechado | **Firebase** (Google, gratuito) — na etapa 3. |
| Confirmar escala | **Sim**, com link de convite pessoal pelo WhatsApp — etapa 4. |

## Etapas

1. **Base — feito.** Achar a igreja, salvar o endereço, menu (Cifras do culto, Próximo culto, Agenda e escalas, Entrar como operador, Trocar de igreja), arquivos, impressão, tela acesa, página sem conexão.
2. **Salvos no celular — feito (20/11).** Ver "Salvos e playlists" abaixo.
3. **Avisos.** "Quem é você?" (nomes das escalas). Escala, ordem que mudou, ensaio, lembrete na véspera. Precisa: projeto Firebase na conta do Bruno; decidir a proteção do `/api/orders` (em aberto) — se fechar, o app ganha uma chave própria.
4. **Extras.** Confirmar escala (link de convite), pedal Bluetooth para virar a página, botão "pôr na agenda do celular". A rolagem automática já existe na página da cifra.

Cada etapa é testada no emulador e no celular de verdade antes da seguinte.

## Salvos e playlists (etapa 2)

Pedido do Bruno: salvar permanentemente, num banco próprio do app, "esquema Cifra Club", com várias playlists com nome.

- **Banco SQLite do app** (`Banco.kt`), um por igreja (`id` do /api/identidade), em `files/salvos/<id>/`. Tabelas: cultos, músicas, playlists e os arquivos das páginas salvas.
- **Como salva** (`Gravador.kt`): abre a página num navegador invisível e guarda tudo o que ela carrega (HTML, CSS, JS, fontes, `/load?date=`). Sem internet, a `PaginaActivity` entrega esses arquivos: a cifra funciona igual (tom, rolagem, partitura), sem copiar código do U-Control para o app. Conteúdo em arquivos por hash (`Acervo.kt`): o CSS de 50 cifras é um arquivo só.
- **O que salva** (`Sincronia.kt`, quando o app abre com conexão, no máximo a cada 5 min, ou "Atualizar agora"): os cultos dos próximos 15 dias com música (`/api/app/salvar`) e as músicas das playlists (`/api/app/musicas`). Só baixa de novo o que mudou (`versao` de cada culto/música, ou U-Control atualizado). O `last_played` não conta como mudança.
- **Permanente:** sem conexão nada é apagado. Culto passado fica até a pessoa apagar (segurar na lista); culto futuro que sumiu da agenda da igreja sai. Música apagada no U-Control continua na playlist.
- **Playlists:** botão "+ Salvar na playlist" na página da cifra (só no app, posto pela `ponte.js`) ou "Adicionar música" (busca no U-Control; sem conexão, entre as já salvas). Arrastar ≡ muda a ordem, deslizar tira. "Tocar" abre com a barra anterior/próxima.
- **Sem conexão:** "Salvos no celular" no menu e na tela de busca da igreja. Uma página aberta normalmente que falha por falta de conexão cai na versão salva, se houver. Faixa no topo: "Versão salva no celular em …".
- Precisa do U-Control com `/api/app/salvar` (api 2). Num servidor antigo, o app diz "Sem conexão com o U-Control" e só mostra o que já tinha.

## Distribuição — em aberto

Só o link no U-Control (como o APK do telão) ou também a Play Store (taxa única de US$ 25 e revisão do Google).

## Montar e testar

```
cd android-equipe
JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 ./gradlew testDebugUnitTest assembleDebug
# APK: app/build/outputs/apk/debug/app-debug.apk
```

- Precisa do Java 17 e do Android SDK (`local.properties` com `sdk.dir`, fora do Git).
- No emulador, o computador é `10.0.2.2`: um U-Control rodando aqui na porta 8585 é achado pela busca.
- A versão de teste deixa inspecionar a página pelo Chrome do computador (`chrome://inspect`).
- O APK de teste é assinado com a chave de desenvolvimento deste computador. Para distribuir, criar uma chave própria do app e **guardar bem**: sem ela, uma versão nova não instala por cima.

## Cuidados conhecidos

- A primeira página aberta carrega o motor do Chrome; o menu já o carrega antes (`MenuActivity.aquecerNavegador`). No emulador com pouca memória isso chegou a passar de 5 s.
- A busca só varre redes até /22 (1024 endereços). Rede maior: digitar o endereço.
- O servidor precisa ter `/api/identidade` (U-Control desta versão em diante). Um U-Control antigo não é achado pela busca nem aceito ao digitar.
