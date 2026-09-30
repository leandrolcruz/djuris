#!/usr/bin/env bash
#
# Importa o backend EMPACOTADO com o Python que vai no instalador.
#
# Por que isto existe: a rota /ocr recebe a página como multipart/form-data, e o
# FastAPI exige `python-multipart` para montá-la. Ele não falha ao chamar a rota
# — falha ao IMPORTAR o módulo, quando o decorador registra a rota. O pacote
# estava no venv de desenvolvimento e não no Python embarcado, então 110 testes
# passaram, o instalador foi gerado, e o backend morria na máquina do usuário. A
# tela ficava em "Carregando motor de anonimização" para sempre, sem erro
# visível, porque quem morreu foi o processo filho.
#
# Nenhum teste unitário pega isso: o que falta não é lógica, é um arquivo dentro
# do interpretador que vai no instalador. Só executá-lo pega.
#
# Importar cobre as rotas, que é onde o decorador falha. Mas não cobria tudo: o
# tokenizador do spaCy só é tocado quando o motor é construído, e o embarcado
# saiu uma vez sem `pt_core_news_lg` e sem `thinc`, com todas as rotas
# registradas e o import limpo. Por isso o `pt_core_news_lg` é carregado aqui
# também — custa segundos e é pré-requisito dos DOIS modos, não só do leve
# (no modo BERT ele entra como tokenizador; ver `_transformer_config`).
#
# O que continua de fora, de propósito: subir o servidor e baixar o BERT. São
# 2,5 GB que chegam na primeira execução do app, não no build.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
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
if [[ -f "$PYTHON" ]]; then
  echo "Importando o backend com o Python embarcado."
  echo "(pela ponte do WSL leva minutos — o torch é lido arquivo a arquivo)"
elif [[ -x "$RAIZ/.venv/bin/python" ]]; then
  BACKEND="$RAIZ/python-backend"
  PYTHON="$RAIZ/.venv/bin/python"
  echo "Sem python-embed; verificando com o venv sobre python-backend/."
else
  echo "Nem python-embed nem .venv encontrados." >&2
  echo "Rode scripts/setup-macos.sh (macOS) ou monte o embarcado." >&2
  exit 1
fi

VERIFICACAO='
import sys
import server

# `app.openapi()`, e não `app.routes`.
#
# O FastAPI atual não achata as rotas de um router incluído em `app.routes`:
# elas aparecem como um único `_IncludedRouter` sem `path`, e as rotas `/v1`
# ficariam invisíveis para uma checagem ingênua — reprovando um build correto.
# O `openapi()` resolve os routers e é a visão que um cliente de verdade teria.
caminhos = set(server.app.openapi()["paths"])

exigidas = {
    # As que a interface usa. Quebrar qualquer uma trava o aplicativo.
    "/health", "/ocr", "/processar", "/anonymize", "/remascarar",
    # A API local. Sem elas, a CLI, uma extensão e o MCP levam 404 no aplicativo
    # instalado, enquanto em desenvolvimento tudo funciona — porque ali se roda
    # do diretório de origem, e não da cópia empacotada.
    "/v1/info", "/v1/parear", "/v1/anonimizar", "/v1/documento", "/v1/clientes",
}
faltando = exigidas - caminhos
if faltando:
    print("ROTAS AUSENTES: %s" % sorted(faltando), file=sys.stderr)
    raise SystemExit(1)
print("ok: %d rotas registradas, inclusive /ocr e a API /v1" % len(caminhos))

# O servidor MCP importa? É dependência de RUNTIME nova, e o embarcado é
# montado com `--no-deps`: o que não estiver no requirements-embed.txt não
# entra, o pip diz "pronto" e a falta só aparece quando alguém roda o comando.
# Foi assim com o `python-multipart` — 110 testes verdes, instalador entregue,
# backend morrendo na largada.
import mcp_server
if len(mcp_server.FERRAMENTAS) != 4:
    print("MCP: esperava 4 ferramentas", file=sys.stderr)
    raise SystemExit(1)
print("ok: mcp_server importa e declara as 4 ferramentas")

import spacy
spacy.load("pt_core_news_lg")
print("ok: pt_core_news_lg carrega (tokenizador dos dois modos)")
'

if ! saida="$(cd "$BACKEND" && "$PYTHON" -c "$VERIFICACAO" 2>&1)"; then
  echo "O BACKEND EMPACOTADO NÃO IMPORTA:" >&2
  echo "$saida" | tail -25 | sed 's/^/  /' >&2
  echo >&2
  echo "Falta biblioteca no python-embed? Veja o fim de scripts/sync-backend.sh." >&2
  exit 1
fi

echo "$saida" | sed 's/^/  /'
