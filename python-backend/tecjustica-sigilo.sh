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
