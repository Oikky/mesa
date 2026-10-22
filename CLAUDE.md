# Mesa — controle de som do notebook pelo tablet

**Ao começar qualquer chat neste projeto: ler `PRA-FAZER.md`** (lista viva do que falta). Se eu
disser "continua", é dali que sai a próxima tarefa. Ao terminar algo, atualizar a lista.

## O que é
App que roda no notebook (Windows 11) e vira um app instalado em tela cheia no tablet
(Galaxy Tab S6 Lite, Chrome). Mixer por app e por aba do navegador, master, saídas, microfones, saída por app/aba, tela "tocando agora"
com o vídeo do YouTube ao vivo, pads estilo Stream Deck e um painel por app (fila do YouTube/Spotify,
call do Discord, volume/saída de jogos).

- Endereço do tablet e detalhes da rede de cada PC: `CLAUDE.local.md` (fora do git).
- Liga sozinho no login: atalho `Mesa (servidor).lnk` na pasta Inicializar (pythonw, sem janela).
  `Parar Mesa.bat` / `Iniciar Mesa (sem janela).bat` / `Iniciar Mesa.bat` (com console).
  Log: `logs/mesa.log`. Recriar/remover o atalho: `Iniciar com o Windows.ps1 [-Remover]`.
- Mudou algo em `web/`: o tablet recarrega sozinho (versão no endereço do CSS/JS + aviso pelo WS).
  Mudou algo em `server/`: reiniciar com os .bat (o tablet reconecta sozinho).

## Compartilhar / atualizar
- Repositório git próprio nesta pasta (branch `main`). Fora do git: `.env`, `config/secrets.json`,
  `config/pads.json`, `config/channels.json`, `config/pad-images/`, `certs/`, `logs/`, `.venv/`.
- Amigo instala com `Instalar.bat` (`instalar.py`: venv, deps, chaves, iniciar com o Windows) e
  atualiza com `Atualizar.bat` ou pela tecla de atualizar no tablet (`server/updates.py`).
- Dependência nova: pôr no `requirements.txt` (o Atualizar.bat instala). Commits: `Área: o que mudou`.

## Estrutura
- `server/` (Python 3.14, venv `.venv`): `app.py` (FastAPI; HTTPS 8443 = app, HTTP 8080 = página
  de setup + coisas só do notebook: `/yt` e `/ext` da extensão, login do Spotify), `audio.py`
  (pycaw, thread COM própria), `media.py` (winrt, controle de mídia do Windows), `routing.py`
  (saída por app, interface não documentada do EarTrumpet), `pads.py`, `icons.py` (ícone do .exe e
  `config/channels.json`: ícone/nome/escondido por canal), `video.py` (estado/fila do YouTube vindo da extensão), `tabs.py` (abas com som e volume por aba), `spotify.py`
  (Web API, PKCE), `discord_rpc.py` (RPC local pelo pipe), `secrets_store.py`, `certs.py`.
- `web/`: HTML/CSS/JS puro, sem build (`index.html`, `styles.css`, `app.js`, `sw.js`).
- `extension/`: extensão MV3 do Edge/Chrome (lê vídeo/tempo/fila do YouTube, recebe comandos;
  `tabvol-page.js` roda no mundo da página e aplica o volume da aba em `<video>/<audio>` e WebAudio,
  `tabvol.js` é a ponte; `background.js` manda as abas com som pro `/tabs`).
- `config/`: `pads.json`, `channels.json`, `pad-images/`, **`secrets.json` (tokens) e `.env` na raiz (client id/secret Spotify/Discord,
  nunca mostrar/compartilhar)**.

## Layouts
Tocar em MESACONTROL troca o layout (salvo no tablet em `mesa.layout3`). O atual/escolhido é o
**E · Painel** (desenho do usuário): faders à esquerda, tela 16:9 + transporte + pads 3×3 no meio,
painel à direita dividido em até 3 partes (o que toca, call do Discord, o que eu abri), rodapé com saídas e Bloquear/Reiniciar/Desligar (segurar). O, A, B, C, D
são tentativas antigas (ver PRA-FAZER: limpar).

## Design (aprovado)
Controlador de hardware preto fosco (Boss / Novation Launch Control / Elektron). LEDs só brancos,
100% monocromático (exceção: fundos coloridos opcionais dos pads), capas de fader claras, teclas de borracha, LCD com grade de pixels (capa e vídeo
em P&B; toque na tela alterna colorido). Fontes self-hosted: Inter, IBM Plex Mono, Silkscreen.
Ícones Lucide em `web/icons/sprite.svg` (adicionar símbolos novos lá). Antes de UI, seguir as skills
do CLAUDE.md global (impeccable etc.).

## Como testar
- **Playwright com o Edge** (`channel="msedge"`), nunca o Chrome. Screenshots: deitado 1000×600 @2x,
  em pé 600×1000 @2x (+ desktop). Página: `https://127.0.0.1:8443/?layout=e` (ignore_https_errors).
- **Eu costumo estar ouvindo música**: não mutar o master nem tocar som nos testes. Edge de teste com
  `--mute-audio`. Não mandar estado falso de YouTube pro `/yt` enquanto tem aba real tocando (o tablet
  de verdade pisca entre os dois vídeos).
- Nunca testar reiniciar/desligar/bloquear o PC. Pads que abrem apps fechados vão abrir de verdade.
- Ferramentas de teste ficam no scratchpad (cliente WS do estado, screenshots).

## Armadilhas já resolvidas (não repetir)
- `sys.coinit_flags = 0` antes de importar comtypes/pycaw (senão o WinRT trava: "Nada tocando").
- Edge aberto pelo Playwright não aparece no controle de mídia do Windows.
- CSS: variável que usa outra variável resolve no elemento onde é declarada.
- `RoGetActivationFactory` precisa de COM inicializado na thread.
- Chrome Android só instala PWA sem barra de URL em HTTPS confiável → Tailscale.
- Pipe do Discord: ler e escrever no mesmo handle em threads diferentes trava no Windows → uma
  thread só, com fila de escrita e PeekNamedPipe.
- YouTube no tablet: player 480×270 de verdade reduzido por CSS (cortado 18% nas bordas), só aparece
  4 s depois de tocar (some a camada de controles); legenda desligada no player.
- `[hidden]` precisa de `display:none !important` (as teclas têm display próprio).
- pythonw não tem console: stdout/stderr vão pro `logs/mesa.log`.

## Comunicação
pt-BR, direto. Decisões de produto são minhas: perguntar antes. Commits: `Área: o que mudou`.
