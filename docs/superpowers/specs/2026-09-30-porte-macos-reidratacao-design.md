# Porte para macOS (Apple Silicon) + reidratação reversível

**Data:** 2026-09-30
**Base:** `tecjustica-sigilo` v1.6.1 (fork de `marcosmarf27/tecjustica-sigilo`, MIT)
**Alvo:** macOS 26 arm64, 16 GB RAM, Python 3.12, Node 24

## 1. Objetivo

Rodar o anonimizador no Mac e acrescentar **reidratação** — o ciclo
anonimizar → mandar ao modelo na nuvem → trazer a resposta de volta com os
nomes reais. Quatro usos declarados, todos ativos:

1. blindar peça antes de mandar para modelo na nuvem (Res. CNJ 615/2025);
2. publicar/compartilhar peça sem dado pessoal;
3. processo sigiloso / LGPD, com auditoria;
4. virar passo do pipeline do gabinete (`bot-convert`, `/projudi-intake`).

O porte é escrito como **ramo de plataforma**, não reescrita, para poder voltar
ao upstream: o README de lá diz "Linux/Mac: rode em modo dev. Build nativo sob
demanda", e não há nenhuma issue nem branch de plataforma aberta.

## 2. Fatos verificados antes do desenho

Não são suposições; foram medidos nesta máquina em 30/09/2026.

| Fato | Como foi conferido |
|---|---|
| **As 103 dependências resolvem em arm64 com os pins EXATOS** — `torch 2.13.0`, `onnxruntime 1.28.0`, `opencv 5.0.0.93`, `rapidocr 3.9.2`, `presidio 2.2.364`, `spacy 3.8.15`, `numpy 2.4.6` | `uv pip compile` nativo, py3.12 |
| O backend Python **não tem acoplamento a Windows**; `cliente_local.py` já traz o ramo `darwin` | grep por `win32/DPAPI/wsl/winreg/.exe` |
| O acoplamento vive em 4 arquivos de andaime + Electron, nenhum no motor | idem |
| `Mascarador` **já mantém o mapa reverso** (`_indices`) e o descarta no fim — só `resumo()` (contagens) sai | `mask_config.py:250-288`, `engine.py:652-657` |
| A numeração estável entre peças existe **só no Electron/TS** (`pseudonimos.ts`), é mão única (rótulo→rótulo), e a CLI/MCP não a têm | leitura dos dois módulos |
| `safeStorage` do Electron já usa Keychain no macOS — o cofre da GUI não precisa de porte, só os comentários | `cofre.ts:23-40` |
| Disco interno: **10 GB livres**. SSD externo: **858 GB** | `df -h` |
| O SSD é APFS e honra `chmod 0600`, **mas monta com `noowners`** — dono ignorado, qualquer usuário é tratado como proprietário | `mount`, `diskutil info`, `chmod` de teste |
| `cryptography==48.0.1` já entra no fecho transitivo, em arm64 e no `requirements-embed.txt` | `uv pip compile` |

## 3. Decisões

| Decisão | Escolha | Por quê |
|---|---|---|
| Forma do porte | fork + branch `macos`, 4 fases, mudanças upstreamáveis | o projeto já foi escrito com essa disciplina; trabalhar a favor dela |
| Repositório | `~/tecjustica-sigilo` (GitHub público, `upstream` configurado) | fora de `~/Documents` por causa do EPERM/TCC do macOS; precedente `~/gabinete-flows` |
| Peso (venv + modelos) | `$PESO/` | ~4-5 GB não cabem nos 10 GB livres do interno |
| CLI | shim em `~/.local/bin/tecjustica-sigilo` | mesma convenção do `bot-convert` |
| Melhoria da Fase 1 | reidratação | é a de maior retorno e a que a CLI/MCP nunca teve |
| Chave do mapa reverso | chave `0600` no **disco interno**, mapa cifrado no SSD, `cryptography`, falha fechada | **Keychain foi descartado**: a CLI e o MCP rodam em tmux, fora da sessão gráfica, e ali o Keychain falha (erro 36 — o mesmo que derruba o auto-login da Honda). **O SSD foi descartado para a chave** por estar montado com `noowners` (ver 5.2) |
| Persistência do mapa | padrão **só memória**; disco é opt-in (`--sessao`) com prazo | o mapa é um índice de CPF e nome: a joia da coroa |

