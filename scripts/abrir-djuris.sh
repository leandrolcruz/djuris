#!/usr/bin/env bash
#
# Abre o Direito&Juris a partir do Finder, sem terminal.
#
# Três coisas que um `npm run dev:electron` solto não resolve, e que são o
# motivo de este arquivo existir:
#
# 1. **Aplicativo lançado pelo Finder não herda o PATH do shell.** Ele recebe
#    `/usr/gnu/bin:/usr/local/bin:/bin:/usr/bin:.` e nada mais — e o `node`
#    desta máquina mora no nvm, fora disso. Sem resolver o caminho à mão, o
#    duplo-clique falha com "command not found: npm", mensagem que nem aparece
#    porque não há terminal para mostrá-la.
#
# 2. **Erro precisa ser VISÍVEL.** Sem terminal, `echo` não chega a ninguém. O
#    que não der certo sai em diálogo do sistema. Calar aqui é pior que no
#    terminal: a pessoa clica no ícone e simplesmente nada acontece.
#
# 3. **Fechar a janela tem de fechar tudo.** O `dev:electron` roda o Vite e o
#    Electron sob `concurrently` sem `--kill-others`: saindo do aplicativo, o
#    Vite fica para trás, e cada abertura deixaria mais um. Aqui o Vite é
#    nosso, e morre junto.
set -uo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PESO="${DJURIS_PESO:-/Volumes/SSD do Leandro/djuris}"

avisar() {
  /usr/bin/osascript -e "display dialog \"$1\" with title \"Direito&Juris\" buttons {\"OK\"} default button 1 with icon caution" >/dev/null 2>&1
  exit 1
}

# --- o node, que o Finder não entrega ---------------------------------------
NODE=""
if command -v node >/dev/null 2>&1; then
  NODE="$(command -v node)"
else
  # O mais recente do nvm. Resolver por glob em vez de cravar a versão: o nvm
  # atualiza, e um caminho fixo quebraria calado na próxima atualização.
  for candidato in "$HOME"/.nvm/versions/node/*/bin/node; do
    [ -x "$candidato" ] && NODE="$candidato"
  done
fi
[ -n "$NODE" ] || avisar "Não encontrei o Node nesta máquina.\n\nO aplicativo precisa dele para subir a interface."
export PATH="$(dirname "$NODE"):$PATH"

# --- o peso, que mora no volume externo -------------------------------------
[ -d "$PESO" ] || avisar "O volume com os modelos não está montado.\n\nEsperava encontrar:\n$PESO\n\nMonte o disco e abra de novo."

# --- uma instância por vez ---------------------------------------------------
if pgrep -f "$RAIZ/node_modules/electron/dist" >/dev/null 2>&1; then
  /usr/bin/osascript -e 'display notification "O Direito&Juris já está aberto." with title "Direito&Juris"' >/dev/null 2>&1
  exit 0
fi

cd "$RAIZ" || avisar "A pasta do projeto sumiu:\n$RAIZ"

REGISTRO="${TMPDIR:-/tmp}/djuris-abertura.log"
: > "$REGISTRO"

npm run build:electron-ts >>"$REGISTRO" 2>&1 \
  || avisar "Falhou ao compilar a interface.\n\nDetalhe em:\n$REGISTRO"

# O Vite é NOSSO: subimos, usamos e matamos. É isso que evita o acúmulo de
# processos órfãos a cada abertura.
npx vite >>"$REGISTRO" 2>&1 &
VITE=$!
trap 'kill "$VITE" 2>/dev/null' EXIT

for _ in $(seq 1 120); do
  /usr/bin/curl -sf -o /dev/null http://localhost:5173 && break
  sleep 0.5
done

/usr/bin/curl -sf -o /dev/null http://localhost:5173 \
  || avisar "A interface não subiu em 60 segundos.\n\nDetalhe em:\n$REGISTRO"

# Em primeiro plano de propósito: quando o Electron sai, o `trap` acima derruba
# o Vite. É o fechamento limpo que o `concurrently` não dá.
npx electron . >>"$REGISTRO" 2>&1
