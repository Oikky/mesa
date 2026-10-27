---
name: Mesa
description: Controlador de hardware preto fosco no tablet, monocromático, LEDs brancos.
colors:
  chassis: "#121213"
  chassis-hi: "#19191b"
  ink: "#ededea"
  ink-2: "#a2a29f"
  ink-3: "#6b6b69"
  led: "#ffffff"
  led-off: "#2b2b2d"
  rubber-hi: "#2e2e31"
  rubber-lo: "#222225"
  cap-hi: "#f4f4f1"
  cap-lo: "#c4c4c0"
  lcd: "#08090a"
  lcd-ink: "#e6e8e4"
  lcd-dim: "#7a7d79"
typography:
  body:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.4
  silk:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: "10.5px"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "0.12em"
  readout:
    fontFamily: "Plex Mono, ui-monospace, monospace"
    fontWeight: 500
  pixel:
    fontFamily: "Silkscreen, Plex Mono, monospace"
    fontWeight: 400
rounded:
  hairline: "2px"
  sm: "3px"
  md: "7px"
  lg: "10px"
  round: "50%"
spacing:
  pad: "clamp(14px, 2vw, 22px)"
components:
  key:
    backgroundColor: "{colors.rubber-hi}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
  key-small:
    backgroundColor: "{colors.rubber-hi}"
    textColor: "{colors.ink}"
    height: "36px"
    padding: "0 12px"
  fader-cap:
    backgroundColor: "{colors.cap-hi}"
    textColor: "{colors.chassis}"
  lcd:
    backgroundColor: "{colors.lcd}"
    textColor: "{colors.lcd-ink}"
---

# Design System: Mesa

## Overview
Um aparelho, não um site. Chassi preto fosco granulado com luz suave de cima, serigrafia clara em
caixa alta, capas de fader claras, régua de tracinhos, teclas de borracha, LEDs brancos pequenos e uma
tela LCD monocromática com grade de pixels. Referências: Boss EQ-200, Novation Launch Control XL,
Elektron Analog Heat. Layout atual: **E · Painel** (faders à esquerda, tela 16:9 + transporte + pads
3×3 no meio, painel à direita, rodapé com saídas e energia).

## Colors
### Neutral
Tudo é preto/cinza/branco: `chassis` de fundo, `ink`/`ink-2`/`ink-3` para texto em três níveis,
`rubber-*` para teclas, `cap-*` para capas de fader, `lcd*` para a tela.
### Named Rules
- **LED branco só.** Estado ligado = LED branco com brilho; desligado = `led-off`. Sem cor de status.
- **Monocromático.** Exceções: fundo colorido opcional dos pads e o "tocando agora" (A e B), que
  segue a cor da capa ou da miniatura do vídeo (`--amb`) e alterna pra P&B a pedido do usuário.
- "Tocando agora" segue o Spotify de propósito: cartão do mini player no A, barra do player no B,
  play num círculo branco, linha do tempo fina e branca.

## Typography
Inter para interface, IBM Plex Mono para leituras numéricas, Silkscreen para o LCD. Todas self-hosted
em `web/fonts/`. Rótulos de serigrafia: 10.5px, 600, caixa alta, tracking .12em.

## Layout
Grade fixa de aparelho (100dvh, sem rolagem da página), `--pad` como espaçamento base, respeita
safe-area. Testar deitado 1000×600 e em pé 600×1000.

## Elevation & Depth
Profundidade física: sombras internas em LEDs e teclas, gradiente de borracha (`rubber-hi` → `rubber-lo`),
leve brilho nos LEDs acesos. Nada de cards flutuando.

## Shapes
Cantos pequenos: 7px nas teclas, 2–3px em detalhes, 10px em blocos maiores, círculo nos LEDs.

## Components
### Buttons
`.key`: tecla de borracha com ícone Lucide 20px (sprite em `web/icons/sprite.svg`), afunda no toque,
LED interno quando `aria-pressed="true"`. Ações destrutivas exigem segurar.
### LCD
Fundo `lcd`, texto `lcd-ink`, grade de pixels por cima, fonte pixel.
### Faders
Trilho escuro com régua de tracinhos, capa clara (`cap-hi` → `cap-lo`).

## Do's and Don'ts
### Do:
- Manter monocromático e com cara de hardware.
- Alvos de toque grandes; estado legível de relance.
### Don't:
- Cores de destaque, gradientes decorativos, glassmorphism, cards de site.
- `[hidden]` sem `display:none !important` (as teclas têm display próprio).