## 4. Fase 1 — o porte

O backend Python **não muda para rodar no Mac** — é o achado da seção 2, e o
que encurta o porte. (A Fase 1b mexe nele, mas por causa da reidratação, não
da plataforma.) Mudam quatro arquivos de andaime:

| Arquivo | Hoje | Fase 1 |
|---|---|---|
| `scripts/setup-python-embed.sh` | Python embeddable Windows | não usado (é da Fase 3) |
| `scripts/fetch-ocr-models.sh` | já tenta `bin/python` | conferir o SHA-256 contra o `MANIFESTO.json` |
| `scripts/smoke-backend.sh` | exige `python-embed/python.exe` | aceitar `bin/python` |
| `python-backend/tecjustica-sigilo.cmd` | batch Windows | ganha par `.sh` |

Acrescenta-se `scripts/setup-macos.sh`: cria o venv no SSD via `uv`, aponta
`HF_HOME` para lá, baixa `pt_core_news_lg` e os modelos de OCR, instala o shim.

**Guarda de SSD ausente.** O shim confere a montagem e falha com
"monte o volume de peso", não com `ModuleNotFoundError`.

Nada de Electron nesta fase.

## 5. Fase 1b — reidratação

Quatro mudanças, todas no Python:

1. **Guardar a grafia original.** `_normalizar()` (`mask_config.py:239`) tira
   acento e caixa — o mapa de hoje devolveria `joao da silva`. `_indices` passa
   a guardar `(indice, primeira_grafia_vista)`.
2. **`Mascarador.mapa()`** → `{"[PESSOA_1]": "João da Silva"}`. `resumo()`
   fica intacto — nada quebra.

   **Duas camadas, e a distinção importa.** `anonymize()` devolve o mapa em
   `mapa_reverso` porque quem chama em processo é o servidor local, que
   precisa dele para gravar a sessão. **A CLI e o MCP nunca o imprimem** —
   nem em `-f json`. Sem `--sessao` o mapa é descartado; com `--sessao` ele
   vai cifrado para o disco e o que sai no stdout continua sendo só o texto
   mascarado. Um mapa reverso em stdout é um vazamento com outro nome.
3. **Sessão multi-peça.** Hoje o `Mascarador` nasce e morre a cada
   `anonymize()`, então a inicial e a procuração geram dois `[PESSOA_1]`
   **diferentes** e o modelo troca as pessoas com confiança. Ganha
   `sessao: str | None`; com sessão, o backend mantém o `Mascarador` num
   registro e as peças compartilham a numeração. É o `pseudonimos.ts` descido
   para o Python.
4. **Comando `reidratar`**: texto com rótulos + mapa da sessão → nomes reais.

### 5.1 A regra de ouro

**`reidratar` não é tool MCP.** Se o modelo a chamar, os nomes reais entram no
contexto dele e desfazem exatamente o que a ferramenta existe para fazer.

- MCP expõe `anonimizar_texto` (já existe) e **não** expõe reidratar;
- `reidratar` é CLI, roda local, escreve arquivo;
- se um dia virar tool, devolve **o caminho do arquivo**, nunca o conteúdo.

### 5.2 O mapa em repouso

Cifrado com `cryptography` (já é dependência), **chave e texto cifrado em
volumes diferentes**:

