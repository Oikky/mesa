# Pra fazer — Mesa

Ler no início de todo chat. Riscar (`[x]`) o que terminar e anotar a data.

## Esperando o usuário
- [ ] Recarregar a extensão em `edge://extensions` (↻ no card da Mesa) — **versão 1.5.0 (volume, medidor e saída por aba; fila do YouTube pelos dados) pede acesso
      a todos os sites** (precisa pra mexer no volume de qualquer aba): aceitar. Depois dar F5 nas abas
      que já estavam abertas (sem F5 a aba aparece, mas só o mute funciona; o painel avisa).
- [x] Spotify conectado (22/10/2026). Era: criar o app em developer.spotify.com (redirect `http://127.0.0.1:8080/spotify/callback`,
      Web API), Client ID já no `.env` (22/10). Falta: redirect URI no dashboard + autorizar em http://127.0.0.1:8080/spotify/login no notebook.
      Passo a passo no fim do `PROMPT.md`. (Abas já abertas no Edge em 22/10/2026.)
- [x] Discord conectado (22/10/2026). Era: criar o app em discord.com/developers (OAuth2: Client ID + Reset Secret, redirect
      `http://127.0.0.1`). Client ID e Secret já no `.env` (22/10); falta conferir o redirect e "Conectar" no painel e aprovar no
      Discord do notebook.

## Amigo (Luiz) usando a Mesa — 22/10/2026
- Repo público: https://github.com/Oikky/mesa (branch main). Ele instalou em `C:\Users\luizg\Mesa`
  com `Instalar.bat`, usa **Opera** e a **própria rede Tailscale** (`Instalar.bat --tailscale`).
- Pra mandar atualização pra ele: commit + `git push` daqui; ele toca na seta do tablet ou roda
  `Atualizar.bat`. Mudou a extensão → ele precisa recarregar em `opera://extensions`.
- Status: Discord dele conectado (faltava o Redirect `http://127.0.0.1` no app do Discord).
  Spotify dele levou 429 e o Spotify mandou esperar 1 h (versão antiga perguntava demais; já corrigido).
- [ ] Confirmar com ele depois da 1 h: fila do Spotify e do YouTube aparecendo no Opera. Se não,
      pedir o texto de http://127.0.0.1:8080/diag do PC dele.
- [ ] Se o Spotify der 403 "conta não liberada": ele está usando o Client ID de outra pessoa → criar
      o app dele (developer.spotify.com, redirect `http://127.0.0.1:8080/spotify/callback`).

## Próximo
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
- [ ] Quando o layout E estiver aprovado de vez: apagar os layouts O/A/B/C/D (CSS/JS) e o toque na
      marca que troca layout.
- [ ] Pads: hoje o layout E mostra só os 9 primeiros; decidir se tem página extra ou rolagem.
- [ ] Pad "Mime" do desenho: descobrir o que é (app/atalho) e o que o painel dele deve mostrar.

## Feito (resumo)
- 22/10/2026: fila do YouTube lida dos dados do YouTube (`extension/yt-data.js`, mundo da página):
  vem completa até em aba de fundo, com nome do canal (antes lia a tela, que monta aos poucos).
  Parte do Spotify aparece quando a conta diz que está tocando (`spnow`, vale pro Spotify Web/Opera);
  a do YouTube quando a extensão diz que tem vídeo tocando. Diagnóstico em http://127.0.0.1:8080/diag.
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
