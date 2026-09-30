# Porte macOS arm64 + Reidratação Reversível — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rodar o `tecjustica-sigilo` no macOS Apple Silicon pela CLI e pelo MCP, e acrescentar reidratação — desfazer localmente a máscara na resposta que voltou de um modelo na nuvem.

**Architecture:** O backend Python não muda para rodar no Mac (as 103 dependências resolvem em arm64 nos pins exatos). O venv e os modelos moram no SSD externo, e `~/tecjustica-sigilo/.venv` é um **symlink** para lá — assim todo script que já procura `.venv/bin/python` funciona sem diff. A reidratação nasce no `Mascarador`, que já mantém o mapa reverso e o descarta; expõe-se esse mapa, permite-se compartilhá-lo entre peças dos mesmos autos, e grava-se cifrado com a chave no disco interno.

**Tech Stack:** Python 3.12, `uv`, Presidio 2.2.364, spaCy 3.8.15, `cryptography` (Fernet), pytest 9.1.1, bash.

---

## Convenções deste plano

Caminhos absolutos, sempre:

| Nome | Caminho |
|---|---|
| `$REPO` | `/Users/leandroleitedacruz/tecjustica-sigilo` |
| `$PESO` | `/Volumes/SSD do Leandro/tecjustica-sigilo` |
| venv | `$PESO/venv` (e `$REPO/.venv` → symlink para ele) |
| modelos HF | `$PESO/hf-cache` |
| mapas cifrados | `$PESO/mapas` |
| chave | `~/.config/tecjustica-sigilo/mapa.key` (disco **interno**, `0600`) |
| shim da CLI | `~/.local/bin/tecjustica-sigilo` |

Branch: `macos`. Um commit por tarefa.

**Português nos comentários e mensagens.** O repositório é escrito inteiro em
português, com comentários que explicam *por que*, não *o que*. Código novo
segue isso — um comentário em inglês aqui é um corpo estranho.

---

## File Structure

**Fase 1 — porte (andaime, nada no motor)**

| Arquivo | Responsabilidade |
|---|---|
| `scripts/setup-macos.sh` | **criar** — monta o venv no SSD, symlink `.venv`, baixa `pt_core_news_lg` e os modelos de OCR, instala o shim |
| `scripts/smoke-backend.sh` | **modificar** — hoje só conhece `python-embed/python.exe`; passa a aceitar o venv quando o embarcado não existe |
| `python-backend/tecjustica-sigilo.sh` | **criar** — par POSIX do `.cmd`, com `HF_HOME` apontado |

**Fase 1b — reidratação**

| Arquivo | Responsabilidade |
|---|---|
| `python-backend/mask_config.py` | **modificar** — `Mascarador` guarda a grafia original; ganha `mapa()` |
| `python-backend/engine.py` | **modificar** — `anonymize()` aceita `Mascarador` injetado e devolve `mapa_reverso` |
| `python-backend/mapa_reverso.py` | **criar** — cifragem, gravação, leitura, prazo e a substituição pura. Módulo separado porque não depende do motor: roda sem carregar modelo e é testável em milissegundos |
| `python-backend/cli.py` | **modificar** — `--autos` no `anonimizar`; subcomando `reidratar` |
| `python-backend/requirements.txt` | **modificar** — declarar `cryptography`, hoje transitivo |
| `python-backend/tests/test_mapa_reverso.py` | **criar** — contrato do mapa |
| `python-backend/tests/test_reidratacao_cli.py` | **criar** — `--autos` e `reidratar` ponta a ponta |
| `docs/macos.md` | **criar** — o que o `desenvolvimento-windows.md` é para o Windows |

**Fora de escopo, declarado:** Electron, `.dmg`, `setup-python-embed.sh`,
threading de `--autos` pelas rotas HTTP (`/anonymize`, `/v1/anonimizar`). A CLI
na Fase 1 roda sempre em processo local, porque não há aplicativo aberto — o
caminho remoto ganha `autos` na Fase 2, junto da GUI.

---

# FASE 1 — O PORTE

## Task 1: Ambiente no SSD e symlink do venv

**Files:**
- Create: `/Users/leandroleitedacruz/tecjustica-sigilo/scripts/setup-macos.sh`

- [ ] **Step 1: Escrever o script**

```bash
#!/usr/bin/env bash
#
# Monta o ambiente de desenvolvimento no macOS (Apple Silicon).
#
# Por que o peso vai para um volume externo: o venv com torch, o modelo BERT e
# os pesos de OCR passam de 4 GB, e o disco interno desta máquina tem 10 GB
# livres. O código continua no interno; só o peso sai.
#
# Por que `.venv` no repositório é um SYMLINK e não o venv de verdade: tudo
# neste projeto já procura `.venv/bin/python` — `fetch-ocr-models.sh`, e o
# `electron/main.ts` em modo dev. Apontar um link para o volume externo faz
# esses caminhos continuarem certos sem um único `if` novo.
#
# Uso: scripts/setup-macos.sh
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PESO="${TECJUSTICA_PESO:-/Volumes/SSD do Leandro/tecjustica-sigilo}"
VENV="$PESO/venv"
VOLUME="$(dirname "$PESO")"

if [[ ! -d "$VOLUME" ]]; then
  echo "O volume '$VOLUME' não está montado." >&2
  echo "Monte-o e rode de novo, ou aponte TECJUSTICA_PESO para outro lugar." >&2
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "uv não encontrado. Instale com: brew install uv" >&2
  exit 1
fi

mkdir -p "$PESO/hf-cache" "$PESO/mapas"

echo "==> venv em $VENV"
uv venv --python 3.12 "$VENV"

echo "==> dependências (runtime + desenvolvimento)"
VIRTUAL_ENV="$VENV" uv pip install \
  -r "$RAIZ/python-backend/requirements.txt" \
  -r "$RAIZ/python-backend/requirements-dev.txt"

# O symlink. `-n` para não seguir um link já existente e criar o novo lá
# dentro; `-f` para substituir. Sem `-n`, rodar duas vezes cria
# `.venv/venv -> ...` e o caminho quebra de um jeito difícil de ler.
echo "==> symlink $RAIZ/.venv -> $VENV"
ln -sfn "$VENV" "$RAIZ/.venv"

echo "==> pt_core_news_lg (pré-requisito dos DOIS modos, não só do leve)"
HF_HOME="$PESO/hf-cache" "$VENV/bin/python" -m spacy download pt_core_news_lg

echo "==> modelos de OCR (SHA-256 conferido contra o MANIFESTO.json)"
"$RAIZ/scripts/fetch-ocr-models.sh"

echo
echo "Pronto. Confira com:"
echo "  $RAIZ/.venv/bin/python -c 'import server; print(\"ok\")'"
```

- [ ] **Step 2: Tornar executável e rodar**

```bash
chmod +x /Users/leandroleitedacruz/tecjustica-sigilo/scripts/setup-macos.sh
/Users/leandroleitedacruz/tecjustica-sigilo/scripts/setup-macos.sh
```

Expected: termina com `Pronto.`. Demora vários minutos (torch são ~1 GB).
Se `uv` faltar, ele diz `brew install uv` e sai com 1 — isso é sucesso da
guarda, não falha do script.

- [ ] **Step 3: Verificar o symlink e o import do backend**

```bash
ls -l /Users/leandroleitedacruz/tecjustica-sigilo/.venv
cd /Users/leandroleitedacruz/tecjustica-sigilo/python-backend && \
  HF_HOME="/Volumes/SSD do Leandro/tecjustica-sigilo/hf-cache" \
  ../.venv/bin/python -c "import server, mcp_server; print('rotas:', len(server.app.openapi()['paths']), 'tools:', len(mcp_server.FERRAMENTAS))"
```

Expected: o `ls -l` mostra `.venv -> /Volumes/SSD do Leandro/tecjustica-sigilo/venv`,
e o import imprime `rotas: <n> tools: 4`.

- [ ] **Step 4: Verificar que nada pesado foi para o disco interno**

```bash
du -sh /Users/leandroleitedacruz/tecjustica-sigilo
du -sh "/Volumes/SSD do Leandro/tecjustica-sigilo"
df -h / | tail -1
```

Expected: o repositório fica em dezenas de MB; o SSD é que engordou. Se o
interno passou de 1 GB, o symlink não pegou — investigue antes de seguir.

- [ ] **Step 5: Commit**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo
git add scripts/setup-macos.sh
git commit -m "Monta o ambiente de macOS com o peso num volume externo

O venv com torch, o BERT e os pesos de OCR passam de 4 GB, e o disco
interno desta máquina tem 10 GB livres. O código continua no interno.

\`.venv\` no repositório é um symlink para o volume externo de propósito:
\`fetch-ocr-models.sh\` e o \`electron/main.ts\` em modo dev já procuram
\`.venv/bin/python\`, e um link faz esses caminhos continuarem certos sem
um único \`if\` novo."
```

---

## Task 2: `smoke-backend.sh` aceita o venv quando não há embarcado

O script existe para pegar a classe de defeito que nenhum teste unitário pega:
biblioteca que falta **no interpretador que vai no instalador**. No Mac ainda
não há instalador, mas o valor de importar o backend de verdade é o mesmo. Hoje
ele sai com 0 e a mensagem "esperado fora do Windows/WSL" — um `check` que
sempre passa é indistinguível de um `check` que não roda.

**Files:**
- Modify: `/Users/leandroleitedacruz/tecjustica-sigilo/scripts/smoke-backend.sh:27-35`

- [ ] **Step 1: Ver o estado atual falhando no propósito**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo && bash scripts/smoke-backend.sh
```

Expected: `python-embed/python.exe não encontrado — nada a verificar.` e exit 0.
Ou seja, não verificou nada.

- [ ] **Step 2: Trocar a resolução do interpretador**

Substituir o bloco atual (as linhas de `BACKEND=` até o `fi` do `if [[ ! -f "$PYTHON" ]]`) por:

```bash
BACKEND="$RAIZ/resources/python-backend"
PYTHON="$BACKEND/python-embed/python.exe"

# Ordem: o Python EMBARCADO primeiro, porque é ele que vai no instalador e é
# o único cujo conjunto de bibliotecas o `--no-deps` pode ter deixado
# incompleto. Onde ele não existe — macOS e Linux, onde o build nativo ainda
# não é gerado — vale o venv sobre o código de origem: não é o mesmo
# interpretador do produto, mas pega import quebrado, rota fora do ar e
# tokenizador faltando, que é a maior parte do que este script existe para
# achar.
#
# O que NÃO se faz aqui é sair com 0 sem verificar nada. Era o comportamento
# anterior fora do Windows, e um `check` que sempre passa não se distingue de
# um `check` que não roda — some no log junto dos que de fato passaram.
if [[ ! -f "$PYTHON" ]]; then
  if [[ -x "$RAIZ/.venv/bin/python" ]]; then
    BACKEND="$RAIZ/python-backend"
    PYTHON="$RAIZ/.venv/bin/python"
    echo "Sem python-embed; verificando com o venv sobre python-backend/."
  else
    echo "Nem python-embed nem .venv encontrados." >&2
    echo "Rode scripts/setup-macos.sh (macOS) ou monte o embarcado." >&2
    exit 1
  fi
fi
```

- [ ] **Step 3: Rodar e confirmar que agora VERIFICA**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo && \
  HF_HOME="/Volumes/SSD do Leandro/tecjustica-sigilo/hf-cache" bash scripts/smoke-backend.sh
```

Expected, as três linhas:
```
  ok: N rotas registradas, inclusive /ocr e a API /v1
  ok: mcp_server importa e declara as 4 ferramentas
  ok: pt_core_news_lg carrega (tokenizador dos dois modos)
```

- [ ] **Step 4: Confirmar que a guarda ainda falha quando deve**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo && \
  mv .venv .venv-guardado && bash scripts/smoke-backend.sh; echo "saída: $?"; \
  mv .venv-guardado .venv
```

Expected: `Nem python-embed nem .venv encontrados.` e `saída: 1`.

- [ ] **Step 5: Commit**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo
git add scripts/smoke-backend.sh
git commit -m "Faz o smoke verificar no Mac em vez de sair calado

Fora do Windows o script saía com 0 e 'nada a verificar'. Um check que
sempre passa não se distingue de um check que não roda: ele soma uma
linha verde ao log e some entre os que de fato verificaram algo.

Sem python-embed, agora usa o venv sobre python-backend/. Não é o
interpretador do produto, mas pega import quebrado, rota fora do ar e
tokenizador faltando — a maior parte do que este script existe para
achar. Sem nenhum dos dois, falha com 1."
```

---

## Task 3: Shim POSIX da CLI

**Files:**
- Create: `/Users/leandroleitedacruz/tecjustica-sigilo/python-backend/tecjustica-sigilo.sh`

- [ ] **Step 1: Escrever o shim**

```bash
#!/usr/bin/env bash
#
# Par POSIX do `tecjustica-sigilo.cmd`: chama o `cli.py` com o interpretador do
# projeto. O `"$@"` repassa a linha inteira, então os subcomandos funcionam sem
# que este arquivo os conheça:
#
#   tecjustica-sigilo autos.pdf              (PDF, DOCX, imagem — com OCR)
#   tecjustica-sigilo arquivo.txt -o saida.md
#   cat arquivo.txt | tecjustica-sigilo
#   tecjustica-sigilo ler autos.pdf          (extrai sem anonimizar)
#   tecjustica-sigilo reidratar resposta.txt --autos 5626981
#   tecjustica-sigilo mcp                    (servidor MCP em stdio)
#
# Este arquivo é instalado por symlink em ~/.local/bin, então ele resolve o
# próprio caminho real antes de subir dois níveis: sem isso, `dirname $0` daria
# ~/.local/bin e o cli.py não estaria lá.
set -euo pipefail

ORIGEM="${BASH_SOURCE[0]}"
while [[ -L "$ORIGEM" ]]; do
  DESTINO="$(readlink "$ORIGEM")"
  [[ "$DESTINO" == /* ]] && ORIGEM="$DESTINO" || ORIGEM="$(dirname "$ORIGEM")/$DESTINO"
done
BACKEND="$(cd "$(dirname "$ORIGEM")" && pwd)"
RAIZ="$(cd "$BACKEND/.." && pwd)"

PESO="${TECJUSTICA_PESO:-/Volumes/SSD do Leandro/tecjustica-sigilo}"
PYTHON="$RAIZ/.venv/bin/python"

# A mensagem importa: o modo de falha mais provável desta instalação é o volume
# externo desmontado, e o sintoma cru seria um ModuleNotFoundError de torch —
# que manda a pessoa depurar dependência quando o problema é um cabo.
if [[ ! -x "$PYTHON" ]]; then
  echo "O motor não está acessível em $PYTHON." >&2
  if [[ ! -d "$PESO" ]]; then
    echo "O volume '$(dirname "$PESO")' não está montado — monte-o e tente de novo." >&2
  else
    echo "Rode $RAIZ/scripts/setup-macos.sh para montar o ambiente." >&2
  fi
  exit 1
fi

export HF_HOME="${HF_HOME:-$PESO/hf-cache}"
export PRESIDIO_MAPA_DIR="${PRESIDIO_MAPA_DIR:-$PESO/mapas}"

exec "$PYTHON" "$BACKEND/cli.py" "$@"
```

- [ ] **Step 2: Instalar por symlink e testar**

```bash
chmod +x /Users/leandroleitedacruz/tecjustica-sigilo/python-backend/tecjustica-sigilo.sh
ln -sfn /Users/leandroleitedacruz/tecjustica-sigilo/python-backend/tecjustica-sigilo.sh \
        ~/.local/bin/tecjustica-sigilo
tecjustica-sigilo --help
```

Expected: o texto de ajuda com os subcomandos `anonimizar, ler, ocr, status, conectar, mcp`.

- [ ] **Step 3: Testar o caminho feliz de verdade, com texto**

```bash
printf 'O autor JOÃO DA SILVA, CPF 529.982.247-25, ajuizou a ação.\n' \
  | PRESIDIO_NLP_MODE=spacy tecjustica-sigilo
```

Expected: saída com `[PESSOA_1]` e `[CPF_1]` no lugar do nome e do CPF.
(`529.982.247-25` tem DV válido de propósito — um CPF inválido é descartado
pelo próprio motor e o teste passaria por engano.)

- [ ] **Step 4: Testar a guarda do volume**

```bash
TECJUSTICA_PESO=/Volumes/Inexistente/x \
  bash -c 'unset HF_HOME; /Users/leandroleitedacruz/tecjustica-sigilo/python-backend/tecjustica-sigilo.sh --help' \
  ; echo "saída: $?"
```

Expected: como o `.venv` existe, ele roda normalmente — a guarda do volume só
dispara quando o `.venv` some junto. Para exercer a mensagem de volume:

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo && mv .venv .venv-guardado
TECJUSTICA_PESO=/Volumes/Inexistente/x ./python-backend/tecjustica-sigilo.sh --help; echo "saída: $?"
mv .venv-guardado .venv
```

Expected: `O volume '/Volumes/Inexistente' não está montado` e `saída: 1`.

- [ ] **Step 5: Commit**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo
git add python-backend/tecjustica-sigilo.sh
git commit -m "Dá à CLI um shim POSIX, par do .cmd do Windows

Resolve o próprio caminho antes de subir dois níveis, porque é instalado
por symlink em ~/.local/bin — sem isso, dirname \$0 daria o bin e o
cli.py não estaria lá.

A guarda de volume desmontado existe pelo sintoma: sem ela, o SSD fora
do ar produz um ModuleNotFoundError de torch, que manda a pessoa depurar
dependência quando o problema é um cabo."
```

