# Pra fazer — Mesa

Ler no início de todo chat. Riscar (`[x]`) o que terminar e anotar a data.

## Esperando o usuário
- [ ] Instalar o **Equalizer APO** no notebook (download aberto no navegador em 22/10; rodar o instalador,
      marcar a saída no Configurator, reiniciar o PC).
      Depois o cartão "EQ · saída" ao lado dos faders vira o equalizador (escreve `mesa.txt` na pasta
      config do APO). Testar mexendo de leve, com música baixa.
- [ ] Recarregar a extensão em `edge://extensions` (↻ no card da Mesa) — **versão 1.5.0 (volume, medidor e saída por aba; fila do YouTube pelos dados) pede acesso
      a todos os sites** (precisa pra mexer no volume de qualquer aba): aceitar. Depois dar F5 nas abas
      que já estavam abertas (sem F5 a aba aparece, mas só o mute funciona; o painel avisa).
- [x] Spotify conectado (22/10/2026). Era: criar o app em developer.spotify.com (redirect `http://127.0.0.1:8070/spotify/callback`,
      Web API), Client ID já no `.env` (22/10). Falta: redirect URI no dashboard + autorizar em http://127.0.0.1:8070/spotify/login no notebook.
      Passo a passo no fim do `PROMPT.md`. (Abas já abertas no Edge em 22/10/2026.)
- [x] Discord conectado (22/10/2026). Era: criar o app em discord.com/developers (OAuth2: Client ID + Reset Secret, redirect
      `http://127.0.0.1`). Client ID e Secret já no `.env` (22/10); falta conferir o redirect e "Conectar" no painel e aprovar no
      Discord do notebook.
- [x] Hook do RTK instalado (27/10/2026).
- [x] Plugins carregados e Context7 testado (27/10/2026).
- [x] Correção de segurança: **aprovado o código de pareamento** (27/10/2026). Fazer agora (ver "Próximo").

## Amigo (Luiz) usando a Mesa — 22/10/2026
- Repo público: https://github.com/Oikky/mesa (branch main). Ele instalou em `C:\Users\luizg\Mesa`
  com `Instalar.bat`, usa **Opera** e a **própria rede Tailscale** (`Instalar.bat --tailscale`).
- Pra mandar atualização pra ele: commit + `git push` daqui; ele toca na seta do tablet ou roda
  `Atualizar.bat`. Mudou a extensão → ele precisa recarregar em `opera://extensions`.
- Status: Discord dele conectado (faltava o Redirect `http://127.0.0.1` no app do Discord).
  Spotify dele levou 429 e o Spotify mandou esperar 1 h (versão antiga perguntava demais; já corrigido).
- [ ] Confirmar com ele depois da 1 h: fila do Spotify e do YouTube aparecendo no Opera. Se não,
      pedir o texto de http://127.0.0.1:8070/diag do PC dele.
- [ ] Se o Spotify der 403 "conta não liberada": ele está usando o Client ID de outra pessoa → criar
      o app dele (developer.spotify.com, redirect `http://127.0.0.1:8070/spotify/callback`).

## Próximo
- [ ] **Parear o tablet de verdade**: no notebook abrir http://127.0.0.1:8070 (passo 4 mostra o código),
      digitar no tablet. Avisar o Luiz: depois do Atualizar ele vê a tela "Parear com o notebook" e faz o mesmo no PC dele.
- [ ] Testar volume por aba de verdade (depois de recarregar a extensão): duas abas tocando, sub-faders,
      painel do Edge, mute nativo, aba com WebAudio (jogo de navegador), Spotify Web.
- [ ] Conferir no Discord se o volume das pessoas bate (a call real veio com 200 = máximo da escala).
- [ ] Testar saída por aba de verdade (primeira vez num site: permitir o microfone no Edge do notebook).
- [ ] Testar a call do Discord de verdade (fotos, quem fala) e o medidor das abas com o Edge real.
- [ ] Testar os pads novos de verdade (Create 26.2 pelo CurseForge, OBS pelo atalho, Discord, VS Code).
- [ ] Ideia pra depois: "sub-canais" em outros apps com várias sessões de áudio do mesmo .exe.

## Depois
- [ ] Testar de verdade no Tab S6 Lite: vários dedos ao mesmo tempo, tela cheia, tela sem apagar,
      reconexão, vídeo sincronizado, painel, segurar pra reiniciar/desligar.
- [ ] Testar Spotify e Discord com as contas reais (ainda não rodaram com dados de verdade).
- [ ] Testar no tablet: barra lateral e gaveta (puxar, abas Saídas/Mic/Faders), três dedos pra cima
      (A <-> B, com animação), controles por cima da capa no A, cor da capa, banco de mics (arrastar
      pra baixo traz os mics).
