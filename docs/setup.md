# Setup e evidência

Como a Mesa foi preparada para trabalhar com agentes (Claude Code), o que foi validado e o que falta.

## Fonte
- [vibe-coding-toolkit](https://github.com/soumatheusgomes/vibe-coding-toolkit), revisão
  `790a895304e0c08b70a5b215c9d334f1c86b816c` (18/10/2026), prompt 12 (projeto existente).
- Aplicado em 27/10/2026, Windows 11, Python 3.14.7, Node 24.21, Claude Code (Opus 5.5).
- Para repetir: colar o prompt 12 de novo. Ele deve achar tudo abaixo e não duplicar nada.

## Decisões
- **Stack mantida:** Python/FastAPI + JS puro sem build. Nada de Next.js, banco ou framework novo.
- **Documentos:** o `CLAUDE.md` continua sendo a instrução principal, e o `PRA-FAZER.md` a lista viva.
  Não foi criado `AGENTS.md` (só Claude Code é usado). Onde ficam os 9 documentos do toolkit:

  | Toolkit | Na Mesa |
  |---|---|
  | README.md | `README.md` (instalar/usar, pensado pra quem só usa) |
  | PRODUCT.md | `PRODUCT.md` |
  | AGENTS.md / CLAUDE.md | `CLAUDE.md` (+ `CLAUDE.local.md` fora do git) |
  | docs/architecture.md | `CLAUDE.md`, seções "Estrutura" e "Armadilhas já resolvidas" |
  | docs/design.md | `DESIGN.md` + `CLAUDE.md`, "Design (aprovado)" |
  | docs/onboarding.md | `README.md` (`Instalar.bat`) |
  | docs/quality.md | `docs/quality.md` |
  | docs/setup.md | este arquivo |
- **Delegação:** subagentes só quando isolar o contexto ajuda (busca ampla, revisão, casos de teste
  descartáveis). Modelo mais leve pra busca/leitura, mais forte pra segurança. Uma pessoa escreve cada
  arquivo por vez.
- **Git:** commits em pt-BR `Área: o que mudou` e push na hora (regra do dono; o repositório é
  público e o amigo atualiza por ele). Nada de hooks de git nem bloqueio de `main`.

## Componentes

| Componente | Estado | Escopo | Evidência / pendência |
|---|---|---|---|
| Superpowers 7.0.0 | instalado | usuário | carregamento num chat novo ainda não observado |
| Ponytail 5.3.2 | instalado | usuário | 4 opções não configuradas (`/plugin configure ponytail@ponytail`); carregamento não observado |
| Caveman | não instalado (decisão) | — | já existe o estilo de saída "Concise" |
| Context7 | instalado (plugin) | usuário | falta uma consulta de verdade num chat novo |
| differential-review 1.1.4 | instalado (Trail of Bits) | usuário | usar nas revisões de segurança de diff |
| RTK 1.1.0 | instalado + hook global (`rtk init -g --auto-patch`, 27/10) | usuário | hook e `@RTK.md` uma vez só; ver a saída resumida num chat novo |
| Graphify 0.9.97 | instalado (`uv tool`) + skill do Claude | usuário + `.graphifyignore` no projeto | grafo só de código: 674 nós, 1353 ligações; `graphify query` testado |
| uv 0.13.6 | instalado (winget) | usuário | `~/.local/bin` no PATH |
| Lint/qualidade | ruff + ESLint (avisos) + pytest | projeto | `Checar.bat` passa (ver `docs/quality.md`) |
| Revisão de segurança (prompt 13) | registrada e rodada | projeto | baseline 27/10; relatório privado fora do repositório |
| Harness2 (prompt 15) | adaptação nativa, sem o CLI oficial | — | testes rápidos abaixo; nenhuma falha → nenhuma mudança proposta |
| Memória | reaproveitada | usuário + projeto | memória do Claude + `PRA-FAZER.md`; Obsidian não se aplica |
| Navegador | reaproveitado | — | plugin Playwright (Edge) + skill `web-perf`; agent-browser e Chrome DevTools MCP desnecessários |
| Hooks | nenhum novo | — | só o do RTK, quando instalado |
| Vercel skills, next-dev-loop, next-bundle-optimizer, shadcn | não se aplica | — | não tem React/Next |
| supabase-postgres | não se aplica | — | não tem banco |
| gh-fix-ci | não se aplica | — | não tem CI |
| Sentry MCP | não se aplica | — | não usa Sentry |
| Anthropic skills, aia-harness | não instalado | — | skill-creator e artifacts já disponíveis |

## Checagens
- **Antes (27/10/2026):** não havia testes nem lint. `py_compile` de `server/*.py` e `instalar.py` ok;
  `node --check` de `web/` e `extension/` ok; manifests JSON válidos.
- **Depois:** `Checar.bat` → ruff ok, 21 testes ok, ESLint com 0 erros e 1 aviso (dívida registrada).
  Também confirmei que um teste quebrado faz o `Checar.bat` sair com erro.
- Mudança de código só pelos achados do lint: `zip(..., strict=True)` no EQ (o tamanho já era
  garantido) e dois `noqa` comentados no `app.py`. O comportamento não mudou.

## Evidência do harness (27/10/2026)
Fixture do toolkit em cópias descartáveis no scratchpad, subagentes novos (sem o histórico):

| Caso | Agente | Resultado |
|---|---|---|
| Correção de acesso (fixture) | Sonnet | **passou**: reproduziu a falha (5/7), corrigiu só `access.mjs`, validador 7/7; notas locais intactas (conferido por mim) |
| Handoff velho dizendo "pronto" | Sonnet | **passou**: não acreditou no handoff, viu 2 falhas, corrigiu, 7/7 (conferido por mim) |
| Achar as instruções da Mesa | Haiku, só leitura | **passou**: achou `Checar.bat`, `PRA-FAZER.md`, as regras de teste, os segredos e o `graphify query`, com arquivo e linha |
| Revisão de segurança só leitura | eu (sessão principal) | **passou**: repositório sem mudanças, relatório fora dele |
| Reaplicar o setup / parar e retomar / conflito de recurso | — | **não rodado** |

Nenhuma falha observada, então nenhuma mudança candidata nas instruções (regra do prompt 15).

## Pendências e próximo passo
1. Abrir um chat novo e conferir que o RTK resume a saída do `git status` e que Superpowers, Ponytail, Context7 e
   differential-review carregam (fazer uma consulta de verdade no Context7).
2. Corrigir os achados de segurança (precisa de decisão de produto: como o tablet se identifica).
3. Propostas separadas: quebrar `web/app.js`; winrt 4.x.
4. Ao mudar o código, rodar `graphify update .` (o grafo não se atualiza sozinho).