---

## Task 4: A suíte existente é o gate do porte

Nada aqui é código novo. É a verificação de que o porte está certo, e é o
momento de descobrir um acoplamento a Windows que a leitura não pegou.

**Files:** nenhum (só se um teste reprovar).

- [ ] **Step 1: Rodar a suíte inteira**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo/python-backend && \
  HF_HOME="/Volumes/SSD do Leandro/tecjustica-sigilo/hf-cache" \
  ../.venv/bin/python -m pytest tests -q 2>&1 | tail -25
```

Expected: todos passando. O `conftest.py` já força `PRESIDIO_NLP_MODE=spacy`,
então o BERT não é carregado e a suíte roda em segundos, não minutos.

- [ ] **Step 2: Se algo reprovar, classificar ANTES de corrigir**

Três causas possíveis, com tratamento diferente:

1. **Caminho de Windows literal** (ex.: `.venv/Scripts/python.exe` em
   `tests/test_cli.py` ou `electron/tokenIntegracao.test.mjs:37`) — corrigir
   acrescentando o candidato POSIX **sem remover** o do Windows. O fork
   pretende voltar ao upstream; tirar o caminho do Windows quebraria lá.
2. **Dependência de comportamento do sistema de arquivos** (sensibilidade a
   maiúsculas, separador) — corrigir no teste, com comentário dizendo por quê.
3. **Defeito real de plataforma no motor** — parar e reportar. Não remendar
   teste que está certo.

- [ ] **Step 3: Registrar o resultado como fato, não como impressão**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo/python-backend && \
  HF_HOME="/Volumes/SSD do Leandro/tecjustica-sigilo/hf-cache" \
  ../.venv/bin/python -m pytest tests -q 2>&1 | tail -3 \
  > /tmp/resultado-suite-macos.txt; cat /tmp/resultado-suite-macos.txt
```

- [ ] **Step 4: Commit (só se houve correção)**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo
git add -u
git commit -m "Aceita o layout POSIX do venv nos testes, mantendo o do Windows

O candidato de Windows fica: este fork pretende voltar ao upstream, e
lá é o único que existe."
```

Se nada reprovou, não há commit — e é o melhor resultado possível.

---

## Task 5: Registrar o servidor MCP no Claude Code

**Files:** nenhum no repositório (configuração do usuário).

- [ ] **Step 1: Registrar**

```bash
claude mcp add tecjustica-sigilo -- /Users/leandroleitedacruz/.local/bin/tecjustica-sigilo mcp
```

- [ ] **Step 2: Conferir que subiu com as 4 ferramentas**

```bash
claude mcp list 2>&1 | grep -i tecjustica
```

Expected: a linha do servidor, conectado.

- [ ] **Step 3: Exercer uma ferramenta pelo protocolo, sem depender do cliente**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo/python-backend && \
  HF_HOME="/Volumes/SSD do Leandro/tecjustica-sigilo/hf-cache" PRESIDIO_NLP_MODE=spacy \
  ../.venv/bin/python -m pytest tests/test_mcp_protocolo.py -q
```

Expected: PASS. Este teste sobe o `cli.py mcp` como subprocesso e conversa por
stdio — é a verificação de que o registro vai funcionar, independente do cliente.

- [ ] **Step 4: Nada a commitar; anotar no doc da Task 15.**

---

# FASE 1b — REIDRATAÇÃO

## Task 6: `Mascarador` — um rótulo um valor, grafia original, e `mapa()`

Três mudanças no mesmo método, porque são a mesma edição e separá-las criaria
fronteira artificial.

**A que foi descoberta ao executar o plano, e é a mais séria.**
`ROTULO_ENTIDADE` mapeia `PHONE_NUMBER_BR` **e** `PHONE_NUMBER` ao mesmo rótulo
`TELEFONE`, e `_placeholder` numera por `entity_type` — cada tipo começando do 1.
O motor inicializado suporta os dois (27 entidades; `PHONE_NUMBER` é o embutido
do Presidio, `PHONE_NUMBER_BR` é o do projeto, ambos em `PRIORIDADE_ENTIDADE`,
`engine.py:104`). Demonstrado nesta máquina:

```
(64) 99999-1111    -> [TELEFONE_1]
+55 11 98888-2222  -> [TELEFONE_1]      # valores diferentes, MESMO rótulo
```

Sem reidratação isso já é um texto ambíguo: um modelo que o leia conflui dois
telefones num só. Com reidratação fica pior — a chave `[TELEFONE_1]` do mapa
recebe um dos dois e a substituição escreve **o telefone errado** num documento
com toda a aparência de correto. É defeito herdado do upstream, não criado aqui,
e é por isso que entra nesta tarefa: `mapa()` não pode nascer sobre ele.

**As outras duas.** A chave de `_indices` é `_normalizar(texto)`, que tira acento
e caixa, então o valor guardado devolveria `joao da silva`; e não há como pedir o
mapa.

**Files:**
- Modify: `/Users/leandroleitedacruz/tecjustica-sigilo/python-backend/mask_config.py:262-288`
- Test: `/Users/leandroleitedacruz/tecjustica-sigilo/python-backend/tests/test_mapa_reverso.py`

- [ ] **Step 1: Escrever os testes que falham**

Criar `tests/test_mapa_reverso.py`:

```python
"""
O mapa reverso é o de-para entre `[PESSOA_1]` e o valor real.

Ele existe para uma coisa só: a resposta que voltou de um modelo na nuvem fala
em `[PESSOA_1]`, e quem lê precisa do nome. Três propriedades sustentam isso, e
nenhuma é óbvia.

**Um rótulo designa um valor só.** `ROTULO_ENTIDADE` manda dois tipos
(`PHONE_NUMBER_BR` e `PHONE_NUMBER`) para o mesmo `TELEFONE`, e o motor suporta
os dois. Numerar por tipo dava `[TELEFONE_1]` a dois telefones diferentes: texto
ambíguo antes de qualquer reidratação, e substituição do valor errado depois. A
numeração é por RÓTULO porque o rótulo é a identidade que o leitor e o modelo
enxergam — `entity_type` é detalhe interno de quem detectou.

**A grafia tem de ser a original.** A chave de deduplicação é
`_normalizar(texto)`, que tira acento e caixa de propósito — é o que faz
`JOÃO DA SILVA` e `joao da silva` receberem o mesmo número, e é o que o OCR
exige. Guardar a chave como valor devolveria `joao da silva` na reidratação:
não é erro que quebre nada, é erro que entrega um documento com nome errado
parecendo certo.

**As políticas `parcial` e `total` não têm mapa, e não é omissão.** Elas não
passam pelo `_placeholder`, então nada é numerado e `mapa()` devolve `{}`.
Reidratar `J**** d* S****` é impossível — a informação não existe mais no texto.
Quem pedir mapa com essas políticas tem de receber vazio, não uma aproximação.
"""

import pytest

from mask_config import Mascarador


def test_um_rotulo_designa_um_valor_so_entre_tipos_diferentes():
    """
    O defeito que esta tarefa conserta. Antes, os dois viravam `[TELEFONE_1]`.
    """
    m = Mascarador("placeholder")
    a = m.mascarar("PHONE_NUMBER_BR", "(64) 99999-1111")
    b = m.mascarar("PHONE_NUMBER", "+55 11 98888-2222")
    assert a == "[TELEFONE_1]"
    assert b == "[TELEFONE_2]", "dois telefones diferentes não podem colidir"
    assert m.mapa() == {
        "[TELEFONE_1]": "(64) 99999-1111",
        "[TELEFONE_2]": "+55 11 98888-2222",
    }


def test_mesmo_valor_em_tipos_diferentes_recebe_um_numero_so():
    """
    O outro lado da mesma moeda: se dois detectores acham o MESMO telefone e o
    classificam diferente, ele é um telefone, e merece um rótulo.
    """
    m = Mascarador("placeholder")
    assert m.mascarar("PHONE_NUMBER_BR", "(64) 99999-1111") == "[TELEFONE_1]"
    assert m.mascarar("PHONE_NUMBER", "(64) 99999-1111") == "[TELEFONE_1]"
    assert m.mapa() == {"[TELEFONE_1]": "(64) 99999-1111"}


def test_mapa_devolve_a_grafia_original_com_acento_e_caixa():
    m = Mascarador("placeholder")
    assert m.mascarar("PERSON", "JOÃO DA SILVA") == "[PESSOA_1]"
    assert m.mapa() == {"[PESSOA_1]": "JOÃO DA SILVA"}


def test_a_primeira_grafia_vista_e_a_que_fica():
    """
    O mesmo valor escrito de dois jeitos recebe um número só — e o mapa guarda a
    PRIMEIRA aparição. É arbitrário, mas tem de ser determinístico: a alternativa
    (a última) faria o mapa depender de quantas vezes o documento repetiu o nome.
    """
    m = Mascarador("placeholder")
    assert m.mascarar("PERSON", "JOÃO DA SILVA") == "[PESSOA_1]"
    assert m.mascarar("PERSON", "joao da silva") == "[PESSOA_1]"
    assert m.mapa() == {"[PESSOA_1]": "JOÃO DA SILVA"}


def test_numeracao_segue_a_ordem_de_chamada_e_separa_rotulos():
    m = Mascarador("placeholder")
    m.mascarar("PERSON", "Ana Souza")
    m.mascarar("CPF_BR", "529.982.247-25")
    m.mascarar("PERSON", "Bruno Lima")
    assert m.mapa() == {
        "[PESSOA_1]": "Ana Souza",
        "[PESSOA_2]": "Bruno Lima",
        "[CPF_1]": "529.982.247-25",
    }


def test_resumo_continua_contando_por_TIPO_e_nao_por_rotulo():
    """
    Contrato antigo que NÃO pode mudar de forma: `resumo()` vira
    `valores_distintos` e atravessa `api_v1.py:152`, `server.py:331` e a
    interface (`src/hooks/useLote.ts`). A numeração passou a ser por rótulo; a
    contagem continua por tipo.
    """
    m = Mascarador("placeholder")
    m.mascarar("PERSON", "Ana Souza")
    m.mascarar("PERSON", "ana souza")
    m.mascarar("PERSON", "Bruno Lima")
    assert m.resumo() == {"PERSON": 2}


def test_resumo_separa_os_dois_tipos_de_telefone_mesmo_com_rotulo_comum():
    m = Mascarador("placeholder")
    m.mascarar("PHONE_NUMBER_BR", "(64) 99999-1111")
    m.mascarar("PHONE_NUMBER", "+55 11 98888-2222")
    assert m.resumo() == {"PHONE_NUMBER_BR": 1, "PHONE_NUMBER": 1}


@pytest.mark.parametrize("politica", ["parcial", "total"])
def test_politicas_sem_placeholder_nao_tem_mapa(politica):
    m = Mascarador(politica)
    m.mascarar("PERSON", "João da Silva")
    assert m.mapa() == {}
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo/python-backend && \
  ../.venv/bin/python -m pytest tests/test_mapa_reverso.py -q
```

Expected: FAIL. O primeiro erro deve ser `AttributeError: 'Mascarador' object
has no attribute 'mapa'`; ao acrescentar `mapa()` sem corrigir a numeração, o
que falha passa a ser `test_um_rotulo_designa_um_valor_so_entre_tipos_diferentes`
com `[TELEFONE_1] != [TELEFONE_2]`. **Confirme que esse teste falha por essa
razão antes de corrigir a numeração** — é a prova de que o defeito é real e não
uma precaução teórica.

- [ ] **Step 3: Implementar**

Em `mask_config.py`, substituir `__init__`, `_placeholder` e `resumo()`, e
acrescentar `mapa()`:

```python
    def __init__(self, politica: str = POLITICA_PADRAO):
        if politica not in POLITICAS:
            raise ValueError(
                f"política de máscara desconhecida: {politica!r} "
                f"(use uma de {', '.join(POLITICAS)})"
            )
        self.politica = politica
        # Duas estruturas, porque são duas perguntas diferentes — e juntá-las
        # numa só foi o defeito.
        #
        # `_numeros` decide o TEXTO, e numera por RÓTULO. O rótulo é a
        # identidade que o leitor e o modelo enxergam; `entity_type` é detalhe
        # de quem detectou. `ROTULO_ENTIDADE` manda `PHONE_NUMBER_BR` e
        # `PHONE_NUMBER` ao mesmo `TELEFONE`, e o motor suporta os dois: numerar
        # por tipo dava `[TELEFONE_1]` a dois telefones diferentes — texto
        # ambíguo, e mapa reverso que substitui o valor errado.
        #
        # O valor é `(indice, primeira_grafia_vista)`, e não só o índice. A chave
        # é `_normalizar(texto)` — sem acento, minúscula — porque é o que faz
        # `JOÃO DA SILVA` e `joao da silva` receberem o mesmo número, o que o OCR
        # torna obrigatório. Mas a chave normalizada não reidrata: devolveria
        # `joao da silva`, um nome errado num documento que parece certo.
        self._numeros: dict[str, dict[str, tuple[int, str]]] = {}
        # `_tipos` conta por `entity_type`, porque é isso que `resumo()` promete
        # e `valores_distintos` atravessa a API (`api_v1.py:152`,
        # `server.py:331`) até a interface. Mudar a forma disso quebraria a tela.
        self._tipos: dict[str, set[str]] = {}

    def mascarar(self, entity_type: str, texto: str) -> str:
        if self.politica == "parcial":
            return apply_mask(entity_type, texto)
        if self.politica == "total":
            return "*" * len(texto)
        return self._placeholder(entity_type, texto)

    def _placeholder(self, entity_type: str, texto: str) -> str:
        rotulo = ROTULO_ENTIDADE.get(entity_type, entity_type)
        chave = _normalizar(texto)

        por_rotulo = self._numeros.setdefault(rotulo, {})
        if chave not in por_rotulo:
            por_rotulo[chave] = (len(por_rotulo) + 1, texto)

        self._tipos.setdefault(entity_type, set()).add(chave)

        indice, _ = por_rotulo[chave]
        return f"[{rotulo}_{indice}]"

    def resumo(self) -> dict[str, int]:
        """Quantos valores distintos foram encontrados por tipo."""
        return {tipo: len(chaves) for tipo, chaves in self._tipos.items()}

    def mapa(self) -> dict[str, str]:
        """
        O de-para `{"[PESSOA_1]": "João da Silva"}`.

        Não há colisão possível aqui, e a garantia é ESTRUTURAL, não conferida:
        `_numeros` é indexado pelo rótulo e numera dentro dele, então duas
        entradas distintas nunca produzem a mesma etiqueta. Uma verificação em
        tempo de execução seria mais fraca — pegaria o erro depois de existir,
        em vez de torná-lo impossível de escrever.

        Vazio nas políticas `parcial` e `total`: elas não passam por
        `_placeholder`, e reidratar `J**** d* S****` é impossível porque a
        informação não está mais no texto. Vazio é a resposta correta, não uma
        lacuna a preencher por aproximação.
        """
        return {
            f"[{rotulo}_{indice}]": original
            for rotulo, valores in self._numeros.items()
            for indice, original in valores.values()
        }
```

- [ ] **Step 4: Rodar a suíte INTEIRA, não só o arquivo novo**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo/python-backend && \
  HF_HOME="/Volumes/SSD do Leandro/tecjustica-sigilo/hf-cache" \
  ../.venv/bin/python -m pytest tests -q 2>&1 | tail -8
```

Expected: 179 passed + os novos, 2 skipped. A suíte inteira é obrigatória aqui,
e não só `test_mapa_reverso.py`: esta tarefa mexe na numeração dos placeholders,
que `test_mascaramento.py` trava de propósito, e em `resumo()`, que
`test_api_v1.py` e `test_mascaramento.py:230,249` conferem pela API. Se algum
deles reprovar, **não afrouxe o teste** — ou a implementação está errada, ou a
mudança de contrato é maior do que esta tarefa previu, e nos dois casos é para
reportar.

- [ ] **Step 5: Commit**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo
git add python-backend/mask_config.py python-backend/tests/test_mapa_reverso.py
git commit -m "Numera pseudônimo por rótulo, guarda a grafia e expõe mapa()"
```

A mensagem deve dizer as três coisas e, na primeira, que o defeito é herdado e
foi demonstrado: dois telefones diferentes recebiam `[TELEFONE_1]` porque
`ROTULO_ENTIDADE` manda dois tipos ao mesmo rótulo e a numeração era por tipo.

---

## Task 7: `anonymize()` aceita `Mascarador` injetado e devolve `mapa_reverso`

Hoje o `Mascarador` nasce e morre dentro de `anonymize()` (`engine.py:640`).
É por isso que a inicial e a procuração, anonimizadas em chamadas separadas,
geram dois `[PESSOA_1]` **diferentes** — e um modelo lendo as duas juntas
responde com confiança trocando as pessoas.

A injeção resolve isso sem registro global nenhum: a CLI processa os arquivos
num laço, no mesmo processo, e pode segurar um `Mascarador` ao longo dele.

**Files:**
- Modify: `/Users/leandroleitedacruz/tecjustica-sigilo/python-backend/engine.py:530-538` (assinatura), `:640` (criação), `:652-657` (retorno)
- Test: `/Users/leandroleitedacruz/tecjustica-sigilo/python-backend/tests/test_mapa_reverso.py`

