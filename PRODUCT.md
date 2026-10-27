# Product

<!-- impeccable:product-schema 1 -->

> Inferido do CLAUDE.md e do código (não houve entrevista do init). Corrigir o que estiver errado.

## Platform

web

## Users
O dono do notebook (e amigos que instalam pelo `Instalar.bat`), sentado no PC com o tablet
(Galaxy Tab S6 Lite, Chrome, PWA em tela cheia) apoiado ao lado como uma mesa de som. Usa enquanto
joga, ouve música, assiste YouTube ou está em call no Discord: olha de relance e toca rápido.

## Product Purpose
Controlar o som do notebook Windows pelo tablet sem sair do que está fazendo: volume por app e por
aba, master, saídas e microfones, saída por app/aba, "tocando agora" com o vídeo do YouTube ao vivo,
pads estilo Stream Deck e painéis por app (fila do YouTube/Spotify, call do Discord, jogos).
Sucesso = nunca precisar dar Alt+Tab pra mexer em som.

## Positioning
Um controlador físico de verdade em forma de app: mixer por app *e por aba do navegador*, ligado ao
controle de mídia do Windows, à extensão do YouTube, ao Spotify e ao RPC do Discord, rodando local.

## Operating Context
Tablet deitado (1000×600) ou em pé (600×1000), na mesa, ao lado do monitor, iluminação variada.
Toque com o dedo, de relance. Acesso por Tailscale (HTTPS). Servidor sobe sozinho no login.

## Capabilities and Constraints
- Servidor Python/FastAPI no notebook; front em HTML/CSS/JS puro sem build (`web/`).
- Atualiza o tablet sozinho quando `web/` muda.
- Ações destrutivas (reiniciar/desligar/bloquear) só com segurar.
- Nunca mutar o master nem tocar som em testes; o dono costuma estar ouvindo música.

## Brand Commitments
- Nome: Mesa (MESACONTROL na serigrafia).
- Visual aprovado: controlador de hardware preto fosco (Boss / Novation Launch Control / Elektron),
  100% monocromático, LEDs só brancos. Textos de interface em pt-BR.

## Product Principles
1. Leitura de relance: estado visível sem precisar interpretar.
2. Toque direto e seguro: alvos grandes, nada destrutivo num toque só.
3. Parece um aparelho, não um site.
4. Tudo local, nada de conta ou nuvem além do necessário (Spotify/Discord).