- [ ] Conferir no tablet a fila na barra lateral (capinhas; tocar numa toca ela). No A cabem ~3, o resto rola.
- [ ] Apagar os layouts antigos O/A/C/D (CSS/JS); hoje só abrem pelo `?layout=` no endereço.
- [ ] Pads: hoje o layout E mostra só os 9 primeiros; decidir se tem página extra ou rolagem.
- [ ] Pad "Mime" do desenho: descobrir o que é (app/atalho) e o que o painel dele deve mostrar.

## Próximo
- [ ] Sugestões nos outros pads: Discord (servidores/canais), OBS (cenas), etc.
- [ ] Spotify: autorizar a Mesa de novo (segurar o pad do Spotify > "Autorizar no notebook") pra
      aparecer o que tocou antes (permissão nova `user-read-recently-played`).

## Feito (resumo)
- 27/10/2026: pareamento do tablet (`server/pairing.py`): código em `config/pair.txt`, mostrado só no
  notebook (http://127.0.0.1:8070), tablet guarda num cookie; sem ele o /ws e as imagens recusam. Origin
  checado no /ws e no /pair; endpoints da extensão recusam sites; /padbg e /icon só servem imagens.
- 27/10/2026: vibe-coding-toolkit (prompt 12) aplicado: `Checar.bat` (ruff + 21 testes pytest + ESLint),
  `docs/quality.md` e `docs/setup.md`, Graphify (grafo do código, fora do git), uv e RTK instalados,
  revisão de segurança de base (privada). Propostas separadas: quebrar `web/app.js`, winrt 4.x.
- 22/10/2026: segurar um pad (e soltar sem arrastar) abre as sugestões dele por cima dos pads:
  YouTube (o que passou no notebook, `config/history.json`), Spotify (tocou há pouco + playlists),
  Create 26.2 (mundos; escolher marca como último jogado com cópia `level.dat_mesa` e abre o jogo),
  VS Code (pastas recentes). Editar o pad: lápis na gaveta. Fila da barra anda suave (anel desliza,
  lista sobe); arrastar o player funciona no tablet; três dedos sem filter/blur (fluido).
- 22/10/2026: EQ saiu da tela (o servidor continua com `eq.py`). Faders com largura padrão (112 px,
  encolhem até 84 se faltar lugar); L/R também na aba (extensão 1.6.0: StereoPanner; recarregar + F5).
  Canal chega abrindo espaço e sai apagando/encolhendo, vizinhos deslizam. Mute = tecla do tamanho do
  fader com ícone, clara quando mudo. Segurar no nome: renomear, fixar (fica apagado sem som) ou
  arrastar pra mudar a ordem (`chpin`/`chorder` em `config/channels.json`, chave `_order`).
  Fila na barra em grupos (YouTube, Spotify, Discord), com as capas que cabem divididas entre eles.
  Vídeo do A em 16:9. "Tocando agora": só troca de app se o Windows ficar 5 s no outro; arrastar pro
  lado escolhe o app (pontinhos embaixo). Dependência nova: `winrt-Windows.Foundation.Collections`.
- 22/10/2026: medidor da aba (extensão 1.5.1) não fica mudo quando o YouTube troca de música (o
  `<video>` troca a trilha de áudio; o medidor agora passa pra trilha nova). Recarregar a extensão + F5.
- 22/10/2026: canais acendem na cor do app enquanto têm som (sobe devagar, desce mais devagar).
  Balanço L/R por app e no master (régua embaixo do nome; arrastar, dois toques centraliza).
  Cartão do EQ ao lado dos faders quando sobra espaço (some com muitos canais ou no banco de mics).
  Pads: mais fileiras quando cabe (até 15), vazias com "+". B: barra de teclas igual à da direita,
  sem a marca; vídeo na barra do player sem a miniatura atrás; fila na barra lateral.
- 22/10/2026: "tocando agora" no estilo do Spotify (A: cartão do mini player com controles por cima
  ao tocar; B: barra do player, vídeo 16:9 pequeno no lugar da capa), cor ambiente da capa/miniatura
  com P&B opcional. Teclas do rodapé viraram barra lateral no A (abas que abrem sozinhas na gaveta,
  sem empilhar parte nova). Pads quadrados e maiores. Aba do navegador igual aos outros faders.
  Banco de mics invertido (arrastar pra baixo traz os mics) e indicadores viraram mic/caixa de som.
  Três dedos com animação. E → "A" nos nomes. Spotify: a fila da playlist voltou (o Spotify desligou
  `/playlists/{id}/tracks`, que respondia 403 "Forbidden"; agora é `/items`).
- 22/10/2026: deitado, o painel da direita virou gaveta: trilho fino com os ícones de cada parte
  (quem fala na call aparece embaixo); arrastar pra esquerda ou tocar abre por cima do centro, pra
  direita ou tocar no fundo fecha. Pedido direto (rodapé, nome do canal) abre; pad só pisca o LED do
  ícone no trilho. Saídas abrem como gaveta também. Capa grande na tela, transporte no estilo do
  mini player do Spotify (play num círculo claro). Tocar em MESACONTROL não troca mais layout: três
  dedos pra cima alternam E <-> B. B refeito em cima do E (`data-deck="b"`): trilho à esquerda com as
  teclas do rodapé e a marca em pé, faixa de cima com tela larga + transporte + knob do volume geral.
- 22/10/2026: fila do YouTube lida dos dados do YouTube (`extension/yt-data.js`, mundo da página):
  vem completa até em aba de fundo, com nome do canal (antes lia a tela, que monta aos poucos).
  Parte do Spotify aparece quando a conta diz que está tocando (`spnow`, vale pro Spotify Web/Opera);
  a do YouTube quando a extensão diz que tem vídeo tocando. Diagnóstico em http://127.0.0.1:8070/diag.
- 22/10/2026: pronto pra compartilhar: repositório git próprio (main), `Instalar.bat`/`instalar.py`
  (venv, dependências, chaves no terminal, ligar com o Windows), `Atualizar.bat` (pull + deps +
  reinicia; avisa se a extensão mudou), aviso de versão nova no tablet (tecla com seta no rodapé,
  `server/updates.py`), README pro amigo. Config pessoal fica fora do git (.gitignore).
- 22/10/2026: painel sem rótulos e sem parte vazia (sem nada aberto a coluna some e faders/pads
  crescem); cada parte minimiza no cabeçalho (lembrado em `mesa.folded`; a call minimizada mostra as
  fotinhas). Pessoas da call viram faders depois do Discord (0–200). Banco de mics na coluna dos
  faders: arrastar pra baixo troca (som sobe, mics entram), LEDs na borda mostram/trocam o banco.
  Lista não rolava: `.track` do fader pegava os itens da lista (agora `.fader .track`).
  Sliders do painel não pulam mais durante o arrasto (`data-drag`).
- 22/10/2026: painel dividido em até 3 partes (o que toca · call do Discord · o que eu abri), tecla de
  mic no rodapé (mic padrão do Windows com volume/mute/medidor; mic e saída do Discord com volume,
  via `SET_VOICE_SETTINGS`), saída por aba (chip do fader da aba; `setSinkId` na página — o Edge pede
  permissão de microfone uma vez por site pra mostrar as saídas; extensão 1.4.0).
- 22/10/2026: medidor por aba (extensão 1.3.0: `captureStream()` dos `<video>/<audio>` + analisador no
  ganho do WebAudio, 10x/s pelo WS `/ext`). Call do Discord assume o painel ao entrar: fotos em grade,
  anel pulsando em quem fala, toque na pessoa = volume/mute dela. Pads: segurar e arrastar troca de
  lugar (`padMove`), segurar e soltar abre o editor.
- 22/10/2026: imagens prontas pros pads em `web/pad-presets/` (logos YouTube/Spotify, ícones de
  Discord/VS Code/OBS, foto de fone e de Acer Nitro, print da Create; créditos no CREDITOS.txt),
  escolhíveis no editor. Pads novos: VS Code, Create 26.2 (abre pelo CurseForge,
  `curseforge://launch-game?instanceId=<guid>&gameId=432`), Discord, OBS.
- 22/10/2026: config dos canais no notebook (`config/channels.json`: `name`, `hidden`, `icon`; chaves
  .exe, `master`, `dev:<id>`, `site:<domínio>`): painel "Canais" (tecla do olho) esconde qualquer
  fader, inclusive o Main, e renomeia (lápis) apps, abas, Main e saídas. Pads com fundos prontos
  (`"bg": "preset:<nome>"`, 8 neutros + 8 coloridos) escolhidos no editor; os 5 pads ganharam cor.
- 22/10/2026: volume por aba do navegador (extensão 1.2.0: script na página ajusta `<video>/<audio>`
  e WebAudio; mute é o nativo da aba), sub-faders das abas no mixer depois do canal do navegador,
  abas no painel do app do navegador (toque no nome de um canal abre o painel dele), tecla de olho
  no rodapé pra escolher quais faders aparecem, fader só arrasta
  pegando na capa (passar o dedo no trilho rola a fileira), borda esmaecida quando tem mais faders.
- 22/10/2026: vídeo do YouTube na tela (extensão + player sincronizado), iniciar com o Windows,
  ícone por canal (trocável), layouts A–E, tela 16:9, pads no início + fundo de imagem,
  layout E do desenho com painel (YouTube/Spotify/Discord/app), recarregar sozinho no tablet.