- [ ] **Step 1: Acrescentar os testes ao fim de `tests/test_mapa_reverso.py`**

```python
# ---------------------------------------------------------------------------
# Numeração compartilhada entre peças dos mesmos autos
#
# Estes testes não carregam modelo: chamam `_aplicar_mascaras`, que é estático e
# recebe os spans prontos. O que se mede é o contrato do Mascarador
# compartilhado, não a qualidade da detecção.
# ---------------------------------------------------------------------------

from engine import PresidioEngine


def test_mascarador_compartilhado_da_o_mesmo_numero_em_duas_pecas():
    """
    Sem compartilhar, `[PESSOA_1]` designa Ana na inicial e Bruno na procuração.
    Juntas num contexto, o modelo troca as pessoas — e a resposta sai bem
    escrita, plausível e errada.
    """
    inicial = "Ana Souza propôs a ação."
    procuracao = "Bruno Lima outorga poderes."

    m = Mascarador("placeholder")
    saida_inicial = PresidioEngine._aplicar_mascaras(
        inicial, [(0, 9, "PERSON", 0.99)], m
    )
    saida_procuracao = PresidioEngine._aplicar_mascaras(
        procuracao, [(0, 10, "PERSON", 0.99)], m
    )

    assert saida_inicial == "[PESSOA_1] propôs a ação."
    assert saida_procuracao == "[PESSOA_2] outorga poderes."
    assert m.mapa() == {"[PESSOA_1]": "Ana Souza", "[PESSOA_2]": "Bruno Lima"}


def test_mesma_pessoa_em_duas_pecas_recebe_um_numero_so():
    m = Mascarador("placeholder")
    PresidioEngine._aplicar_mascaras("Ana Souza propôs.", [(0, 9, "PERSON", 0.99)], m)
    saida = PresidioEngine._aplicar_mascaras(
        "ANA SOUZA foi ouvida.", [(0, 9, "PERSON", 0.99)], m
    )
    assert saida == "[PESSOA_1] foi ouvida."
    assert m.mapa() == {"[PESSOA_1]": "Ana Souza"}


def test_anonymize_recusa_mascarador_de_outra_politica():
    """
    Injetar um Mascarador 'total' e pedir política 'placeholder' é ambiguidade:
    um dos dois seria silenciosamente ignorado. Recusar é a única saída que não
    mente sobre o que foi aplicado.
    """
    motor = PresidioEngine()
    with pytest.raises(ValueError, match="política"):
        motor.anonymize(
            text="x",
            entities=[],
            politica_mascara="placeholder",
            mascarador=Mascarador("total"),
        )
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo/python-backend && \
  ../.venv/bin/python -m pytest tests/test_mapa_reverso.py -q 2>&1 | tail -12
```

Expected: FAIL — `anonymize() got an unexpected keyword argument 'mascarador'`.

- [ ] **Step 3: Implementar**

3a. Na assinatura de `anonymize` (`engine.py:530`), acrescentar o parâmetro
como **último**, para não deslocar chamada posicional existente:

```python
    def anonymize(
        self,
        text: str,
        entities: list[str],
        language: str = "pt",
        progresso: "Callable[[int, int], None] | None" = None,
        politica_mascara: str = POLITICA_PADRAO,
        cancelado: "Callable[[], bool] | None" = None,
        mascarador: "Mascarador | None" = None,
    ) -> dict:
```

3b. No docstring, depois do parágrafo de `politica_mascara`, acrescentar:

```
        `mascarador`, se informado, é reaproveitado em vez de um novo — é o que
        dá a várias peças dos mesmos autos um espaço de numeração comum.
        Anonimizadas em chamadas separadas, a inicial e a procuração produzem
        dois `[PESSOA_1]` diferentes, e um modelo que leia as duas juntas
        responde trocando as pessoas: um erro que não parece erro, porque a
        resposta sai bem escrita.
```

3c. A validação vai **no começo** do método, junto da checagem de `_ready` já
existente — antes de qualquer trabalho caro:

```python
        if mascarador is not None and mascarador.politica != politica_mascara:
            raise ValueError(
                f"mascarador com política {mascarador.politica!r} não combina "
                f"com politica_mascara={politica_mascara!r} — um dos dois seria "
                f"ignorado em silêncio"
            )
```

3d. Trocar a criação (`engine.py:640`):

```python
        spans = self._fundir_spans(text, brutos)
        mascarador = mascarador if mascarador is not None else Mascarador(politica_mascara)
```

3e. Acrescentar a chave ao retorno (`engine.py:652`):

```python
        return {
            "anonymized_text": self._aplicar_mascaras(text, spans, mascarador),
            "entities_found": entidades,
            "politica_mascara": politica_mascara,
            "valores_distintos": mascarador.resumo(),
            # O de-para para reidratar. Quem chama em processo é o servidor
            # local e a CLI, que precisam dele para gravar a sessão de autos.
            #
            # A CLI e o MCP NUNCA o imprimem — nem em `-f json`. Um mapa reverso
            # em stdout é um vazamento com outro nome: desfaz, numa linha de
            # log ou num pipe, o que o resto do programa existe para fazer.
            "mapa_reverso": mascarador.mapa(),
        }
```

- [ ] **Step 4: Rodar a suíte inteira, não só o arquivo novo**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo/python-backend && \
  HF_HOME="/Volumes/SSD do Leandro/tecjustica-sigilo/hf-cache" \
  ../.venv/bin/python -m pytest tests -q 2>&1 | tail -8
```

Expected: PASS em tudo. A chave nova no dicionário de retorno é aditiva, mas
`test_api_v1.py` e `test_seguranca_api.py` inspecionam respostas de rota —
rodar tudo é o que confirma que nada lia o dicionário por igualdade estrita.

- [ ] **Step 5: Commit**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo
git add python-backend/engine.py python-backend/tests/test_mapa_reverso.py
git commit -m "Permite compartilhar o Mascarador entre peças e devolve o mapa

O Mascarador nascia e morria dentro de anonymize(), então a inicial e a
procuração dos mesmos autos produziam dois [PESSOA_1] DIFERENTES. Um
modelo que leia as duas juntas responde com confiança trocando as
pessoas — erro que não parece erro, porque a resposta sai bem escrita.

Injetar o Mascarador resolve sem registro global: a CLI percorre os
arquivos num laço, no mesmo processo, e segura um só ao longo dele.

Política divergente entre o Mascarador injetado e politica_mascara é
recusada com ValueError, e cedo: aceitar ignoraria um dos dois em
silêncio, mentindo sobre o que foi aplicado."
```

---

## Task 8: `reidratar()` — a substituição pura

Antes de qualquer cifragem ou disco: a substituição em si, que é onde mora um
defeito clássico. Trocar `[PESSOA_1]` antes de `[PESSOA_10]` corrompe o
segundo, e o resultado (`João da Silva0`) parece um erro de digitação.

**Files:**
- Create: `/Users/leandroleitedacruz/tecjustica-sigilo/python-backend/mapa_reverso.py`
- Test: `/Users/leandroleitedacruz/tecjustica-sigilo/python-backend/tests/test_mapa_reverso.py`

- [ ] **Step 1: Acrescentar os testes ao fim de `tests/test_mapa_reverso.py`**

```python
# ---------------------------------------------------------------------------
# A substituição
# ---------------------------------------------------------------------------

import mapa_reverso


def test_reidrata_substituindo_os_rotulos():
    texto = "[PESSOA_1] alega que [PESSOA_2] não pagou. CPF: [CPF_1]."
    mapa = {
        "[PESSOA_1]": "Ana Souza",
        "[PESSOA_2]": "Bruno Lima",
        "[CPF_1]": "529.982.247-25",
    }
    assert mapa_reverso.reidratar(texto, mapa) == (
        "Ana Souza alega que Bruno Lima não pagou. CPF: 529.982.247-25."
    )


def test_dois_digitos_nao_sao_corrompidos_pelo_de_um_digito():
    """
    O defeito clássico: substituir `[PESSOA_1]` por varredura ingênua atinge o
    prefixo de `[PESSOA_10]` e produz `Ana Souza0` — que não parece defeito de
    programa, parece erro de digitação de quem escreveu o documento.
    """
    mapa = {f"[PESSOA_{i}]": f"Pessoa{i}" for i in range(1, 13)}
    texto = " ".join(f"[PESSOA_{i}]" for i in (1, 10, 2, 11, 12))
    assert mapa_reverso.reidratar(texto, mapa) == (
        "Pessoa1 Pessoa10 Pessoa2 Pessoa11 Pessoa12"
    )


def test_rotulo_com_cedilha_e_reconhecido():
    """`ENDEREÇO` tem cedilha: uma classe [A-Z_] o deixaria de fora em silêncio."""
    mapa = {"[ENDEREÇO_1]": "Rua Cassiano Correia, 4"}
    assert mapa_reverso.reidratar("Reside em [ENDEREÇO_1].", mapa) == (
        "Reside em Rua Cassiano Correia, 4."
    )


def test_rotulo_fora_do_mapa_fica_como_esta():
    """
    Um rótulo sem entrada é o caso de autos trocados, ou de mapa vencido e
    apagado. Deixá-lo visível é a única saída honesta: apagar fingiria que o
    trecho não existia, e adivinhar seria pior.
    """
    saida = mapa_reverso.reidratar("[PESSOA_1] e [PESSOA_9]", {"[PESSOA_1]": "Ana"})
    assert saida == "Ana e [PESSOA_9]"


def test_texto_sem_rotulo_atravessa_intacto():
    assert mapa_reverso.reidratar("Nada a substituir.", {"[PESSOA_1]": "Ana"}) == (
        "Nada a substituir."
    )
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo/python-backend && \
  ../.venv/bin/python -m pytest tests/test_mapa_reverso.py -q 2>&1 | tail -6
```

Expected: FAIL — `ModuleNotFoundError: No module named 'mapa_reverso'`.

- [ ] **Step 3: Criar o módulo com a parte pura**

```python
"""
Mapa reverso — o de-para entre `[PESSOA_1]` e o valor real.

## Para que serve

A resposta que volta de um modelo na nuvem fala em `[PESSOA_1]`. Quem lê precisa
do nome. Este módulo guarda o de-para e o aplica de volta.

## A regra que governa o desenho

**Reidratar não é ferramenta de agente.** Chamada por um modelo, ela devolve os
nomes reais ao contexto dele — que é a nuvem — e desfaz exatamente o que este
programa existe para fazer. Por isso `mcp_server.py` não a expõe e continua
declarando quatro ferramentas. Ela é comando de linha, roda nesta máquina, e
escreve arquivo. Se algum dia virar ferramenta, devolve o CAMINHO do arquivo,
nunca o conteúdo.

## O que este módulo NÃO faz

Não detecta e não mascara. Recebe o mapa pronto de quem mascarou. É por isso que
ele não importa `engine` e roda sem carregar modelo — os testes dele levam
milissegundos.
"""

from __future__ import annotations

import functools
import re

# A classe de caracteres cobre `Ç` (U+00C7) e as vogais acentuadas porque
# `ENDEREÇO` é um dos rótulos. Com `[A-Z_]+` ele ficaria de fora em silêncio:
# o texto sairia reidratado, sem erro nenhum, e com o endereço ainda mascarado.
#
# A varredura é de UMA passagem, com consulta ao dicionário. Substituir rótulo
# por rótulo em laço é o defeito clássico: `[PESSOA_1]` é prefixo de
# `[PESSOA_10]`, e trocar o primeiro antes produz `Ana Souza0` — que não parece
# defeito de programa, parece erro de digitação do documento.
RE_ROTULO = re.compile(r"\[[A-ZÀ-Þ_]+_\d+\]")


def reidratar(texto: str, mapa: dict[str, str]) -> str:
    """
    Devolve `texto` com cada rótulo trocado pelo valor do `mapa`.

    Rótulo sem entrada fica como está. É o caso de autos trocados ou de mapa
    vencido e apagado, e deixá-lo visível é a única saída honesta: apagar
    fingiria que o trecho não existia, e adivinhar seria pior que as duas.
    """
    return RE_ROTULO.sub(lambda m: mapa.get(m.group(0), m.group(0)), texto)
```

- [ ] **Step 4: Rodar e ver passar**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo/python-backend && \
  ../.venv/bin/python -m pytest tests/test_mapa_reverso.py -q
```

Expected: PASS em todos.

- [ ] **Step 5: Commit**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo
git add python-backend/mapa_reverso.py python-backend/tests/test_mapa_reverso.py
git commit -m "Acrescenta a substituição do mapa reverso, em uma passagem

Uma passagem com consulta ao dicionário, não um laço de replace: a
segunda forma corrompe [PESSOA_10] ao trocar [PESSOA_1], produzindo 'Ana
Souza0' — que não parece defeito de programa, parece erro de digitação
do documento.

A classe de caracteres cobre Ç porque ENDEREÇO é um dos rótulos. Com
[A-Z_]+ ele ficaria de fora em silêncio: o texto sairia reidratado, sem
erro nenhum, e com o endereço ainda mascarado.

O módulo não importa engine de propósito — roda sem carregar modelo."
```

---

## Task 9: A chave, e a falha fechada

Onde a chave mora foi decidido por medição, não por gosto: o SSD é APFS e honra
`chmod 0600`, **mas monta com `noowners`** (`Owners: Disabled`). Com o dono
ignorado, qualquer usuário da máquina é tratado como proprietário, e um `0600`
ali não protege ninguém. A chave vai para o disco interno; só o texto cifrado
vai para o SSD — e separá-los é ganho: o volume que pode ser levado embora não
carrega mais a chave dele.

**Files:**
- Modify: `/Users/leandroleitedacruz/tecjustica-sigilo/python-backend/mapa_reverso.py`
- Test: `/Users/leandroleitedacruz/tecjustica-sigilo/python-backend/tests/test_mapa_reverso.py`

- [ ] **Step 1: Acrescentar os testes**

