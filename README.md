# Mesa

Controle de som do PC (Windows) pelo tablet ou celular, com cara de mesa de som: um fader por app,
por aba do navegador e por pessoa da call, microfones, saída de áudio de cada app, tela do que está
tocando (com o vídeo do YouTube ao vivo), pads estilo Stream Deck e um painel com a fila do
YouTube/Spotify e a call do Discord.

## Instalar (uma vez)

Precisa de **Windows 10/11**, **[Python 3.11+](https://www.python.org/downloads/)** (na instalação,
marcar **“Add python.exe to PATH”**) e **[Git](https://git-scm.com/download/win)**.

```powershell
git clone <endereço do repositório> Mesa
cd Mesa
.\Instalar.bat
```

O instalador faz tudo no terminal: cria o ambiente, instala as dependências, pergunta as chaves do
Spotify e do Discord (as duas são opcionais, Enter pula), pergunta se a Mesa liga junto com o Windows
e já deixa ela rodando. No fim ele mostra o endereço pra abrir no tablet.

### No tablet

**Com Tailscale (recomendado, funciona de qualquer lugar):** o instalador pergunta se é pra usar e
configura sozinho (`tailscale serve` na porta 10443, só pros aparelhos da **sua** rede Tailscale). Antes:
1. Instalar o [Tailscale](https://tailscale.com/download/windows) no PC e no tablet, logados na mesma conta.
2. Em <https://login.tailscale.com/admin/dns>, ligar **MagicDNS** e **Enable HTTPS** (uma vez).

No fim o instalador mostra o endereço (`https://seu-pc.sua-rede.ts.net:10443`): abrir no Chrome do
tablet › menu › **Instalar app**. Não precisa instalar certificado. Pra configurar depois:
`Instalar.bat --tailscale`.

**Sem Tailscale (mesmo Wi-Fi do PC):**
1. Abrir `http://IP-DO-PC:8070` e seguir a página: instala o certificado da Mesa (uma vez).
2. Abrir `https://IP-DO-PC:8443` › menu do Chrome › **Instalar app**.

Se o Windows perguntar do firewall na primeira vez, permitir em **rede privada**.

### Extensão do navegador (opcional, recomendada)

Mostra o vídeo do YouTube na tela da Mesa e deixa mudar volume e saída **de cada aba**.
`edge://extensions` (ou `chrome://extensions`) › ligar **Modo de desenvolvedor** › **Carregar sem
pacote** › escolher a pasta `extension`. Ela pede acesso a todos os sites (é o que deixa mexer no
som de qualquer aba).

## Atualizar

Quando sai versão nova, aparece uma tecla com uma seta no rodapé do tablet: é só tocar. Ou dar dois
cliques em **`Atualizar.bat`** no PC. Ele baixa a versão nova (`git pull`), atualiza o que precisa e
reinicia a Mesa; o tablet recarrega sozinho. Se a extensão mudou, ele avisa: aí é clicar em ↻ no
card da Mesa em `edge://extensions`.

As suas configurações **não são tocadas** na atualização: chaves (`.env`), pads, nomes e canais
escondidos (`config/`), certificados (`certs/`).

## Trocar as chaves do Spotify/Discord

`Instalar.bat --chaves` (Enter mantém o que já está).

- **Spotify:** <https://developer.spotify.com/dashboard> › Create app › Redirect URI
  `http://127.0.0.1:8070/spotify/callback` › marcar **Web API** › copiar o **Client ID**.
  Depois, no tablet: painel do Spotify › **Autorizar no notebook**. Tocar faixas exige Premium.
- **Discord:** <https://discord.com/developers/applications> › New Application › **OAuth2**: copiar
  **Client ID**, **Reset Secret** e copiar o **Client Secret**, e em Redirects adicionar
  `http://127.0.0.1`. Depois, no tablet: painel do Discord › **Conectar** e aprovar no Discord do PC.

## Dia a dia

| Arquivo | Pra quê |
|---|---|
| `Iniciar Mesa (sem janela).bat` | liga a Mesa escondida (igual quando o Windows inicia) |
| `Iniciar Mesa.bat` | liga com uma janela de log (pra ver erro) |
| `Parar Mesa.bat` | desliga |
| `Iniciar com o Windows.ps1` | liga/desliga o “abrir junto com o Windows” (`-Remover` pra tirar) |
| `logs/mesa.log` | o que aconteceu (mandar esse arquivo quando algo der errado) |
| <http://127.0.0.1:8070/diag> | o que a Mesa está recebendo agora (abrir no PC e mandar o texto quando algo não aparece) |

No tablet: tocar em um pad dispara, **segurar e arrastar** troca ele de lugar, **segurar e soltar**
edita. Arrastar pra baixo na coluna dos faders mostra os microfones. A tecla do olho escolhe quais
faders aparecem e dá nome a cada um.