| | Onde | Por quê |
|---|---|---|
| **chave** | `~/.config/tecjustica-sigilo/mapa.key`, `0600`, disco interno | medido em 30/09: o SSD é APFS e aceita `chmod 0600`, **mas está montado com `noowners`** (`Owners: Disabled`) — o dono é ignorado e qualquer usuário da máquina é tratado como proprietário. `0600` ali não protege ninguém |
| **mapa cifrado** | `$PESO/mapas/` | é o volume com espaço, e separá-lo da chave é ganho: SSD levado ou roubado não carrega a chave |

**Falha fechada** em dois testes, não um: recusa gravar se não puder cifrar, e
recusa se a chave estiver num volume que ignora dono (`noowners`) ou com modo
diferente de `0600`. Nunca grava em claro. É a cultura do próprio projeto
(`cofre.ts`, `fetch-ocr-models.sh`).

Prazo de guarda: **7 dias** (o cofre da GUI usa 30, mas ele guarda documento
anonimizado; este guarda o de-para para o dado real). Ajustável por
`PRESIDIO_MAPA_PRAZO_DIAS`.

## 6. Testes

O gate do porte é a suíte que **já existe**: 13 arquivos em
`python-backend/tests`, com regressões de OCR real (entidade partida entre
linhas, dígito trocado por letra parecida). Passando no Mac, o porte está certo.

Novos, para a reidratação:

- round-trip: anonimizar → reidratar devolve o original nos trechos detectados;
- grafia com acento e caixa preservada (`João`, não `joao`);
- numeração compartilhada entre duas peças da mesma sessão;
- recusa de gravar o mapa quando a cifragem não está disponível;
- o mapa nunca aparece na saída de `anonimizar` sem `--sessao`.

Gate de acurácia **sobre o acervo do Leandro**: os 99,97% do README são do
corpus do autor. Medir é `PRESIDIO_EVAL_CORPUS=<caminho>` + `eval.run_eval`.

## 7. Limites declarados

- Reidratação restaura só o que foi **detectado**. O que escapou nunca foi
  mascarado — e o README é explícito de que a substituição é por posição, então
  um valor reconhecido em dois pontos e perdido num terceiro fica em claro.
- O gate de acurácia do upstream mede **recall, não precisão** (`docs/acuracia.md`).
- 16 GB de RAM é o mínimo medido pelo autor; na faixa em que a memória acaba o
  desempenho não degrada devagar, desaba.
- O mapa cifrado não protege contra programa malicioso rodando como o próprio
  usuário. Nenhuma cifragem atrelada à conta protege contra isso.
- **E há um caso que nenhuma defesa dentro do Fernet alcança**, medido ao
  implementar a chave: quem consegue trocar a chave pode recifrar um mapa
  **forjado** com ela. Aí o `decrypt` tem sucesso, nenhum alarme dispara, e a
  reidratação escreve os valores que a outra pessoa escolheu — sem erro e sem
  sintoma. Cifragem autenticada não ajuda, porque ela prova "isto foi escrito por
  quem tem esta chave", e nesse cenário o atacante tem esta chave.

  Daí a consequência, dita com todas as letras: o `0600` do arquivo e a recusa em
  volume `noowners` **não são defesa periférica do Fernet — são a única coisa que
  faz "esta chave" significar "eu"**. Autenticar a própria chave exigiria
  registrar uma impressão dela em outro lugar, e está fora do escopo deste plano.

## 8. Fases seguintes

| Fase | Escopo |
|---|---|
| 2 | GUI em modo dev (`npm run dev:electron`); LaunchAgent opcional para motor quente — ciente de que LaunchAgent morre no reboot com FileVault |
| 3 | `.app`/`.dmg` arm64: `python-build-standalone` via `uv` em lugar do embeddable; `mac:` no `electron-builder.yml`; CLI por symlink em vez de registro/WSL |
| 4 | tarja real em PDF (sem PyMuPDF — é AGPL e o projeto o recusa de propósito); certidão de anonimização; ganchos no `bot-convert` e no `/projudi-intake` |