```python
# ---------------------------------------------------------------------------
# A chave e a falha fechada
#
# ## Por que quase todo teste daqui finge que o volume honra dono
#
# `_volume_honra_dono` lê o `mount` da máquina de verdade. Se os testes o
# deixassem real, eles passariam a depender de ONDE o pytest põe o `tmp_path` —
# nesta máquina cai sob `/`, que honra dono, e tudo passa. Numa máquina cujo
# temporário fique num volume `noowners`, ou num contêiner de integração
# contínua, os mesmos testes falhariam com `CifragemIndisponivel` reclamando de
# `noowners`: a mensagem certa para o ambiente e a errada para o que o teste
# queria medir, apontando o depurador para o lugar errado.
#
# Este fork pretende voltar ao upstream, onde roda na máquina de outra gente.
# Então: os testes que medem OUTRA coisa fixam a resposta em `True`, e os dois
# que medem a checagem em si a exercem de propósito.
# ---------------------------------------------------------------------------

import os
import stat

import pytest


@pytest.fixture
def volume_honra_dono(monkeypatch):
    """Isola os testes da configuração de montagem da máquina que os roda."""
    monkeypatch.setattr(mapa_reverso, "_volume_honra_dono", lambda _c: True)


def test_cria_a_chave_com_modo_0600(tmp_path, monkeypatch, volume_honra_dono):
    chave = tmp_path / "mapa.key"
    monkeypatch.setenv("PRESIDIO_MAPA_CHAVE", str(chave))
    primeira = mapa_reverso._chave()
    assert chave.exists()
    assert stat.S_IMODE(chave.stat().st_mode) == 0o600
    assert len(primeira) > 0


def test_reusa_a_chave_existente(tmp_path, monkeypatch, volume_honra_dono):
    """Recunhar a chave tornaria ilegível todo mapa já gravado."""
    chave = tmp_path / "mapa.key"
    monkeypatch.setenv("PRESIDIO_MAPA_CHAVE", str(chave))
    assert mapa_reverso._chave() == mapa_reverso._chave()


def test_recusa_chave_com_modo_frouxo(tmp_path, monkeypatch, volume_honra_dono):
    """
    Chave legível por outros não é chave. Corrigir o modo em silêncio seria
    pior: não há como saber quem já a leu, e o programa seguiria afirmando uma
    garantia que aquele arquivo não sustenta mais.
    """
    chave = tmp_path / "mapa.key"
    monkeypatch.setenv("PRESIDIO_MAPA_CHAVE", str(chave))
    mapa_reverso._chave()
    os.chmod(chave, 0o644)
    with pytest.raises(mapa_reverso.CifragemIndisponivel, match="0600"):
        mapa_reverso._chave()


def test_recusa_chave_em_volume_que_ignora_dono(tmp_path, monkeypatch):
    """Este exerce a checagem, então NÃO usa a fixture que a neutraliza."""
    chave = tmp_path / "mapa.key"
    monkeypatch.setenv("PRESIDIO_MAPA_CHAVE", str(chave))
    monkeypatch.setattr(mapa_reverso, "_volume_honra_dono", lambda _c: False)
    with pytest.raises(mapa_reverso.CifragemIndisponivel, match="noowners"):
        mapa_reverso._chave()
    assert not chave.exists(), "recusou, então não pode ter criado a chave"


def test_volume_honra_dono_reconhece_noowners():
    """
    A leitura vem do `mount`, não de um palpite pelo caminho. O volume externo
    desta máquina monta com noowners, e um `/Volumes/...` hardcoded como
    'inseguro' reprovaria um volume corretamente montado de outra pessoa.

    Recebe a tabela pronta, então não toca no sistema e vale em qualquer máquina.
    """
    montagens = {"/": "apfs, local, journaled", "/Volumes/X": "apfs, local, noowners"}
    assert mapa_reverso._analisar_montagens(montagens, "/Users/x/.config/k") is True
    assert mapa_reverso._analisar_montagens(montagens, "/Volumes/X/k") is False


def test_ponto_de_montagem_com_parentese_no_nome_e_lido_certo():
    """
    `/Volumes/Backup (2024)` é nome legítimo, e a leitura do `mount` separa o
    ponto das flags pelo ÚLTIMO ` (` justamente por isso.
    """
    montagens = {"/": "apfs, local", "/Volumes/Backup (2024)": "apfs, noowners"}
    assert mapa_reverso._analisar_montagens(montagens, "/Volumes/Backup (2024)/k") is False
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo/python-backend && \
  ../.venv/bin/python -m pytest tests/test_mapa_reverso.py -q 2>&1 | tail -6
```

Expected: FAIL — `AttributeError: module 'mapa_reverso' has no attribute '_chave'`.

- [ ] **Step 3: Implementar**

Acrescentar a `mapa_reverso.py`, depois de `reidratar`:

```python
import os
import stat
import subprocess
from pathlib import Path

CHAVE_PADRAO = Path.home() / ".config" / "tecjustica-sigilo" / "mapa.key"


class CifragemIndisponivel(RuntimeError):
    """
    Não há como cifrar com a garantia prometida — e então nada é gravado.

    É a mesma escolha do `cofre.ts` (que recusa gravar onde o sistema não
    oferece cifragem) e do `fetch-ocr-models.sh` (que recusa um download sem
    pin). Quando a garantia não pode ser dada, a operação não acontece: um mapa
    reverso em claro é um índice de CPF e nome, exatamente o artefato que este
    programa existe para não criar.
    """


def _caminho_chave() -> Path:
    return Path(os.environ.get("PRESIDIO_MAPA_CHAVE") or CHAVE_PADRAO)


def _analisar_montagens(montagens: dict[str, str], caminho: str) -> bool:
    """
    Dado `{ponto_de_montagem: flags}`, diz se `caminho` cai num volume que honra
    dono. Separado de `_volume_honra_dono` para ser testável sem tocar o
    sistema — a alternativa seria um teste que só passa nesta máquina.

    O ponto de montagem que vale é o MAIS LONGO que prefixa o caminho: `/` casa
    com tudo, e escolhê-lo diria que todo volume honra dono.
    """
    escolhido, flags = "", ""
    for ponto, valor in montagens.items():
        if (caminho == ponto or caminho.startswith(ponto.rstrip("/") + "/")) and len(ponto) > len(escolhido):
            escolhido, flags = ponto, valor
    return "noowners" not in flags


@functools.lru_cache(maxsize=1)
def _tabela_de_montagens() -> dict[str, str]:
    """
    `{ponto_de_montagem: flags}`, lido uma vez por processo.

    O cache existe porque `gravar()` chama `_chave()` e também `ler()`, que
    chama `_chave()` de novo — sem ele, cada gravação de mapa gastaria dois
    processos `/sbin/mount`, e a CLI grava uma vez por lote de peças.

    Cachear é seguro para o que se pergunta aqui: a chave mora no disco interno,
    cuja montagem não muda no meio de uma execução. O volume EXTERNO pode ser
    desmontado a qualquer momento, mas quem responde por ele é a falha de
    leitura do arquivo cifrado, não esta tabela.
    """
    try:
        saida = subprocess.run(
            ["/sbin/mount"], capture_output=True, text=True, timeout=5, check=True
        ).stdout
    except (OSError, subprocess.SubprocessError):
        # Não sabendo, devolve tabela vazia — e `_analisar_montagens` não acha
        # montagem, o que `_volume_honra_dono` trata como recusa. É a direção
        # certa do erro: o custo de um falso alarme é uma mensagem; o de um
        # falso "seguro" é um mapa desprotegido.
        return {}

    montagens: dict[str, str] = {}
    for linha in saida.splitlines():
        # `/dev/disk3s5 on / (apfs, local, journaled)`
        if " on " not in linha or "(" not in linha:
            continue
        resto = linha.split(" on ", 1)[1]
        ponto, _, flags = resto.rpartition(" (")
        montagens[ponto.strip()] = flags.rstrip(")")
    return montagens


def _volume_honra_dono(caminho: Path) -> bool:
    """
    `noowners` faz o sistema ignorar o dono: todo arquivo do volume responde
    como se fosse do usuário atual, e o `0600` deixa de proteger contra outro
    usuário da máquina.

    A informação vem do `mount`, não de um palpite pelo prefixo do caminho. O
    SSD desta máquina monta com noowners, mas tratar `/Volumes/` como inseguro
    por definição reprovaria o volume corretamente montado de outra pessoa —
    seria uma regra que acerta aqui por coincidência.
    """
    montagens = _tabela_de_montagens()
    if not montagens:
        return False
    return _analisar_montagens(montagens, str(caminho.resolve()))


def _chave() -> bytes:
    """
    Devolve a chave Fernet, criando-a na primeira vez.

    Nunca recunha uma chave existente: isso tornaria ilegível todo mapa já
    gravado, e o sintoma seria "reidratar parou de funcionar", que não aponta
    para aqui.
    """
    from cryptography.fernet import Fernet

    caminho = _caminho_chave()

    # `resolve()` não exige que o arquivo exista, então a checagem vale antes da
    # primeira criação também — e é aí que ela mais importa.
    if not _volume_honra_dono(caminho):
        raise CifragemIndisponivel(
            f"{caminho} está num volume montado com noowners — o dono é "
            f"ignorado e o modo 0600 não protege contra outro usuário. "
            f"Aponte PRESIDIO_MAPA_CHAVE para o disco interno."
        )

    if caminho.exists():
        if stat.S_IMODE(caminho.stat().st_mode) != 0o600:
            raise CifragemIndisponivel(
                f"{caminho} não está em 0600. Não corrijo em silêncio: não há "
                f"como saber quem já a leu, e seguir usando afirmaria uma "
                f"garantia que este arquivo não sustenta mais. "
                f"Confira quem teve acesso, apague-a (os mapas gravados ficam "
                f"ilegíveis) e deixe-a ser recriada."
            )
        return caminho.read_bytes()

    caminho.parent.mkdir(parents=True, exist_ok=True)
    nova = Fernet.generate_key()
    # Cria já fechado: gravar e depois chmod deixa uma janela em que o arquivo
    # existe legível. `0o600` no `os.open`, e não `write_bytes` seguido de
    # `chmod`.
    descritor = os.open(caminho, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descritor, "wb") as arquivo:
        arquivo.write(nova)
    return nova
```

- [ ] **Step 4: Rodar e ver passar**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo/python-backend && \
  ../.venv/bin/python -m pytest tests/test_mapa_reverso.py -q
```

Expected: PASS em todos.

- [ ] **Step 5: Commit**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo
git add python-backend/mapa_reverso.py python-backend/tests/test_mapa_reverso.py
git commit -m "Põe a chave do mapa no disco interno, com falha fechada dupla

Medido: o SSD é APFS e honra chmod 0600, mas monta com noowners (Owners:
Disabled). Com o dono ignorado, qualquer usuário da máquina responde
como proprietário e o 0600 ali não protege ninguém. A chave fica no
disco interno; só o texto cifrado vai para o volume externo — e separá-
los é ganho, porque o volume que pode ser levado não carrega a chave.

Recusa em dois casos, ambos sem gravar: volume com noowners, e chave com
modo diferente de 0600. O modo frouxo não é corrigido em silêncio — não
há como saber quem já leu o arquivo, e consertar o bit faria o programa
seguir afirmando uma garantia que aquela chave não sustenta mais.

A leitura do noowners vem do mount, não do prefixo do caminho: tratar
/Volumes/ como inseguro por definição acertaria aqui por coincidência e
reprovaria o volume bem montado de outra pessoa."
```

---

## Task 10: Gravar, ler e esquecer o mapa

**Files:**
- Modify: `/Users/leandroleitedacruz/tecjustica-sigilo/python-backend/mapa_reverso.py`
- Test: `/Users/leandroleitedacruz/tecjustica-sigilo/python-backend/tests/test_mapa_reverso.py`

- [ ] **Step 1: Acrescentar os testes**

```python
# ---------------------------------------------------------------------------
# Gravação, leitura e prazo
# ---------------------------------------------------------------------------


from pathlib import Path


@pytest.fixture
def cofre(tmp_path, monkeypatch):
    """Chave e mapas em tmp_path — nunca no cofre real do usuário."""
    monkeypatch.setenv("PRESIDIO_MAPA_CHAVE", str(tmp_path / "mapa.key"))
    monkeypatch.setenv("PRESIDIO_MAPA_DIR", str(tmp_path / "mapas"))
    return tmp_path


def test_grava_e_le_o_mesmo_mapa(cofre):
    mapa = {"[PESSOA_1]": "Ana Souza", "[CPF_1]": "529.982.247-25"}
    mapa_reverso.gravar("5626981", mapa)
    assert mapa_reverso.ler("5626981") == mapa


def test_o_arquivo_gravado_nao_contem_o_valor_em_claro(cofre):
    """O teste que importa: se este passar por acidente, a cifragem não rodou."""
    mapa_reverso.gravar("5626981", {"[PESSOA_1]": "Ana Souza"})
    bruto = (cofre / "mapas" / "5626981.mapa").read_bytes()
    assert b"Ana Souza" not in bruto
    assert b"PESSOA_1" not in bruto


def test_gravar_de_novo_funde_em_vez_de_substituir(cofre):
    """
    Cada peça dos autos chega numa execução. Substituir perderia o mapa da peça
    anterior e a reidratação sairia parcial — pior que falhar, porque parece
    completa.
    """
    mapa_reverso.gravar("5626981", {"[PESSOA_1]": "Ana Souza"})
    mapa_reverso.gravar("5626981", {"[PESSOA_2]": "Bruno Lima"})
    assert mapa_reverso.ler("5626981") == {
        "[PESSOA_1]": "Ana Souza",
        "[PESSOA_2]": "Bruno Lima",
    }


def test_gravar_nao_sobrescreve_mapa_que_nao_decifra(cofre):
    """
    Gravar em cima apagaria o de-para de tudo que já foi anonimizado nestes
    autos, e a causa da ilegibilidade pode ser benigna e reversível (a chave
    errada na variável de ambiente, o arquivo vindo de outra máquina).
    """
    from cryptography.fernet import Fernet

    mapa_reverso.gravar("5626981", {"[PESSOA_1]": "Ana Souza"})
    antes = (cofre / "mapas" / "5626981.mapa").read_bytes()
    Path(os.environ["PRESIDIO_MAPA_CHAVE"]).write_bytes(Fernet.generate_key())

    with pytest.raises(mapa_reverso.MapaIlegivel):
        mapa_reverso.gravar("5626981", {"[PESSOA_2]": "Bruno Lima"})
    assert (cofre / "mapas" / "5626981.mapa").read_bytes() == antes, (
        "recusou, então o arquivo anterior tem de estar byte a byte intacto"
    )


def test_ler_autos_inexistente_devolve_vazio(cofre):
    assert mapa_reverso.ler("nao-existe") == {}


def test_mapa_que_nao_decifra_levanta_alarme_em_vez_de_devolver_vazio(cofre):
    """
    A distinção que esta exceção preserva. Foi medida na Task 9: `Fernet` aceita
    qualquer chave bem-formada de 44 bytes e só falha no `decrypt`, com
    `InvalidToken` sem argumento nenhum — o mesmo evento de um mapa adulterado.

    Devolver `{}` aqui faria a reidratação entregar o texto com os rótulos em
    claro e sem mensagem, e quem lê concluiria "o prazo venceu". São coisas
    muito diferentes e merecem reações muito diferentes.
    """
    from cryptography.fernet import Fernet

    mapa_reverso.gravar("5626981", {"[PESSOA_1]": "Ana Souza"})

    # Troca a chave por OUTRA bem-formada — não corrompe, substitui.
    Path(os.environ["PRESIDIO_MAPA_CHAVE"]).write_bytes(Fernet.generate_key())

    with pytest.raises(mapa_reverso.MapaIlegivel, match="5626981"):
        mapa_reverso.ler("5626981")


def test_mapa_ilegivel_nao_e_apagado(cofre):
    """
    Apagar seria irreversível e a causa pode ser benigna (a chave recriada de
    propósito). Quem decide é a pessoa, com o arquivo ainda na mão.
    """
    from cryptography.fernet import Fernet

    mapa_reverso.gravar("5626981", {"[PESSOA_1]": "Ana Souza"})
    alvo = cofre / "mapas" / "5626981.mapa"
    Path(os.environ["PRESIDIO_MAPA_CHAVE"]).write_bytes(Fernet.generate_key())

    with pytest.raises(mapa_reverso.MapaIlegivel):
        mapa_reverso.ler("5626981")
    assert alvo.exists(), "mapa ilegível não pode ser apagado pela leitura"


def test_mapa_vencido_e_apagado_e_nao_lido(cofre):
    mapa_reverso.gravar("5626981", {"[PESSOA_1]": "Ana Souza"})
    alvo = cofre / "mapas" / "5626981.mapa"
    antigo = alvo.stat().st_mtime - (8 * 86400)
    os.utime(alvo, (antigo, antigo))
    assert mapa_reverso.ler("5626981") == {}
    assert not alvo.exists(), "vencido tem de ser apagado, não só ignorado"


def test_prazo_configuravel_por_ambiente(cofre, monkeypatch):
    monkeypatch.setenv("PRESIDIO_MAPA_PRAZO_DIAS", "30")
    mapa_reverso.gravar("5626981", {"[PESSOA_1]": "Ana Souza"})
    alvo = cofre / "mapas" / "5626981.mapa"
    antigo = alvo.stat().st_mtime - (8 * 86400)
    os.utime(alvo, (antigo, antigo))
    assert mapa_reverso.ler("5626981") == {"[PESSOA_1]": "Ana Souza"}


def test_esquecer_apaga(cofre):
    mapa_reverso.gravar("5626981", {"[PESSOA_1]": "Ana Souza"})
    assert mapa_reverso.esquecer("5626981") is True
    assert mapa_reverso.ler("5626981") == {}
    assert mapa_reverso.esquecer("5626981") is False


def test_etiqueta_conflitante_e_recusada_em_vez_de_sobrescrita(cofre):
    """
    O defeito que esta recusa existe para impedir, demonstrado antes de existir:

        segunda:  anonimizar inicial.pdf    --autos X  ->  [PESSOA_1] = Ana
        quarta:   anonimizar procuracao.pdf --autos X  ->  [PESSOA_1] = Bruno
        fusão sem recusa: {'[PESSOA_1]': 'Bruno Lima'}   <- a Ana desapareceu

    Cada invocação da CLI é um processo novo, com Mascarador novo, numerando do
    1. Sem recusa, reidratar a resposta sobre a peça de segunda escreveria
    "Bruno Lima" onde estava a Ana — com confiança, num texto bem formado.
    """
    mapa_reverso.gravar("5626981", {"[PESSOA_1]": "Ana Souza"})
    with pytest.raises(mapa_reverso.EtiquetaConflitante, match="PESSOA_1"):
        mapa_reverso.gravar("5626981", {"[PESSOA_1]": "Bruno Lima"})
    assert mapa_reverso.ler("5626981") == {"[PESSOA_1]": "Ana Souza"}, (
        "recusou, então o mapa anterior tem de estar intacto"
    )


def test_gravar_a_mesma_etiqueta_com_o_mesmo_valor_nao_e_conflito(cofre):
    """Reprocessar a mesma peça é idempotente, não erro."""
    mapa_reverso.gravar("5626981", {"[PESSOA_1]": "Ana Souza"})
    mapa_reverso.gravar("5626981", {"[PESSOA_1]": "Ana Souza", "[CPF_1]": "529.982.247-25"})
    assert mapa_reverso.ler("5626981") == {
        "[PESSOA_1]": "Ana Souza",
        "[CPF_1]": "529.982.247-25",
    }


@pytest.mark.parametrize("ruim", ["../fuga", "a/b", "", "."])
def test_nome_de_autos_que_escaparia_do_diretorio_e_recusado(cofre, ruim):
    """
    O nome dos autos vem da linha de comando e vira nome de arquivo. Sem
    validação, `--autos ../../algo` grava fora do diretório de mapas.
    """
    with pytest.raises(ValueError, match="autos"):
        mapa_reverso.gravar(ruim, {"[PESSOA_1]": "Ana"})
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo/python-backend && \
  ../.venv/bin/python -m pytest tests/test_mapa_reverso.py -q 2>&1 | tail -6
```

Expected: FAIL — `module 'mapa_reverso' has no attribute 'gravar'`.

- [ ] **Step 3: Implementar**

Acrescentar ao fim de `mapa_reverso.py`:

```python
import json
import re as _re
import time

DIR_PADRAO = Path("/Volumes/SSD do Leandro/tecjustica-sigilo/mapas")
PRAZO_DIAS_PADRAO = 7

# O nome dos autos vem da linha de comando e vira nome de arquivo. Sem esta
# régua, `--autos ../../algo` grava fora do diretório de mapas.
RE_AUTOS = _re.compile(r"^[A-Za-z0-9._-]{1,120}$")


def _dir_mapas() -> Path:
    return Path(os.environ.get("PRESIDIO_MAPA_DIR") or DIR_PADRAO)


def _prazo_dias() -> int:
    bruto = os.environ.get("PRESIDIO_MAPA_PRAZO_DIAS")
    if not bruto:
        return PRAZO_DIAS_PADRAO
    try:
        return max(1, int(bruto))
    except ValueError:
        return PRAZO_DIAS_PADRAO


def _caminho(autos: str) -> Path:
    if not RE_AUTOS.match(autos) or autos in {".", ".."}:
        raise ValueError(
            f"nome de autos inválido: {autos!r} — use letras, números, ponto, "
            f"hífen e sublinhado (é nome de arquivo)"
        )
    return _dir_mapas() / f"{autos}.mapa"


class EtiquetaConflitante(RuntimeError):
    """
    A mesma etiqueta designa valores diferentes no mapa gravado e no que chega.

    É o sintoma de numeração que recomeçou: `Mascarador` novo numera do 1, então
    uma segunda invocação da CLI sobre os mesmos autos produz `[PESSOA_1]` para
    outra pessoa. Fundir sobrescreveria, e a reidratação da primeira peça
    escreveria o nome de quem apareceu na segunda — num texto bem formado.

    A cura é semear o `Mascarador` com o mapa gravado (ver `Mascarador.semear`),
    e esta exceção é a rede embaixo dela: se a semeadura falhar ou for esquecida,
    a gravação para em vez de corromper.
    """


def gravar(autos: str, mapa: dict[str, str]) -> Path:
    """
    Funde `mapa` no que já estava gravado para estes autos e grava cifrado.

    Funde, e não substitui, porque cada peça chega numa execução: substituir
    perderia o mapa da peça anterior e a reidratação sairia PARCIAL — pior que
    falhar, porque um documento meio reidratado tem toda a aparência de
    completo.

    **Recusa etiqueta conflitante**, e isso é o oposto de fundir cegamente. Se
    `[PESSOA_1]` já vale "Ana Souza" no disco e chega valendo "Bruno Lima", não
    há fusão possível que preserve as duas — e escolher uma em silêncio produz
    reidratação errada na outra. Levanta `EtiquetaConflitante`.

    **Propaga `MapaIlegivel`** — vindo do `ler()` desta mesma função —, e isso é
    de propósito: um mapa que existe e não decifra não pode ser sobrescrito por
    um novo. Gravar em cima apagaria o de-para de tudo que já foi anonimizado
    nestes autos, e o que motiva a ilegibilidade pode ser benigno e reversível
    (a chave errada em `PRESIDIO_MAPA_CHAVE`, o volume de outra máquina). Quem
    decide apagar é a pessoa, com o arquivo na mão.

    E `CifragemIndisponivel`, de `_chave()`, pela mesma razão do módulo inteiro:
    sem poder cifrar, não grava.
    """
    from cryptography.fernet import Fernet

    caminho = _caminho(autos)
    chave = _chave()  # antes de criar diretório: falhando, nada toca o disco

    gravado = ler(autos)
    for etiqueta, valor in mapa.items():
        anterior = gravado.get(etiqueta)
        if anterior is not None and anterior != valor:
            raise EtiquetaConflitante(
                f"{etiqueta} vale {anterior!r} no mapa dos autos {autos!r} e "
                f"chegou valendo {valor!r}. A numeração recomeçou — semeie o "
                f"Mascarador com o mapa gravado antes de anonimizar (ver "
                f"Mascarador.semear). Nada foi gravado."
            )

    juntos = {**gravado, **mapa}
    caminho.parent.mkdir(parents=True, exist_ok=True)
    corpo = Fernet(chave).encrypt(json.dumps(juntos, ensure_ascii=False).encode())

    # Grava em temporário e renomeia: a troca é atômica no mesmo volume, então
    # uma interrupção no meio deixa o mapa anterior intacto em vez de um
    # arquivo truncado que não decifra.
    temporario = caminho.with_suffix(".mapa.parcial")
    descritor = os.open(temporario, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descritor, "wb") as arquivo:
        arquivo.write(corpo)
    os.replace(temporario, caminho)
    return caminho


class MapaIlegivel(RuntimeError):
    """
    O arquivo do mapa existe, está no prazo, e não decifra.

    **Isto é alarme, não ausência**, e a distinção foi o achado que reescreveu
    esta função. Arquivo ausente é benigno e esperado — é o expurgo funcionando.
    Arquivo presente e ilegível significa que a chave não é mais a que cifrou
    aquele mapa: ela foi recriada, ou substituída.

    Colapsar os dois em `{}` seria o defeito pior: a reidratação devolveria o
    texto com `[PESSOA_1]` em claro e nenhuma mensagem, e quem lê concluiria
    "venceu, normal" — quando o que houve foi a chave ser trocada. É a mesma
    lição que o `CLAUDE.md` deste repositório registra sobre o contador de OCR:
    "na dúvida não afirme" é boa regra para afirmar fato e péssima para calar
    alarme.
    """


def ler(autos: str) -> dict[str, str]:
    """
    Devolve o mapa destes autos, ou `{}` se não existe ou venceu.

    Vencido é **apagado**, não apenas ignorado: prazo de guarda que só esconde
    não é prazo de guarda — o índice de CPF e nome continuaria no disco.

    Levanta `MapaIlegivel` quando o arquivo existe, está no prazo e não decifra.
    O porquê de não devolver `{}` está na exceção.
    """
    from cryptography.fernet import Fernet, InvalidToken

    caminho = _caminho(autos)
    if not caminho.exists():
        return {}

    if time.time() - caminho.stat().st_mtime > _prazo_dias() * 86400:
        caminho.unlink(missing_ok=True)
        return {}

    try:
        corpo = Fernet(_chave()).decrypt(caminho.read_bytes())
    except InvalidToken as erro:
        raise MapaIlegivel(
            f"o mapa dos autos {autos!r} existe em {caminho} e não decifra com "
            f"a chave atual. A chave foi recriada (o que torna ilegível todo "
            f"mapa gravado antes dela) ou substituída. O arquivo NÃO foi "
            f"apagado — apagá-lo é irreversível, e a decisão é sua."
        ) from erro
    return json.loads(corpo)


def esquecer(autos: str) -> bool:
    """Apaga o mapa destes autos. `False` se não havia nada."""
    caminho = _caminho(autos)
    if not caminho.exists():
        return False
    caminho.unlink()
    return True
```

- [ ] **Step 4: Rodar e ver passar**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo/python-backend && \
  ../.venv/bin/python -m pytest tests/test_mapa_reverso.py -q
```

Expected: PASS em todos.

- [ ] **Step 5: Commit**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo
git add python-backend/mapa_reverso.py python-backend/tests/test_mapa_reverso.py
git commit -m "Grava o mapa cifrado, com fusão, prazo de 7 dias e troca atômica

Funde em vez de substituir porque cada peça dos autos chega numa
execução: substituir perderia o mapa da peça anterior e a reidratação
sairia parcial — pior que falhar, porque um documento meio reidratado
tem toda a aparência de completo.

Vencido é APAGADO, não ignorado: prazo de guarda que só esconde não é
prazo de guarda, o índice de CPF e nome continuaria no disco. Sete dias,
não os 30 do cofre da interface — o cofre guarda documento anonimizado,
este guarda o de-para para o dado real.

Grava em temporário e renomeia: interrupção no meio deixa o mapa
anterior intacto em vez de um arquivo truncado que não decifra.

O nome dos autos passa por régua de nome de arquivo — sem ela,
--autos ../../algo grava fora do diretório."
```

---

## Task 10b: `Mascarador.semear()` — a numeração CONTINUA entre invocações

A Task 10 pôs uma rede (`EtiquetaConflitante`). Esta é a cura.

**O defeito, demonstrado antes de a tarefa existir.** Cada invocação da CLI é um
processo novo, com `Mascarador` novo, numerando do 1:

```
segunda:  tecjustica-sigilo anonimizar inicial.pdf    --autos 5626981  ->  [PESSOA_1] = Ana
quarta:   tecjustica-sigilo anonimizar procuracao.pdf --autos 5626981  ->  [PESSOA_1] = Bruno
```

O `--autos` desenhado até aqui compartilha numeração **dentro de** uma invocação
e não **entre** invocações — mas acrescentar peça dias depois é o uso normal de
um processo judicial, e a promessa da opção é justamente a de que `[PESSOA_1]`
seja a mesma pessoa em todas as peças.

A cura é semear: antes de anonimizar, o `Mascarador` recebe o mapa já gravado e
continua de onde a execução anterior parou.

**Files:**
- Modify: `/Users/leandroleitedacruz/tecjustica-sigilo/python-backend/mask_config.py`
- Modify: `/Users/leandroleitedacruz/tecjustica-sigilo/python-backend/mapa_reverso.py`
- Test: `/Users/leandroleitedacruz/tecjustica-sigilo/python-backend/tests/test_mapa_reverso.py`

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar ao fim de `tests/test_mapa_reverso.py`:

```python
# ---------------------------------------------------------------------------
# Semeadura: a numeração continua entre invocações
# ---------------------------------------------------------------------------


def test_semear_continua_a_numeracao_em_vez_de_recomecar():
    """
    O caso que motiva o método. A segunda invocação sobre os mesmos autos tem de
    dar `[PESSOA_2]` a quem chegou depois, não `[PESSOA_1]` de novo.
    """
    primeira = Mascarador("placeholder")
    assert primeira.mascarar("PERSON", "Ana Souza") == "[PESSOA_1]"

    segunda = Mascarador("placeholder")
    segunda.semear(primeira.mapa())
    assert segunda.mascarar("PERSON", "Bruno Lima") == "[PESSOA_2]"
    assert segunda.mapa() == {"[PESSOA_1]": "Ana Souza", "[PESSOA_2]": "Bruno Lima"}


def test_semear_reconhece_quem_ja_tinha_numero():
    """
    A mesma pessoa numa peça nova recebe o número que já era dela — é isso que
    faz o modelo entender que a Ana da inicial é a Ana da procuração.
    """
    primeira = Mascarador("placeholder")
    primeira.mascarar("PERSON", "Ana Souza")

    segunda = Mascarador("placeholder")
    segunda.semear(primeira.mapa())
    assert segunda.mascarar("PERSON", "ANA SOUZA") == "[PESSOA_1]"


def test_semear_com_buraco_na_sequencia_nao_reusa_numero():
    """
    `remascarar()` renumera do zero ao liberar um falso positivo, e um mapa
    gravado antes disso pode chegar com buraco. Numerar por `len()+1` reusaria um
    número já tomado e faria duas pessoas virarem a mesma. O próximo é
    `max(...)+1`.
    """
    m = Mascarador("placeholder")
    m.semear({"[PESSOA_1]": "Ana Souza", "[PESSOA_3]": "Carla Dias"})
    assert m.mascarar("PERSON", "Bruno Lima") == "[PESSOA_4]"


def test_semear_separa_rotulos():
    m = Mascarador("placeholder")
    m.semear({"[PESSOA_1]": "Ana Souza", "[CPF_1]": "529.982.247-25"})
    assert m.mascarar("PERSON", "Bruno Lima") == "[PESSOA_2]"
    assert m.mascarar("CPF_BR", "111.444.777-35") == "[CPF_2]"


def test_semear_nao_conta_para_o_resumo():
    """
    `resumo()` vira `valores_distintos` e diz o que ESTA execução encontrou.
    Semear não é encontrar: contar o que veio do disco inflaria o número que a
    interface mostra sobre o documento que acabou de ser lido.
    """
    m = Mascarador("placeholder")
    m.semear({"[PESSOA_1]": "Ana Souza"})
    assert m.resumo() == {}
    m.mascarar("PERSON", "Bruno Lima")
    assert m.resumo() == {"PERSON": 1}


def test_a_forma_da_etiqueta_nao_aceita_simbolo():
    """
    `×` (U+00D7) fica no meio do bloco Latin-1 maiúsculo e não é letra. A irmã em
    TypeScript o exclui por usar `\\p{Lu}`; o intervalo partido `À-Ö`/`Ø-Þ` faz o
    Python concordar. Nenhum rótulo real usaria símbolo — o teste existe para as
    duas camadas não divergirem em rigor sem ninguém notar.
    """
    from mask_config import RE_ETIQUETA

    assert RE_ETIQUETA.fullmatch("[ENDEREÇO_1]") is not None
    assert RE_ETIQUETA.fullmatch("[PESSOA_12]") is not None
    assert RE_ETIQUETA.fullmatch("[ORGANIZATION_1]") is not None
    assert RE_ETIQUETA.fullmatch("[×_1]") is None
    assert RE_ETIQUETA.fullmatch("[pessoa_1]") is None
    assert RE_ETIQUETA.fullmatch("[PESSOA_]") is None
    assert RE_ETIQUETA.fullmatch("[PESSOA_1") is None


def test_semear_recusa_etiqueta_fora_de_forma():
    m = Mascarador("placeholder")
    with pytest.raises(ValueError, match="etiqueta"):
        m.semear({"PESSOA_1": "Ana Souza"})


def test_semear_recusa_dois_numeros_para_o_mesmo_valor():
    """
    Mapa em que a mesma pessoa aparece com dois números é mapa corrompido, e
    seguir com ele escolheria um dos dois em silêncio.
    """
    m = Mascarador("placeholder")
    with pytest.raises(ValueError, match="dois números"):
        m.semear({"[PESSOA_1]": "Ana Souza", "[PESSOA_2]": "ana souza"})


def test_semear_em_politica_sem_placeholder_e_recusado():
    """Semear um Mascarador que não numera é pedido sem sentido — e silencioso."""
    for politica in ("parcial", "total"):
        m = Mascarador(politica)
        with pytest.raises(ValueError, match="placeholder"):
            m.semear({"[PESSOA_1]": "Ana Souza"})
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo/python-backend && \
  ../.venv/bin/python -m pytest tests/test_mapa_reverso.py -q 2>&1 | tail -8
```

Expected: FAIL — `AttributeError: 'Mascarador' object has no attribute 'semear'`.

- [ ] **Step 3: Implementar**

**3a.** A definição da etiqueta passa a morar em `mask_config.py`, que é quem a
CRIA, e o `mapa_reverso.py` a importa em vez de repetir.

Hoje há duas cópias do mesmo padrão: `RE_ROTULO` em `mapa_reverso.py` (Task 8) e
o f-string `f"[{rotulo}_{indice}]"` em `_placeholder`. Com o `semear` precisando
**ler** a etiqueta de volta, seriam três lugares descrevendo a mesma forma. Este
repositório tem um `AGENTS.md` escrito inteiro sobre isso: "documento duplicado
não diverge com aviso — a versão desatualizada continua parecendo atual".

Em `mask_config.py`, junto de `ROTULO_ENTIDADE`:

```python
# A forma de uma etiqueta, num lugar só.
#
# Ela é ESCRITA aqui (`_placeholder`), LIDA aqui (`Mascarador.semear`) e LIDA em
# `mapa_reverso.reidratar`. Três descrições da mesma forma divergiriam sem aviso,
# e o sintoma seria um rótulo que a reidratação não reconhece — texto que sai
# "reidratado" com um pedaço ainda mascarado, sem erro nenhum.
#
# A classe cobre `Ç` (U+00C7) porque `ENDEREÇO` é um dos rótulos; com `[A-Z_]+`
# ele ficaria de fora em silêncio — o texto sairia "reidratado" com o endereço
# ainda mascarado, sem erro nenhum. Conferido contra os 27 tipos que o motor
# suporta, inclusive os que caem no fallback `rotulo == entity_type`
# (`ORGANIZATION`, `DATE_TIME`, `LAW`).
#
# O intervalo é partido em `À-Ö` e `Ø-Þ` para PULAR `×` (U+00D7, sinal de
# multiplicação), que fica no meio do bloco Latin-1 e não é letra. `À-Þ` inteiro
# funcionaria na prática — nenhum rótulo real usa símbolo —, mas a irmã em
# TypeScript já é precisa, e deixar as duas divergirem em rigor é como a
# duplicação começa a apodrecer.
#
# Ver também `electron/pseudonimos.ts`, `RE_ROTULO`: mesmo contrato, motor de
# regex diferente. Lá se usa `\p{Lu}`, que o `re` da biblioteca padrão não tem.
# As duas precisam casar o mesmo conjunto; se uma mudar, a outra muda junto.
RE_ETIQUETA = re.compile(r"\[([A-ZÀ-ÖØ-Þ_]+)_(\d+)\]")
```

Em `mapa_reverso.py`, trocar a definição local por importação, mantendo o nome
`RE_ROTULO` como apelido para não mexer em quem já o usa:

```python
# A forma da etiqueta vem de quem a cria. Repeti-la aqui daria duas descrições
# da mesma coisa, e a desatualizada continuaria parecendo atual — o sintoma
# seria texto "reidratado" com um pedaço ainda mascarado, sem erro nenhum.
from mask_config import RE_ETIQUETA as RE_ROTULO
```

Isso faz `mapa_reverso` importar `mask_config` — o que **não** quebra a promessa
de "não carrega modelo": `mask_config` é regex e dicionário, sem Presidio nem
torch. Confirme medindo o tempo de `import mapa_reverso`.

**3b.** O contador passa a ser `max(...)+1`, não `len(...)+1`.

Com semeadura, o índice pode vir com buraco (o `remascarar()` renumera do zero,
e um mapa gravado antes disso chega descontínuo). `len()+1` reusaria um número
já tomado, e **duas pessoas virariam a mesma** — que é o defeito mais grave que
este módulo pode produzir. Em `_placeholder`:

```python
        por_rotulo = self._numeros.setdefault(rotulo, {})
        if chave not in por_rotulo:
            # `max(...)+1`, e não `len(...)+1`: com semeadura o índice pode vir
            # com buraco, e reusar um número já tomado fundiria duas pessoas numa.
            proximo = max((i for i, _ in por_rotulo.values()), default=0) + 1
            por_rotulo[chave] = (proximo, texto)
```

**3c.** O método `semear`:

```python
    def semear(self, mapa: dict[str, str]) -> None:
        """
        Restaura a numeração de um mapa já gravado, para que esta execução
        CONTINUE de onde a anterior parou.

        Sem isto, `--autos` compartilha numeração dentro de UMA invocação e não
        entre invocações — e acrescentar peça dias depois é o uso normal de um
        processo. A segunda chamada começaria do `[PESSOA_1]` outra vez, e a
        gravação recusaria por `EtiquetaConflitante` (ou, sem a recusa,
        sobrescreveria e faria a peça de segunda reidratar com o nome de quem
        apareceu na quarta).

        Não conta para o `resumo()`: semear não é encontrar, e `valores_distintos`
        diz o que ESTA execução achou no documento que acabou de ler.
        """
        if self.politica != "placeholder":
            raise ValueError(
                f"semear não faz sentido na política {self.politica!r}: ela não "
                f"numera nada, então não há numeração a continuar (use placeholder)"
            )

        for etiqueta, original in mapa.items():
            achado = RE_ETIQUETA.fullmatch(etiqueta)
            if achado is None:
                raise ValueError(f"etiqueta fora de forma no mapa: {etiqueta!r}")
            rotulo, indice = achado.group(1), int(achado.group(2))

            por_rotulo = self._numeros.setdefault(rotulo, {})
            chave = _normalizar(original)
            anterior = por_rotulo.get(chave)
            if anterior is not None and anterior[0] != indice:
                raise ValueError(
                    f"o mapa dá dois números ao mesmo valor {original!r}: "
                    f"{anterior[0]} e {indice}. Mapa corrompido — seguir com ele "
                    f"escolheria um dos dois em silêncio."
                )
            por_rotulo[chave] = (indice, original)
```

- [ ] **Step 4: Rodar a suíte INTEIRA**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo/python-backend && \
  HF_HOME="/Volumes/SSD do Leandro/tecjustica-sigilo/hf-cache" \
  ../.venv/bin/python -m pytest tests -q 2>&1 | tail -8
```

A troca de `len()+1` para `max()+1` é mudança de contrato da numeração, e
`test_mascaramento.py` a trava de propósito — sem semeadura os dois são
equivalentes (dicionário sem buraco), mas confirme rodando tudo, não raciocinando.

**Proibido** afrouxar assertiva, `skip`, `xfail` ou ajustar esperado.

- [ ] **Step 5: Medir que o import segue leve**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo/python-backend && \
  ../.venv/bin/python -X importtime -c "import mapa_reverso" 2>&1 | tail -3
```

O módulo passou a importar `mask_config`. Confirme que nada de Presidio, spaCy ou
torch entrou por essa porta — o que sustenta a promessa do docstring de que os
testes dele rodam em milissegundos.

- [ ] **Step 6: Commit**

```bash
git add python-backend/mask_config.py python-backend/mapa_reverso.py \
        python-backend/tests/test_mapa_reverso.py
```

A mensagem deve trazer o exemplo de duas invocações em dias diferentes, dizer que
`max()+1` existe porque semeadura pode trazer buraco e reusar número fundiria
duas pessoas numa, e que a forma da etiqueta passou a morar num lugar só.

---

## Task 11: Declarar `cryptography` como dependência direta

`cryptography==48.0.1` já chega ao venv por via transitiva. Passar a importá-lo
direto sem declarar é o defeito que o próprio `requirements.txt` documenta duas
vezes (no `huggingface_hub` e no `python-multipart`): funciona no venv, e some
no instalador, que é montado com `--no-deps`.

**Files:**
- Modify: `/Users/leandroleitedacruz/tecjustica-sigilo/python-backend/requirements.txt`

- [ ] **Step 1: Confirmar que hoje é transitivo**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo && grep -n "cryptography" python-backend/requirements.txt || echo "NÃO declarado — como esperado"
grep -n "^cryptography" python-backend/requirements-embed.txt
```

Expected: não declarado no `requirements.txt`; presente no `-embed.txt`.

- [ ] **Step 2: Declarar, depois da linha do `mcp`**

```
# Cifragem do mapa reverso (`mapa_reverso.py`, Fernet).
#
# Vinha de carona pela cadeia do `mcp` e por isso funcionava sem estar escrito.
# Está declarado porque o embarcado instala com `--no-deps`: ali o que ninguém
# lista não entra, e o pip ainda diz "pronto". É a mesma armadilha que o
# `huggingface_hub` e o `python-multipart` documentam acima — e o mapa reverso
# é pior de perder, porque a falha não é o backend não subir: é `reidratar`
# morrer na importação depois de o documento já ter ido para a nuvem.
cryptography==48.0.1
```

- [ ] **Step 3: Confirmar que a resolução não mudou**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo && \
  VIRTUAL_ENV=.venv uv pip install -r python-backend/requirements.txt --dry-run 2>&1 | tail -5
```

Expected: nada a instalar ou nenhuma mudança de versão — a declaração fixa o
que já estava lá, não traz pacote novo.

- [ ] **Step 4: Rodar a suíte**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo/python-backend && \
  HF_HOME="/Volumes/SSD do Leandro/tecjustica-sigilo/hf-cache" \
  ../.venv/bin/python -m pytest tests -q 2>&1 | tail -4
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo
git add python-backend/requirements.txt
git commit -m "Declara cryptography, que mapa_reverso.py passou a importar

Vinha de carona pela cadeia do mcp. O embarcado instala com --no-deps:
ali o que ninguém lista não entra, e o pip ainda diz 'pronto'.

É a armadilha que huggingface_hub e python-multipart já documentam neste
arquivo. Perder esta é pior: a falha não é o backend não subir, é
reidratar morrer na importação depois de o documento já ter ido para a
nuvem."
```

---

## Task 12: `--autos` no `anonimizar`

**Files:**
- Modify: `/Users/leandroleitedacruz/tecjustica-sigilo/python-backend/cli.py` — `cmd_anonimizar` (`:281`), `_anonimizar_texto` (`:396`), `construir_parser` (`:519`), `comandos` em `main` (`:606`)
- Test: `/Users/leandroleitedacruz/tecjustica-sigilo/python-backend/tests/test_reidratacao_cli.py`

- [ ] **Step 1: Escrever os testes**

Criar `tests/test_reidratacao_cli.py`:

```python
"""
`--autos` e `reidratar` pela linha de comando.

Estes testes rodam a CLI em processo, com `PRESIDIO_NLP_MODE=spacy` (herdado do
conftest) e arquivos de texto puro — não carregam BERT nem OCR. O que medem é o
contrato da interface: que o mapa vai para o disco, que ele NÃO vai para o
stdout, e que o ciclo fecha.
"""

import json

import pytest

import cli
import mapa_reverso


@pytest.fixture
def cofre(tmp_path, monkeypatch):
    monkeypatch.setenv("PRESIDIO_MAPA_CHAVE", str(tmp_path / "mapa.key"))
    monkeypatch.setenv("PRESIDIO_MAPA_DIR", str(tmp_path / "mapas"))
    return tmp_path


def _peca(pasta, nome, texto):
    caminho = pasta / nome
    caminho.write_text(texto, encoding="utf-8")
    return str(caminho)


def test_autos_grava_o_mapa_e_o_ciclo_fecha(cofre, capsys):
    peca = _peca(cofre, "inicial.txt", "O autor JOÃO DA SILVA ajuizou a ação.")
    assert cli.main(["anonimizar", peca, "--offline", "--autos", "5626981", "-o", "-"]) == 0

    saida = capsys.readouterr().out
    assert "[PESSOA_1]" in saida
    assert "JOÃO DA SILVA" not in saida

    mapa = mapa_reverso.ler("5626981")
    assert mapa == {"[PESSOA_1]": "JOÃO DA SILVA"}
    assert mapa_reverso.reidratar(saida, mapa).count("JOÃO DA SILVA") == 1


def test_o_mapa_nunca_aparece_no_stdout_nem_em_json(cofre, capsys):
    """
    O teste mais importante deste arquivo. `anonymize()` devolve `mapa_reverso`
    porque a CLI precisa dele para gravar; imprimi-lo desfaria, numa linha de
    log ou num pipe, o que o programa inteiro existe para fazer.
    """
    peca = _peca(cofre, "inicial.txt", "O autor JOÃO DA SILVA ajuizou a ação.")
    cli.main(["anonimizar", peca, "--offline", "--autos", "5626981", "-f", "json", "-o", "-"])

    saida = capsys.readouterr().out
    assert "JOÃO DA SILVA" not in saida
    assert "mapa_reverso" not in saida
    corpo = json.loads(saida)
    assert "mapa_reverso" not in corpo
    assert "anonymized_text" in corpo


def test_duas_pecas_dos_mesmos_autos_compartilham_a_numeracao(cofre, capsys):
    a = _peca(cofre, "inicial.txt", "ANA SOUZA propôs a ação.")
    b = _peca(cofre, "procuracao.txt", "BRUNO LIMA outorga poderes.")
    assert cli.main([
        "anonimizar", a, b, "--offline", "--autos", "5626981",
        "--output-dir", str(cofre / "saida"),
    ]) == 0

    assert mapa_reverso.ler("5626981") == {
        "[PESSOA_1]": "ANA SOUZA",
        "[PESSOA_2]": "BRUNO LIMA",
    }


def test_duas_invocacoes_nos_mesmos_autos_continuam_a_numeracao(cofre, capsys):
    """
    O caso que o `--autos` promete e que só a semeadura entrega: acrescentar peça
    dias depois é o uso normal de um processo.

    Sem semear, a segunda invocação daria `[PESSOA_1]` a Bruno — e a gravação
    recusaria por EtiquetaConflitante, porque aquele número já é da Ana.
    """
    a = _peca(cofre, "inicial.txt", "ANA SOUZA propôs a ação.")
    assert cli.main(["anonimizar", a, "--offline", "--autos", "5626981", "-o", "-"]) == 0

    b = _peca(cofre, "procuracao.txt", "BRUNO LIMA outorga poderes.")
    assert cli.main(["anonimizar", b, "--offline", "--autos", "5626981", "-o", "-"]) == 0

    saida = capsys.readouterr().out
    assert "[PESSOA_2]" in saida, "a segunda peça tem de continuar a numeração"

    assert mapa_reverso.ler("5626981") == {
        "[PESSOA_1]": "ANA SOUZA",
        "[PESSOA_2]": "BRUNO LIMA",
    }


def test_a_mesma_pessoa_em_invocacoes_diferentes_mantem_o_numero(cofre, capsys):
    a = _peca(cofre, "inicial.txt", "ANA SOUZA propôs a ação.")
    cli.main(["anonimizar", a, "--offline", "--autos", "5626981", "-o", "-"])
    capsys.readouterr()

    b = _peca(cofre, "depoimento.txt", "Ana Souza foi ouvida em audiência.")
    cli.main(["anonimizar", b, "--offline", "--autos", "5626981", "-o", "-"])

    assert "[PESSOA_1]" in capsys.readouterr().out
    assert mapa_reverso.ler("5626981") == {"[PESSOA_1]": "ANA SOUZA"}


def test_anonimizar_para_quando_o_mapa_dos_autos_nao_decifra(cofre, capsys):
    """
    A chave trocada tem de parar a anonimização ANTES de escrever arquivo, não
    depois. Seguir criaria um segundo mapa para os mesmos autos, e ficariam duas
    numerações incompatíveis sem nada dizendo qual explica qual peça.
    """
    from cryptography.fernet import Fernet

    a = _peca(cofre, "inicial.txt", "ANA SOUZA propôs a ação.")
    assert cli.main(["anonimizar", a, "--offline", "--autos", "5626981", "-o", "-"]) == 0
    capsys.readouterr()

    Path(os.environ["PRESIDIO_MAPA_CHAVE"]).write_bytes(Fernet.generate_key())

    b = _peca(cofre, "procuracao.txt", "BRUNO LIMA outorga poderes.")
    saida_b = cofre / "saida-b.txt"
    assert cli.main([
        "anonimizar", b, "--offline", "--autos", "5626981", "-o", str(saida_b)
    ]) == 1
    assert "ALARME" in capsys.readouterr().err
    assert not saida_b.exists(), "parou antes de escrever, como tem de ser"


def test_autos_com_mascara_sem_mapa_e_recusado(cofre, capsys):
    """
    `parcial` e `total` não produzem mapa. Aceitar `--autos` com elas gravaria
    um mapa vazio e prometeria uma reidratação que nunca funcionaria.
    """
    peca = _peca(cofre, "inicial.txt", "O autor JOÃO DA SILVA ajuizou.")
    assert cli.main([
        "anonimizar", peca, "--offline", "--autos", "x", "-m", "total", "-o", "-"
    ]) == 1
    assert "placeholder" in capsys.readouterr().err
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo/python-backend && \
  ../.venv/bin/python -m pytest tests/test_reidratacao_cli.py -q 2>&1 | tail -8
```

Expected: FAIL — `unrecognized arguments: --autos`.

- [ ] **Step 3: Implementar — quatro pontos**

3a. No `construir_parser`, no grupo `anonimizacao`, depois de `--nlp-mode`:

```python
    anonimizacao.add_argument(
        "--autos", metavar="ID",
        help=(
            "Dá a estas peças um espaço de pseudônimos comum e grava o mapa "
            "cifrado, para depois usar em `reidratar`. Sem isto, cada arquivo "
            "numera do zero e o mapa é descartado."
        ),
    )
```

3b. Em `cmd_anonimizar`, junto das outras validações do começo — antes de
resolver backend ou carregar motor:

```python
    # As políticas `parcial` e `total` não passam pelo `_placeholder`, então não
    # produzem mapa nenhum. Aceitar `--autos` com elas gravaria um mapa vazio e
    # prometeria uma reidratação que nunca funcionaria — e o sintoma apareceria
    # só depois, com o documento já enviado.
    if args.autos and args.mascara != "placeholder":
        print(
            f"erro: --autos exige -m placeholder (recebi {args.mascara!r}).",
            file=sys.stderr,
        )
        print(
            "Máscara parcial e cobertura total não deixam o que reidratar: "
            "o valor não está mais no texto.",
            file=sys.stderr,
        )
        return 1

    # O nome dos autos é validado AQUI, junto das outras checagens de linha de
    # comando, e não no fim: ele vira nome de arquivo, e descobrir que é
    # inválido depois de minutos de OCR seria descobrir tarde. A régua é do
    # `mapa_reverso`, para não haver duas.
    if args.autos:
        import mapa_reverso as _mr
        try:
            _mr._caminho(args.autos)
        except ValueError as erro:
            print(f"erro: {erro}", file=sys.stderr)
            return 1
```

3c. Depois de `modo, sessao = _resolver(args)`, criar o `Mascarador` e recusar
o modo remoto:

```python
    mascarador = None
    if args.autos:
        if modo == "remoto":
            print(
                "erro: --autos ainda só funciona no modo local.\n"
                "Rode com --offline (o motor carrega neste processo).",
                file=sys.stderr,
            )
            return 1

        import mapa_reverso
        from mask_config import Mascarador

        # O Mascarador nasce e morre AQUI, no escopo desta função, e `args.autos`
        # é lido uma vez. É isso que impede que ele atravesse duas invocações e
        # misture pessoas de autos diferentes num espaço de numeração comum — o
        # que produziria um texto internamente coerente e factualmente falso.
        # A vida curta é a garantia; movê-lo para um cache de processo a desfaz.
        mascarador = Mascarador(args.mascara)

        # E a semeadura é o que faz `--autos` valer ENTRE invocações, não só
        # dentro de uma. Sem ela, esta chamada numeraria do `[PESSOA_1]` outra
        # vez e a gravação recusaria por `EtiquetaConflitante` — porque a peça de
        # segunda-feira já gastou aquele número com outra pessoa.
        # Ler o mapa aqui, ANTES de qualquer trabalho caro, tem duas funções: dá
        # a semente da numeração e valida que a chave abre o que está gravado.
        # Descobrir que o mapa não decifra depois de minutos de OCR seria
        # descobrir tarde — e com os arquivos já escritos.
        try:
            gravado = mapa_reverso.ler(args.autos)
        except mapa_reverso.CifragemIndisponivel as erro:
            print(f"erro: {erro}", file=sys.stderr)
            return 1
        except mapa_reverso.MapaIlegivel as erro:
            print(f"ALARME: {erro}", file=sys.stderr)
            print(
                "Não anonimizei nada. Seguir criaria um segundo mapa para os "
                "mesmos autos, e você ficaria com duas numerações incompatíveis "
                "sem saber qual explica qual peça.",
                file=sys.stderr,
            )
            return 1
        if gravado:
            mascarador.semear(gravado)
            print(
                f"autos {args.autos}: continuando a numeração de "
                f"{len(gravado)} pseudônimo(s) já gravado(s).",
                file=sys.stderr,
            )
```

3d. Repassar o `mascarador` às duas chamadas de `_anonimizar_texto` e gravar no
fim. Trocar a assinatura do helper:

```python
def _anonimizar_texto(
    texto, entidades, politica, modo, sessao, token, args, motor=None, mascarador=None
) -> dict:
```

e a chamada local dentro dele (as duas ocorrências de `anonymize`):

```python
    if motor is None:
        with local.MotorLocal(quieto=args.quiet) as ctx:
            return ctx.engine.anonymize(
                text=texto, entities=entidades, politica_mascara=politica,
                mascarador=mascarador,
            )
    return motor.anonymize(
        text=texto, entities=entidades, politica_mascara=politica,
        mascarador=mascarador,
    )
```

Nas duas chamadas em `cmd_anonimizar`, acrescentar `mascarador=mascarador` ao
fim. E antes de cada `return 0`, gravar:

```python
    if mascarador is not None:
        import mapa_reverso

        # Esta gravação acontece DEPOIS de os arquivos anonimizados estarem no
        # disco, e não há como ser antes: o mapa só está completo quando a última
        # peça foi lida. Então a falha aqui tem um efeito específico e precisa ser
        # dita com essas palavras — os arquivos existem, parecem certos, e não há
        # como reidratá-los. Um traceback deixaria a pessoa achando que o
        # problema foi na anonimização.
        try:
            destino_mapa = mapa_reverso.gravar(args.autos, mascarador.mapa())
        except (
            mapa_reverso.EtiquetaConflitante,
            mapa_reverso.CifragemIndisponivel,
            mapa_reverso.MapaIlegivel,
            OSError,
        ) as erro:
            print(f"erro ao gravar o mapa dos autos {args.autos}: {erro}", file=sys.stderr)
            print(
                "ATENÇÃO: a anonimização foi concluída e os arquivos de saída "
                "estão gravados, mas SEM mapa não há como reidratá-los depois. "
                "Resolva o que impediu a gravação e rode de novo sobre os mesmos "
                "arquivos — a anonimização é determinística, então a segunda "
                "passada produz os mesmos rótulos.",
                file=sys.stderr,
            )
            return 1
        # Só o caminho no stderr. O mapa é o de-para para o dado real: mesmo o
        # tamanho dele já diz quantas pessoas há no processo.
        print(f"mapa dos autos {args.autos} -> {destino_mapa}", file=sys.stderr)
```

3e. **Inverter a direção do filtro de `_formatar`** — de lista de negação para
lista de permissão.

O filtro em si já existe: foi adiantado para a Task 7b, porque a Task 7 abriu a
saída e deixá-la aberta por cinco tarefas não se justificava. O que falta é
consertar a **direção** dele, e é a revisão de qualidade da 7b que apontou:

```python
publico = {c: v for c, v in resultado.items() if c != "mapa_reverso"}
```

Isso é lista de negação. Funciona para o campo que conhecemos e falha aberto
para o próximo: quem acrescentar outro campo sensível ao retorno de
`anonymize()` não precisa passar por aqui, e nada avisa.

E não é hipótese — é o que já aconteceu. A Task 7 acrescentou `mapa_reverso` ao
retorno do motor, e ele escapou por DUAS saídas que ninguém revisou. A correção
por negação conserta as duas e mantém a terceira em aberto.

**A correção não é arquitetura nova: é adotar o padrão que o próprio
repositório já usa em dois dos quatro pontos de saída** — `response_model` do
Pydantic na rota `/anonymize` (`server.py`), e dicionário montado campo a campo
no `mcp_server.py`. Os dois são lista de permissão estrutural: campo novo no
motor não sai por eles sem alguém escrever o nome.

```python
# O contrato público do `-f json`, declarado. Campo que não está aqui não sai —
# e é essa a direção certa do filtro.
#
# A versão anterior negava `mapa_reverso` por nome, o que conserta o campo
# conhecido e falha aberto no próximo: a Task 7 acrescentou uma chave ao retorno
# do motor e ela escapou por duas saídas que ninguém tinha revisado. Com lista
# de permissão, o campo novo fica de fora até que alguém decida que é público —
# que é a decisão que deve ser explícita.
#
# `entities_found` SAI, e com o texto real dentro: é o contrato documentado do
# `-f json` ("json = com a lista de ocorrências"), e a lista existe para auditar
# o que foi mascarado. Quem não quer o valor real na saída usa o formato `text`.
CAMPOS_PUBLICOS_JSON = (
    "anonymized_text",
    "entities_found",
    "politica_mascara",
    "valores_distintos",
)


def _formatar(resultado: dict, formato: str) -> str:
    if formato == "json":
        publico = {c: resultado[c] for c in CAMPOS_PUBLICOS_JSON if c in resultado}
        return json.dumps(publico, ensure_ascii=False, indent=2)
    return resultado["anonymized_text"]
```

O teste da Task 7b que confere a ausência de `mapa_reverso` e a presença de
`anonymized_text`/`entities_found` continua valendo sem mudança — ele mede
comportamento, não implementação. Acrescente um que trave a direção nova:
um campo inventado (`"campo_sensivel_futuro"`) no dicionário de entrada **não
pode** aparecer na saída.

3f. **Amarrar o `Mascarador` ao identificador dos autos.**

A revisão da Task 7 observou que nada impede um chamador de reusar o mesmo
`Mascarador` entre autos DIFERENTES — o que misturaria pessoas de processos
distintos num espaço de numeração comum, produzindo um texto internamente
coerente e factualmente falso. Era inalcançável até aqui porque nenhum chamador
passava `mascarador=`; esta tarefa é a primeira que passa.

A defesa não precisa de mecanismo: o `Mascarador` nasce dentro de
`cmd_anonimizar`, vive no escopo da função e morre com ela, e `args.autos` é
lido uma vez. Não há caminho para ele atravessar duas invocações. **Mas isso é
verdade por construção e não está dito em lugar nenhum** — e a próxima pessoa a
mover essa criação para fora da função, ou para um cache de processo, não tem
como saber que a vida curta era a garantia.

Escreva isso no comentário da criação do `Mascarador` (passo 3c), em uma ou duas
frases: por que ele nasce e morre aqui, e o que aconteceria se fosse
reaproveitado entre autos.

- [ ] **Step 4: Rodar e ver passar**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo/python-backend && \
  HF_HOME="/Volumes/SSD do Leandro/tecjustica-sigilo/hf-cache" \
  ../.venv/bin/python -m pytest tests -q 2>&1 | tail -6
```

Expected: PASS em tudo, inclusive `test_cli.py`, que cobre a forma antiga.

- [ ] **Step 5: Commit**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo
git add python-backend/cli.py python-backend/tests/test_reidratacao_cli.py
git commit -m "Dá ao anonimizar um --autos que grava o mapa dos pseudônimos

Um Mascarador atravessa o laço de arquivos, então as peças dos mesmos
autos compartilham a numeração: [PESSOA_1] é a mesma pessoa na inicial e
na procuração. Sem isso, um modelo que leia as duas juntas responde
trocando as pessoas.

--autos é recusado com -m parcial e -m total: elas não deixam o que
reidratar, e aceitar gravaria um mapa vazio prometendo um ciclo que
nunca fecharia — com o sintoma aparecendo só depois do envio.

_formatar remove mapa_reverso da saída, no único ponto por onde ela
passa. Do mapa, só o CAMINHO vai ao stderr: o tamanho dele já diria
quantas pessoas há no processo."
```

---

## Task 13: O subcomando `reidratar`

**Files:**
- Modify: `/Users/leandroleitedacruz/tecjustica-sigilo/python-backend/cli.py`
- Test: `/Users/leandroleitedacruz/tecjustica-sigilo/python-backend/tests/test_reidratacao_cli.py`

- [ ] **Step 1: Acrescentar os testes**

```python
# ---------------------------------------------------------------------------
# reidratar
# ---------------------------------------------------------------------------


def test_reidratar_devolve_os_nomes(cofre, capsys):
    mapa_reverso.gravar("5626981", {"[PESSOA_1]": "João da Silva"})
    resposta = _peca(cofre, "resposta.txt", "Segundo a peça, [PESSOA_1] alega quitação.")
    assert cli.main(["reidratar", resposta, "--autos", "5626981", "-o", "-"]) == 0
    assert capsys.readouterr().out.strip() == (
        "Segundo a peça, João da Silva alega quitação."
    )


def test_reidratar_le_de_stdin(cofre, capsys, monkeypatch):
    import io
    mapa_reverso.gravar("5626981", {"[PESSOA_1]": "João da Silva"})
    monkeypatch.setattr("sys.stdin", io.StringIO("[PESSOA_1] compareceu."))
    assert cli.main(["reidratar", "--autos", "5626981", "-o", "-"]) == 0
    assert capsys.readouterr().out.strip() == "João da Silva compareceu."


def test_reidratar_recusa_arquivo_binario(cofre, capsys):
    """
    O engano natural é passar o PDF dos autos: o `anonimizar` aceita PDF, e nada
    na linha de comando sugere que este subcomando não aceita. Sem a recusa, sai
    um UnicodeDecodeError cru.
    """
    mapa_reverso.gravar("5626981", {"[PESSOA_1]": "João da Silva"})
    pdf = cofre / "autos.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    assert cli.main(["reidratar", str(pdf), "--autos", "5626981", "-o", "-"]) == 1
    erro = capsys.readouterr().err
    assert "não é texto" in erro
    assert "autos.pdf" in erro


def test_reidratar_recusa_texto_que_nao_e_utf8(cofre, capsys):
    """Extensão de texto com bytes latin-1 — sai de sistema judicial antigo."""
    mapa_reverso.gravar("5626981", {"[PESSOA_1]": "João da Silva"})
    ruim = cofre / "resposta.txt"
    ruim.write_bytes("[PESSOA_1] compareceu à audiência.".encode("latin-1"))
    assert cli.main(["reidratar", str(ruim), "--autos", "5626981", "-o", "-"]) == 1
    assert "não é UTF-8" in capsys.readouterr().err


def test_reidratar_sem_mapa_avisa_e_falha(cofre, capsys):
    """
    Sem mapa, devolver o texto com os rótulos e sair 0 seria o pior resultado:
    parece que funcionou. Autos errado e mapa vencido são os dois casos, e os
    dois merecem código de saída diferente de zero.
    """
    resposta = _peca(cofre, "resposta.txt", "[PESSOA_1] alega quitação.")
    assert cli.main(["reidratar", resposta, "--autos", "inexistente", "-o", "-"]) == 1
    assert "não há mapa" in capsys.readouterr().err


def test_reidratar_avisa_rotulo_sem_entrada(cofre, capsys):
    mapa_reverso.gravar("5626981", {"[PESSOA_1]": "João da Silva"})
    resposta = _peca(cofre, "resposta.txt", "[PESSOA_1] e [PESSOA_7] discordam.")
    assert cli.main(["reidratar", resposta, "--autos", "5626981", "-o", "-"]) == 0
    capturado = capsys.readouterr()
    assert "João da Silva e [PESSOA_7]" in capturado.out
    assert "[PESSOA_7]" in capturado.err
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo/python-backend && \
  ../.venv/bin/python -m pytest tests/test_reidratacao_cli.py -q 2>&1 | tail -8
```

Expected: FAIL — `invalid choice: 'reidratar'`.

- [ ] **Step 3: Implementar**

3a. A função, junto das outras `cmd_*` (depois de `cmd_ler`):

```python
def cmd_reidratar(args) -> int:
    """
    Desfaz a máscara num texto que voltou de fora, usando o mapa dos autos.

    Não fala com o motor e não carrega modelo: é substituição de rótulo por
    valor a partir de um mapa já gravado. Roda em milissegundos, e roda com o
    SSD montado e nada mais.

    Por que isto NÃO é ferramenta de MCP: chamada por um agente, ela devolve os
    nomes reais ao contexto dele — que é a nuvem — e desfaz o que o programa
    existe para fazer. `mcp_server.py` segue com quatro ferramentas, e o
    `smoke-backend.sh` confere esse número.
    """
    import mapa_reverso

    try:
        mapa = mapa_reverso.ler(args.autos)
    except (ValueError, mapa_reverso.CifragemIndisponivel) as erro:
        print(f"erro: {erro}", file=sys.stderr)
        return 1
    except mapa_reverso.MapaIlegivel as erro:
        # Ramo próprio, e não junto dos outros, porque a reação é outra: aqui o
        # mapa EXISTE. Tratar isto como "não tenho mapa" devolveria o texto com
        # os rótulos em claro e deixaria quem lê concluir que o prazo venceu.
        print(f"ALARME: {erro}", file=sys.stderr)
        print(
            "Nada foi reidratado. Se você recriou a chave de propósito, os mapas "
            "gravados antes dela são perda esperada. Se não recriou, alguém "
            "mexeu na chave.",
            file=sys.stderr,
        )
        return 1

    if not mapa:
        print(
            f"erro: não há mapa para os autos {args.autos!r}.",
            file=sys.stderr,
        )
        print(
            "Ou o nome está errado, ou o prazo de guarda venceu e o mapa foi "
            "apagado (padrão: 7 dias; veja PRESIDIO_MAPA_PRAZO_DIAS).",
            file=sys.stderr,
        )
        return 1

    if args.files:
        # `reidratar` recebe a RESPOSTA que voltou de um modelo, que é texto.
        # Recusar binário aqui, e não deixar o `read_text` explodir, porque o
        # engano natural é passar o PDF dos autos — o `anonimizar` aceita PDF, e
        # nada na linha de comando sugere que este subcomando não aceita. Um
        # `UnicodeDecodeError` cru mandaria a pessoa procurar defeito de
        # codificação num arquivo que simplesmente não é para entrar aqui.
        binarios = [f for f in args.files if not _e_texto_puro(f)]
        if binarios:
            nomes = ", ".join(Path(f).name for f in binarios)
            print(f"erro: reidratar recusa {nomes} — não é texto.", file=sys.stderr)
            print(
                "Este subcomando reidrata a RESPOSTA que voltou do modelo, que é "
                "texto. Para ler um documento, use `ler` ou `anonimizar`.",
                file=sys.stderr,
            )
            return 1

        partes = []
        for bruto in args.files:
            caminho = Path(bruto)
            if not caminho.exists():
                print(f"erro: {caminho} não existe", file=sys.stderr)
                return 1
            try:
                partes.append(caminho.read_text(encoding="utf-8"))
            except UnicodeDecodeError:
                # Extensão de texto com bytes que não são UTF-8 (um `.txt` salvo
                # em latin-1, que sai de sistema judicial antigo). A régua acima
                # olha a extensão e não o conteúdo, então este ramo existe.
                print(
                    f"erro: {caminho} não é UTF-8. Converta antes "
                    f"(`iconv -f latin1 -t utf8`).",
                    file=sys.stderr,
                )
                return 1
        texto = "\n\n".join(partes)
    else:
        texto = sys.stdin.read()

    saida = mapa_reverso.reidratar(texto, mapa)

    # Rótulo que sobrou é informação, não ruído: significa que o texto fala de
    # alguém que este mapa não conhece — autos trocados, ou peça anonimizada
    # noutra sessão. Silenciar entregaria um documento com lacuna invisível.
    sobraram = sorted(set(mapa_reverso.RE_ROTULO.findall(saida)))
    if sobraram:
        print(
            f"aviso: {len(sobraram)} rótulo(s) sem entrada no mapa, deixados "
            f"como estão: {', '.join(sobraram)}",
            file=sys.stderr,
        )

    _escrever(args.output, saida)
    return 0
```

3b. No `construir_parser`, depois do parser de `ler`:

```python
    p = sub.add_parser(
        "reidratar", parents=[pai],
        help="Devolve os nomes reais a um texto que voltou mascarado de fora.",
    )
    p.add_argument(
        "files", nargs="*",
        help="Arquivos de texto. Sem argumento, lê de stdin.",
    )
    p.add_argument(
        "--autos", required=True, metavar="ID",
        help="Os autos cujo mapa usar (o mesmo ID passado no `anonimizar`).",
    )
    p.set_defaults(func=cmd_reidratar)
```

3c. No `main`, acrescentar ao conjunto que preserva a forma clássica:

```python
    comandos = {"anonimizar", "ler", "ocr", "status", "conectar", "mcp", "reidratar"}
```

3d. **Documentar o subcomando nos DOIS shims** — dívida deixada pela Task 3.

O cabeçalho do `tecjustica-sigilo.sh` chegou a listar `reidratar` como exemplo
antes de o comando existir, e a linha foi retirada: documentação de comando
inexistente engana quem copia o exemplo. Agora que ele existe, a linha volta —
e vai também para o par do Windows, porque dois arquivos que documentam
conjuntos diferentes de comandos começam a contar histórias diferentes. É o
problema que o `AGENTS.md` deste repositório foi escrito para descrever.

Em `python-backend/tecjustica-sigilo.sh`, na lista de exemplos do cabeçalho:

```
#   tecjustica-sigilo reidratar resposta.txt --autos 5626981
```

Em `python-backend/tecjustica-sigilo.cmd`, na lista equivalente, com a forma do
batch:

```
REM   tecjustica-sigilo.cmd reidratar resposta.txt --autos 5626981
```

Confira ao fim que os dois arquivos listam o mesmo conjunto de subcomandos,
ressalvados `status` e `conectar` — que no `.sh` seguem de fora de propósito,
porque dependem do aplicativo aberto, e no macOS ele só existe a partir da
Fase 2.

- [ ] **Step 4: Rodar e ver passar**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo/python-backend && \
  HF_HOME="/Volumes/SSD do Leandro/tecjustica-sigilo/hf-cache" \
  ../.venv/bin/python -m pytest tests -q 2>&1 | tail -6
```

Expected: PASS em tudo.

- [ ] **Step 5: Ciclo completo à mão, pelo shim instalado**

```bash
cd /tmp && printf 'O autor JOÃO DA SILVA, CPF 529.982.247-25, pede a rescisão.\n' > peca.txt
PRESIDIO_NLP_MODE=spacy tecjustica-sigilo anonimizar /tmp/peca.txt --offline --autos teste-ciclo -o /tmp/mascarada.txt
cat /tmp/mascarada.txt
# simula a resposta que voltaria de um modelo, falando em rótulos
printf 'Conforme a peça, [PESSOA_1] (CPF [CPF_1]) pede a rescisão contratual.\n' > /tmp/resposta.txt
tecjustica-sigilo reidratar /tmp/resposta.txt --autos teste-ciclo
```

Expected: a última linha traz `JOÃO DA SILVA` e `529.982.247-25` de volta.
Limpar depois: `tecjustica-sigilo reidratar --help` não apaga nada, então rode
`rm -f /tmp/peca.txt /tmp/mascarada.txt /tmp/resposta.txt` e apague o mapa de
teste com `python -c "import mapa_reverso; mapa_reverso.esquecer('teste-ciclo')"`.

- [ ] **Step 6: Commit**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo
git add python-backend/cli.py python-backend/tests/test_reidratacao_cli.py
git commit -m "Acrescenta o subcomando reidratar, e só como subcomando

Fecha o ciclo: a resposta que volta falando em [PESSOA_1] sai com o
nome. Não carrega modelo — é substituição a partir de um mapa gravado.

Não é ferramenta de MCP de propósito. Chamada por um agente, ela devolve
os nomes reais ao contexto dele, que é a nuvem, e desfaz o que o
programa existe para fazer. mcp_server.py segue com quatro ferramentas e
o smoke confere o número.

Sem mapa, sai 1 em vez de devolver o texto com os rótulos e 0: o
segundo parece ter funcionado. Rótulo que sobra vira aviso no stderr —
significa que o texto fala de alguém que este mapa não conhece, e
silenciar entregaria um documento com lacuna invisível."
```

---

## Task 14: Travar as duas promessas que só um teste segura

Duas afirmações do desenho não estão travadas por nada: que o MCP **não** ganha
`reidratar`, e que o mapa não vaza pelas rotas HTTP. Sem teste, a primeira
morre no dia em que alguém achar prático expor a ferramenta.

**Files:**
- Create: `/Users/leandroleitedacruz/tecjustica-sigilo/python-backend/tests/test_mapa_nao_vaza.py`

- [ ] **Step 1: Escrever os testes**

```python
"""
As duas promessas que só um teste segura.

**O MCP não expõe reidratar.** É a regra de ouro do desenho, e é frágil do jeito
pior: expor a ferramenta parece uma conveniência óbvia para quem chegar depois,
o código funcionaria perfeitamente, e nenhum teste reclamaria. O efeito é que os
nomes reais voltam ao contexto do modelo — a nuvem — e o programa passa a
desfazer o que existe para fazer.

**As rotas HTTP não devolvem o mapa.** `anonymize()` passou a incluir
`mapa_reverso` no dicionário de retorno. Uma rota que serialize o resultado
inteiro entrega o de-para a qualquer cliente pareado, inclusive uma extensão de
navegador.
"""

import mcp_server


def test_mcp_declara_exatamente_quatro_ferramentas():
    assert len(mcp_server.FERRAMENTAS) == 4


def test_nenhuma_ferramenta_de_mcp_reidrata():
    nomes = " ".join(str(chave) for chave in mcp_server.FERRAMENTAS).lower()
    assert "reidrat" not in nomes
    assert not hasattr(mcp_server, "ferramenta_reidratar")


def test_o_modulo_de_mcp_nao_importa_mapa_reverso():
    """
    Import é o começo do caminho. Não importando, a ferramenta não pode nascer
    por descuido — e o dia em que alguém a importar, este teste fala.
    """
    from pathlib import Path
    fonte = Path(mcp_server.__file__).read_text(encoding="utf-8")
    assert "mapa_reverso" not in fonte


def test_rotas_de_anonimizacao_nao_devolvem_o_mapa():
    from fastapi.testclient import TestClient

    import server
    from conftest import TOKEN

    cliente = TestClient(server.app)
    resposta = cliente.post(
        "/anonymize",
        json={"text": "O autor JOÃO DA SILVA ajuizou.", "entities": []},
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert resposta.status_code == 200, resposta.text
    assert "mapa_reverso" not in resposta.text
    assert "JOÃO DA SILVA" not in resposta.text
```

- [ ] **Step 2: Rodar**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo/python-backend && \
  HF_HOME="/Volumes/SSD do Leandro/tecjustica-sigilo/hf-cache" \
  ../.venv/bin/python -m pytest tests/test_mapa_nao_vaza.py -q 2>&1 | tail -15
```

Expected: os três primeiros PASS de imediato. O quarto é o que pode reprovar —
e se reprovar, **é defeito real**, não teste a ajustar.

- [ ] **Step 3: Se a rota vazar o mapa, filtrar na borda**

Em `server.py`, no handler de `/anonymize` (e no de `/v1/anonimizar`, se ele
também serializar o dicionário cru), remover a chave antes de responder:

```python
    # `mapa_reverso` fica FORA da resposta HTTP. Ele existe no retorno do motor
    # porque a CLI precisa dele em processo; entregá-lo por rede o daria a
    # qualquer cliente pareado — inclusive uma extensão de navegador, que é
    # justamente quem nunca deve ver o de-para.
    resultado.pop("mapa_reverso", None)
```

Repetir o teste do Step 2 até passar.

- [ ] **Step 4: Rodar a suíte inteira**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo/python-backend && \
  HF_HOME="/Volumes/SSD do Leandro/tecjustica-sigilo/hf-cache" \
  ../.venv/bin/python -m pytest tests -q 2>&1 | tail -4
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo
git add python-backend/tests/test_mapa_nao_vaza.py python-backend/server.py
git commit -m "Trava as duas promessas que nenhum teste segurava

Que o MCP não expõe reidratar é a regra de ouro do desenho, e era
frágil do jeito pior: expor a ferramenta parece conveniência óbvia para
quem chega depois, funcionaria perfeitamente e nada reclamaria. O efeito
é os nomes reais voltando ao contexto do modelo.

O teste confere as quatro ferramentas, a ausência do nome e que
mcp_server nem IMPORTA mapa_reverso — import é o começo do caminho.

E as rotas HTTP não devolvem mapa_reverso: anonymize() passou a
incluí-lo, e uma rota que serialize o resultado inteiro entrega o de-para
a qualquer cliente pareado, extensão de navegador incluída."
```

---

## Task 15: `docs/macos.md` e o registro do que foi medido

**Files:**
- Create: `/Users/leandroleitedacruz/tecjustica-sigilo/docs/macos.md`
- Modify: `/Users/leandroleitedacruz/tecjustica-sigilo/README.md`

- [ ] **Step 1: Escrever `docs/macos.md`**

Conteúdo obrigatório, nesta ordem:

1. **Pré-requisitos** — macOS 14+ arm64 (o wheel do `onnxruntime` é
   `macosx_14_0_arm64`), Python 3.12, Node 20+, `uv`, e um volume com ~5 GB.
2. **Instalação** — `scripts/setup-macos.sh`, o que ele faz, e o symlink `.venv`.
3. **Por que o peso sai do disco interno** e como mudar (`TECJUSTICA_PESO`).
4. **A CLI** — o shim, o symlink em `~/.local/bin`, e o registro do MCP
   (`claude mcp add tecjustica-sigilo -- ~/.local/bin/tecjustica-sigilo mcp`).
5. **O ciclo de reidratação**, com o exemplo de três comandos do Task 13 Step 5.
6. **Onde ficam a chave e os mapas**, e por que em volumes diferentes
   (`noowners`), com a tabela de variáveis: `PRESIDIO_MAPA_CHAVE`,
   `PRESIDIO_MAPA_DIR`, `PRESIDIO_MAPA_PRAZO_DIAS`.
7. **O que NÃO existe no Mac ainda** — `.dmg`, GUI empacotada, `--autos` no
   modo remoto. Seção explícita: um leitor que procura e não acha supõe defeito.
8. **Testes** — os comandos exatos do Task 4.
9. **Duas ressalvas medidas durante a execução**, que só existem por terem sido
   testadas e merecem estar onde alguém as leia:
   - `uv venv --allow-existing` sobre um venv de **outra** versão de Python não
     falha, mas deixa `lib/python3.11/` órfão ao lado do novo. Não acontece hoje
     (o `setup-macos.sh` pina 3.12 e é o único criador do caminho); passa a
     importar no dia em que a versão pinada subir — aí, apague o venv antes.
   - O teto de 40 saltos do `tecjustica-sigilo.sh` é **inalcançável pelo caminho
     normal de invocação neste sistema**: o macOS tem `SYMLOOP_MAX=32` e o
     kernel recusa abrir o arquivo antes de qualquer linha do script rodar,
     com mensagem própria (`Too many levels of symbolic links`, código 126).
     O teto segue como defesa das vias que não passam pelo `open()` do kernel,
     mas quem for depurar uma cadeia de symlinks vai ver a mensagem do sistema,
     não a do shim — e procurar a mensagem do shim no log seria procurar a
     errada.

10. **Os dois alarmes, e o que fazer com cada um.** Não são erros de uso; são as
    duas recusas que o mapa reverso emite, e a reação certa é diferente:

    | | O que houve | O que fazer |
    |---|---|---|
    | `MapaIlegivel` | o mapa **existe** e não decifra: a chave não é mais a que o cifrou | Se você recriou a chave de propósito, os mapas gravados antes dela são perda esperada — apague-os. Se **não** recriou, alguém mexeu na chave. O arquivo não é apagado automaticamente, de propósito |
    | `EtiquetaConflitante` | `[PESSOA_1]` vale uma coisa no disco e chegou valendo outra | A numeração recomeçou. Normalmente significa que a semeadura não rodou — confira se o `--autos` está escrito igual ao da vez anterior (ver a ressalva de maiúsculas abaixo, se ela se aplicar) |

    Nos dois casos **nada é gravado**, e a mensagem diz isso.

11. **A diferença entre "o mapa venceu" e "o mapa não decifra".** As duas deixam
    você sem reidratação, e é por isso que elas não podem ter a mesma cara.
    Vencido é o prazo de guarda funcionando: o arquivo foi apagado e a saída
    simplesmente não tem mapa. Ilegível é alarme, com a palavra `ALARME` na
    saída. Se você vê rótulo em claro **sem** nenhuma mensagem, foi vencimento;
    com mensagem, foi a chave.

12. **Um limite que nenhuma cifragem alcança**, medido ao implementar a chave:
    quem consegue trocar a chave pode recifrar um mapa **forjado** com ela. Aí o
    `decrypt` tem sucesso, nenhum alarme dispara, e a reidratação escreve os
    valores que a outra pessoa escolheu — sem erro e sem sintoma. Cifragem
    autenticada não ajuda porque ela prova "isto foi escrito por quem tem esta
    chave", e nesse cenário o atacante tem esta chave.

    Consequência, dita com todas as letras: **o `0600` do arquivo e a recusa em
    volume `noowners` não são defesa periférica — são a única coisa que faz
    "esta chave" significar "eu"**.

13. **Uma lacuna de cobertura de teste, declarada.** Dois testes da suíte ficam
    `skipped` por dependerem de `PRESIDIO_CORPUS_OCR`, uma pasta de PDFs
    escaneados reais que não está no repositório. São justamente os de **PDF
    escaneado de verdade** — o caso que mais importa para uso judicial. Apontar
    a variável para um punhado de digitalizações fecha isso. Não é porte, é dado
    de teste; e teste pulado passa por teste aprovado em log corrido.

- [ ] **Step 1b: Registrar no `CLAUDE.md` a decisão da chave**

Levantado pelo implementador da Task 9, e ele está certo: a decisão "chave no
disco interno porque o volume externo monta com `noowners`, e Keychain descartado
porque a CLI e o MCP rodam fora da sessão gráfica" é exatamente do tipo que o
`CLAUDE.md` deste repositório existe para guardar — e hoje ela vive só numa
mensagem de commit, onde ninguém procura.

Acrescente ao `CLAUDE.md`, na seção que couber, em três ou quatro linhas: a
decisão, o fato medido que a sustenta (`Owners: Disabled` no volume externo), e
por que o Keychain não serve aqui. **Não** duplique a explicação longa da
`docs/macos.md` — aponte para ela.

- [ ] **Step 2: Corrigir a linha do README que ficou falsa**

Trocar `Linux/Mac: rode em modo dev (abaixo). Build nativo sob demanda.` por:

```markdown
**macOS (Apple Silicon):** CLI e servidor MCP funcionam nativamente —
veja [`docs/macos.md`](docs/macos.md). A interface gráfica roda em modo dev;
`.dmg` ainda não é gerado.

**Linux:** rode em modo dev. Build nativo sob demanda.
```

- [ ] **Step 3: Conferir que os comandos do doc realmente rodam**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo && \
  grep -oE '^\s*(tecjustica-sigilo|scripts/|claude mcp)[^`]*' docs/macos.md | head -20
```

Rodar cada um à mão. Comando em documentação que não foi executado é comando
errado — o `README` deste projeto tem uma seção inteira sobre isso.

- [ ] **Step 4: Rodar a suíte uma última vez e conferir o repositório limpo**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo/python-backend && \
  HF_HOME="/Volumes/SSD do Leandro/tecjustica-sigilo/hf-cache" \
  ../.venv/bin/python -m pytest tests -q 2>&1 | tail -4
cd /Users/leandroleitedacruz/tecjustica-sigilo && git status --short
```

Expected: PASS, e `git status` sem nada além do doc a commitar.

- [ ] **Step 5: Commit e publicar a branch**

```bash
cd /Users/leandroleitedacruz/tecjustica-sigilo
git add docs/macos.md README.md
git commit -m "Documenta o porte de macOS e corrige a linha que ficou falsa

O README dizia 'Linux/Mac: rode em modo dev'. No Mac a CLI e o MCP agora
rodam nativamente, e continuar dizendo aquilo mandaria o leitor para o
caminho mais difícil dos dois.

A seção 'o que ainda não existe no Mac' é deliberada: quem procura .dmg
e não acha menção nenhuma supõe defeito, não ausência."
git push -u origin macos
```

---

## Self-Review

**Cobertura da spec, seção por seção:**

| Spec | Tarefa |
|---|---|
| §4 porte, 4 arquivos de andaime | 1 (setup), 2 (smoke), 3 (shim). `setup-python-embed.sh` e `fetch-ocr-models.sh` não precisam de mudança — o primeiro é da Fase 3, o segundo já tem o candidato `bin/python` |
| §4 guarda de SSD ausente | 3, Step 4 |
| §5.1 grafia original | 6 |
| §5.2 `mapa()` | 6 |
| §5.3 sessão multi-peça | 7 (injeção) + 12 (`--autos` na CLI) |
| §5.4 comando `reidratar` | 8 (puro) + 13 (CLI) |
| §5.1 regra de ouro (não é tool MCP) | 13 + **14** (travado por teste) |
| §5.2 chave, falha fechada, `noowners` | 9 |
| §5.2 prazo de 7 dias | 10 |
| §6 suíte existente como gate | 4 |
| §6 novos testes da reidratação | 6, 7, 8, 9, 10, 12, 13, 14 |
| §6 gate de acurácia no acervo do Leandro | **não coberto** — depende de um corpus com gabarito que ainda não existe. Registrado em `docs/macos.md` (Task 15, item 8) como o passo que fecha a Fase 1 quando houver corpus |
| §7 limites declarados | Task 15, item 7 |
| §8 Fases 2-4 | fora de escopo, declarado no File Structure |

**Lacuna consciente:** o gate de acurácia sobre o acervo próprio. Medir exige
corpus anotado; sem ele o harness é **pulado**, e o `README` do upstream avisa
que teste pulado passa por teste aprovado em log corrido. Fica como item aberto,
não como passo fingido.

**Consistência de nomes** (conferida contra as tarefas):
`Mascarador.mapa()`, `Mascarador.politica`, `Mascarador._indices`,
`anonymize(..., mascarador=)`, `mapa_reverso.reidratar(texto, mapa)`,
`mapa_reverso.gravar(autos, mapa)`, `mapa_reverso.ler(autos)`,
`mapa_reverso.esquecer(autos)`, `mapa_reverso.CifragemIndisponivel`,
`mapa_reverso.RE_ROTULO`, `mapa_reverso._chave()`, `mapa_reverso._caminho()`,
`mapa_reverso._volume_honra_dono()`, `mapa_reverso._analisar_montagens()`,
`cmd_reidratar`, `--autos`, `PRESIDIO_MAPA_CHAVE`, `PRESIDIO_MAPA_DIR`,
`PRESIDIO_MAPA_PRAZO_DIAS`, `TECJUSTICA_PESO`.

**`--autos`, e não `--sessao`:** `cli.py:96` já usa `sessao` para a sessão HTTP
com o aplicativo (`modo, sessao = _resolver(args)`). Duas coisas diferentes com
o mesmo nome no mesmo arquivo é defeito à espera de acontecer.
