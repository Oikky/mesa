# Qualidade

Como saber se uma mudança na Mesa está certa antes de dizer que está pronta.

## Comandos

| O quê | Comando | O que prova |
|---|---|---|
| Tudo de uma vez | `Checar.bat` | ruff + pytest + ESLint; sai com erro se algo falhar |
| Lint do Python | `.venv\Scripts\python -m ruff check .` | erros, nomes indefinidos, armadilhas (`ruff.toml`) |
| Testes | `.venv\Scripts\python -m pytest -q` | comportamento das partes que não mexem no Windows (`tests/`) |
| Lint do JS | `npx eslint web extension` | erros no app do tablet e na extensão (`eslint.config.mjs`) |
| Ferramentas de dev | `pip install -r requirements-dev.txt` e `npm install` | o `Checar.bat` faz sozinho na primeira vez |

O `Checar.bat` não liga o servidor, não toca som e não mexe no `config/` de verdade. O ESLint é
pulado se o PC não tiver Node.

Depois dos checks, o que só dá pra ver rodando: Playwright com o Edge (`--mute-audio`), deitado
1000×600 e em pé 600×1000 @2x (ver `CLAUDE.md`, "Como testar").

## Regras

- **Python (ruff):** `E4, E7, E9, F, B, ASYNC`. Fora de propósito: `E701/E702/E731` (o código usa
  `if x: return` e lambdas curtas) e `B008` (as tarefas do WS fixam `msg.get(...)` em parâmetro padrão).
  Formatação não é cobrada (reformatar tudo não ajuda).
- **JS (ESLint):** `js/recommended`, tudo como **aviso** por enquanto. Globais: navegador, service
  worker no `sw.js`, `chrome` na extensão, `YT` (API do player do YouTube).
- **Dívida medida em 27/10/2026:** 1 aviso (`no-useless-assignment` em `web/app.js`). Quando zerar,
  trocar `warn` por `error` no `eslint.config.mjs`.
- **Tamanho de arquivo:** a referência é 350 linhas; hoje `web/app.js` (~2900), `web/styles.css`
  (~1600) e `server/app.py` (~700) passam bem disso. Quebrar em partes é uma proposta separada
  (risco de regressão no tablet); não fazer escondido no meio de outra tarefa.

## Testes

- Ficam em `tests/`, um arquivo por módulo (`test_pads.py`, `test_eq.py`...). Cada teste aponta os
  caminhos de config pra `tmp_path` (`monkeypatch.setattr(modulo, "PATH", ...)`).
- Cobertos hoje: pads (lugares, troca, limpeza de imagens, nomes de tecla), chaves (`.env` por cima
  do `secrets.json`), EQ (limites, arquivo do APO, incluir uma vez só), vídeo do YouTube (aba certa,
  fila, expirar).
- Sem teste automático (precisa do Windows de verdade): mixer (pycaw), controle de mídia (winrt),
  saída por app (EarTrumpet), Discord, teclas e abrir apps.
- Bug corrigido = teste que falhava antes, quando der pra testar sem o Windows.

## Revisão depois de mudar

Mudança que não é trivial: rever o diff inteiro e quem chama o que mudou. Mudança que mexe no
`/ws`, nos endpoints HTTP, em caminhos de arquivo, em `pads.run` ou na extensão também passa pela
revisão de segurança abaixo (modo diff).

## Revisão de segurança

- Prompt: `docs/prompts/13-security-review.md` do
  [vibe-coding-toolkit](https://github.com/soumatheusgomes/vibe-coding-toolkit), revisão `790a895`.
  Rodar: *"Leia https://raw.githubusercontent.com/soumatheusgomes/vibe-coding-toolkit/790a895304e0c08b70a5b215c9d334f1c86b816c/docs/prompts/13-security-review.md
  e execute o bloco Prompt neste projeto"* (para uma mudança: dizer o intervalo de commits).
- Só leitura; o relatório vai pra `%LOCALAPPDATA%\security-reviews\` (fora do repositório, que é público).
- **27/10/2026, baseline:** feita. Há achados abertos sobre acesso pela rede; detalhes só no relatório
  privado deste notebook. Correção pendente (ver `PRA-FAZER.md`).

## Avaliar o agente (harness)

- Prompts 14 (avaliação) e 15 (melhoria, modo "adaptação nativa inspirada no Harness2") do mesmo
  toolkit/revisão. Rodar em cópia descartável, nunca nesta pasta.
- Resultado da primeira rodada: `docs/setup.md`, seção "Evidência do harness".

## Dependências

- App: `requirements.txt` (o `Atualizar.bat` instala no PC de quem usa). Dev: `requirements-dev.txt`
  e `package.json` (só checagens; a Mesa não usa Node pra rodar).
- `winrt-*` 4.x existe, mas é versão grande: atualizar só como tarefa própria, testando o "tocando
  agora" de verdade.
