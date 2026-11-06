#!/usr/bin/env bash
# build-app.sh — monta o bundle "SuperFast DM.app" (e, com --dmg, um .dmg).
# Uso:
#   ./build-app.sh          # gera build/SuperFast DM.app
#   ./build-app.sh --dmg    # gera também build/SuperFastDM.dmg
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
APP="$ROOT/app"
BUILD="$HERE/build"
NAME="SuperFast DM"
APPBUNDLE="$BUILD/$NAME.app"

echo "==> Limpando build anterior"
rm -rf "$BUILD"
mkdir -p "$APPBUNDLE/Contents/MacOS" "$APPBUNDLE/Contents/Resources"

echo "==> Copiando código do app para Resources/"
cp -R "$APP"/. "$APPBUNDLE/Contents/Resources/"
rm -rf "$APPBUNDLE/Contents/Resources/__pycache__" 2>/dev/null || true

echo "==> Escrevendo launcher (Contents/MacOS/superfast-dm)"
cat > "$APPBUNDLE/Contents/MacOS/superfast-dm" <<'LAUNCHER'
#!/bin/bash
# Launcher do SuperFast DM: sobe o servidor local e abre o navegador.
APPDIR="$(cd "$(dirname "$0")/.." && pwd)/Resources"

PY=""
for c in python3 /usr/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  osascript -e 'display dialog "Python 3 nao encontrado. Instale com:  xcode-select --install   ou   brew install python3" buttons {"OK"} default 0 with icon stop'
  exit 1
fi

# Já está rodando? Só abre o navegador.
if curl -s --max-time 2 "http://127.0.0.1:7860/health" 2>/dev/null | grep -q '"ok": *[tT]rue'; then
  open "http://127.0.0.1:7860/"
  exit 0
fi

export SFD_OPEN="${SFD_OPEN:-1}"
export SFD_DEST="${SFD_DEST:-$HOME/Downloads/superfast-dm}"
export SFD_DATA="${SFD_DATA:-$HOME/.superfast-dm}"

"$PY" "$APPDIR/server.py" &
SPID=$!
trap 'kill "$SPID" 2>/dev/null' EXIT INT TERM
wait "$SPID"
LAUNCHER
chmod +x "$APPBUNDLE/Contents/MacOS/superfast-dm"

echo "==> Escrevendo Info.plist"
cat > "$APPBUNDLE/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>SuperFast DM</string>
  <key>CFBundleDisplayName</key><string>SuperFast DM</string>
  <key>CFBundleIdentifier</key><string>com.superfastdm.app</string>
  <key>CFBundleVersion</key><string>1.1</string>
  <key>CFBundleShortVersionString</key><string>1.1</string>
  <key>CFBundleExecutable</key><string>superfast-dm</string>
  <key>CFBundleIconFile</key><string>icon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleInfoDictionaryVersion</key><string>6.0</string>
  <key>CFBundleSignature</key><string>????</string>
  <key>LSMinimumSystemVersion</key><string>10.13</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSSupportsAutomaticTermination</key><false/>
  <key>NSSupportsSuddenTermination</key><false/>
  <key>LSApplicationCategoryType</key><string>public.app-category.utilities</string>
  <key>LSBackgroundOnly</key><false/>
</dict>
</plist>
PLIST

echo -n "APPL????" > "$APPBUNDLE/Contents/PkgInfo"

echo "==> Gerando ícone (.icns)"
ICONSET="$BUILD/icon.iconset"
python3 "$HERE/gen_icon.py" "$ICONSET"
if command -v iconutil >/dev/null 2>&1; then
  iconutil -c icns "$ICONSET" -o "$APPBUNDLE/Contents/Resources/icon.icns"
else
  echo "  aviso: iconutil indisponível — usando PNG como ícone"
  cp "$ICONSET/icon_512x512.png" "$APPBUNDLE/Contents/Resources/icon.icns"
fi
rm -rf "$ICONSET"

echo "==> Assinando (ad-hoc)"
codesign --force --deep --sign - "$APPBUNDLE" 2>/dev/null \
  || echo "  aviso: codesign falhou (opcional; o app ainda roda localmente)"

echo ""
echo "============================================================"
echo " App gerado: $APPBUNDLE"
echo "============================================================"

if [ "${1:-}" = "--dmg" ]; then
  echo "==> Gerando DMG"
  DMG="$BUILD/SuperFastDM.dmg"
  STAGE="$BUILD/dmg-stage"
  rm -f "$DMG"; rm -rf "$STAGE"; mkdir -p "$STAGE"
  cp -R "$APPBUNDLE" "$STAGE/"
  ln -s /Applications "$STAGE/Applications"
  hdiutil create -volname "SuperFast DM" -srcfolder "$STAGE" -ov -format UDZO "$DMG" >/dev/null
  rm -rf "$STAGE"
  echo " DMG gerado: $DMG"
fi
