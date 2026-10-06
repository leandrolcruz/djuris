#!/usr/bin/env bash
#
# Gera o atalho clicável do Direito&Juris em ~/Applications.
#
# Existe para a abertura não depender de terminal. O `.app` é uma casca
# AppleScript de três linhas que chama `abrir-djuris.sh` — toda a lógica mora
# lá, e é lá que se mexe.
#
# Por que `.app` e não `.command`: o `.command` abre uma janela de Terminal
# junto e a deixa aberta enquanto o programa roda. Funciona, e parece defeito.
#
# Reinstalar é seguro: o destino é apagado e refeito.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DESTINO="${1:-$HOME/Applications/Direito&Juris.app}"
ABRIR="$RAIZ/scripts/abrir-djuris.sh"

[ -x "$ABRIR" ] || { echo "erro: $ABRIR não é executável" >&2; exit 1; }

mkdir -p "$(dirname "$DESTINO")"
rm -rf "$DESTINO"

# O `&` no fim solta o script: sem ele o AppleScript fica preso esperando o
# Electron sair, e o macOS marca o atalho como "não respondendo" o tempo todo
# em que o aplicativo estiver aberto.
/usr/bin/osacompile -o "$DESTINO" \
  -e "do shell script \"exec '$ABRIR' > /dev/null 2>&1 &\""

# Ícone: o `.icns` precisa de todos os tamanhos, e `iconutil` recusa o conjunto
# se faltar algum par (1x e 2x).
if [ -f "$RAIZ/build/icon.png" ]; then
  conjunto="$(mktemp -d)/djuris.iconset"
  mkdir -p "$conjunto"
  for t in 16 32 64 128 256 512; do
    sips -z "$t" "$t" "$RAIZ/build/icon.png" --out "$conjunto/icon_${t}x${t}.png" >/dev/null
    sips -z "$((t * 2))" "$((t * 2))" "$RAIZ/build/icon.png" \
      --out "$conjunto/icon_${t}x${t}@2x.png" >/dev/null
  done
  iconutil -c icns "$conjunto" -o "$DESTINO/Contents/Resources/applet.icns"
  rm -rf "$(dirname "$conjunto")"
fi

echo "atalho instalado: $DESTINO"
echo "Arraste-o para o Dock se quiser."
