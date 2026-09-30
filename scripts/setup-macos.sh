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
