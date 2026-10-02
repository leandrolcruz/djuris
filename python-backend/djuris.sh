#!/usr/bin/env bash
#
# Par POSIX do `djuris.cmd`: chama o `cli.py` com o interpretador do
# projeto. O `"$@"` repassa a linha inteira, então os subcomandos funcionam sem
# que este arquivo os conheça:
#
#   djuris autos.pdf              (PDF, DOCX, imagem — com OCR)
#   djuris arquivo.txt -o saida.md
#   cat arquivo.txt | djuris
#   djuris ler autos.pdf          (extrai sem anonimizar)
#   djuris ocr pagina.png         (reconhece o texto de uma imagem)
#   djuris reidratar resposta.txt --autos 5626981
#   djuris mcp                    (servidor MCP em stdio)
#
# Este arquivo é instalado por symlink em ~/.local/bin, então ele resolve o
# próprio caminho real antes de subir dois níveis: sem isso, `dirname $0` daria
# ~/.local/bin e o cli.py não estaria lá.
set -euo pipefail

ORIGEM="${BASH_SOURCE[0]}"
ORIGEM_INICIAL="$ORIGEM"
SALTOS=0
TETO_SALTOS=40
while [[ -L "$ORIGEM" ]]; do
  SALTOS=$((SALTOS + 1))
  # Teto para não pendurar o terminal num symlink circular (a -> b -> a):
  # sem ele, este laço não teria como sair sozinho — travamento sem
  # mensagem é o pior desfecho possível aqui, porque quem instalou a
  # ferramenta fica olhando para um terminal parado sem indício do quê
  # investigar. 40 é folga generosa sobre qualquer cadeia real (a
  # instalação normal resolve em 1 salto) e ainda assim falha rápido.
  if (( SALTOS > TETO_SALTOS )); then
    echo "Cadeia de symlinks longa demais ou circular a partir de '$ORIGEM_INICIAL' (mais de $TETO_SALTOS saltos)." >&2
    exit 1
  fi
  DESTINO="$(readlink "$ORIGEM")"
  [[ "$DESTINO" == /* ]] && ORIGEM="$DESTINO" || ORIGEM="$(dirname "$ORIGEM")/$DESTINO"
done
BACKEND="$(cd "$(dirname "$ORIGEM")" && pwd)"
RAIZ="$(cd "$BACKEND/.." && pwd)"

PESO="${DJURIS_PESO:-/Volumes/SSD do Leandro/djuris}"
PYTHON="$RAIZ/.venv/bin/python"

# A mensagem importa: o modo de falha mais provável desta instalação é o volume
# externo desmontado, e o sintoma cru seria um ModuleNotFoundError de torch —
# que manda a pessoa depurar dependência quando o problema é um cabo. Mas
# DJURIS_PESO é override do usuário: só teria a forma "dois níveis sob
# /Volumes" no caso padrão desta máquina, e para qualquer outra forma
# (`dirname "$PESO"`) apontar como "o volume" seria afirmar algo que não se
# sabe — dirname de `$HOME/peso-sigilo` dá `$HOME`, que não é volume nenhum.
# Por isso a mensagem nomeia o que de fato se sabe (o caminho que faltou) e
# sugere a causa provável sem afirmá-la como fato.
if [[ ! -x "$PYTHON" ]]; then
  echo "O motor não está acessível em $PYTHON." >&2
  if [[ ! -d "$PESO" ]]; then
    echo "O caminho '$PESO' não existe. Se ele fica num volume externo, monte-o e tente de novo." >&2
  else
    echo "Rode $RAIZ/scripts/setup-macos.sh para montar o ambiente." >&2
  fi
  exit 1
fi

export HF_HOME="${HF_HOME:-$PESO/hf-cache}"
# Pasta do mapa de pseudônimos (rótulo <-> valor original) gravado pela
# anonimização, para permitir desfazer a máscara depois — ainda sem
# consumidor no código; o subcomando que vai lê-lo chega numa task futura.
export PRESIDIO_MAPA_DIR="${PRESIDIO_MAPA_DIR:-$PESO/mapas}"

exec "$PYTHON" "$BACKEND/cli.py" "$@"
