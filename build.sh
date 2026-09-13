#!/usr/bin/env bash
# Compila el plugin .dex del contrato moai v1 y regenera manifest.json
# (con sha256 del dex) en la raíz del repo.
#
# Requisitos: JDK 8+ y Android SDK con build-tools (d8).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
SDK="${ANDROID_HOME:-$HOME/Android/Sdk}"
BUILD_TOOLS="${ANDROID_BUILD_TOOLS:-$SDK/build-tools/36.0.0}"

pick_platform() {
    for dir in "$SDK"/platforms/*; do
        [ -e "$dir/android.jar" ] && echo "$dir"
    done | sort | tail -n 1
}
PLATFORM="$(pick_platform)"
if [ -z "$PLATFORM" ] || [ ! -x "$BUILD_TOOLS/d8" ]; then
    echo "Falta el Android SDK (android.jar y build-tools/d8)." >&2
    exit 1
fi
ANDROID_JAR="$PLATFORM/android.jar"
D8="$BUILD_TOOLS/d8"

echo ">> Limpiando build/"
rm -rf "$ROOT/build"
mkdir -p "$ROOT/build/contract" "$ROOT/build/plugin" "$ROOT/build/out"

echo ">> Compilando stubs del contrato"
javac -source 8 -target 8 \
    -d "$ROOT/build/contract" \
    "$ROOT"/src/contract/java/com/infomak/moai/contract/*.java

echo ">> Compilando plugin (contra contrato + android.jar)"
javac -source 8 -target 8 \
    -cp "$ROOT/build/contract:$ANDROID_JAR" \
    -d "$ROOT/build/plugin" \
    "$ROOT"/src/plugin/java/com/infomak/moai/ar/*.java

( cd "$ROOT/build" && jar cf plugin.jar -C plugin . )
echo ">> Empaquetado: $(jar tf "$ROOT/build/plugin.jar" | wc -l) archivos"

echo ">> d8 -> dex"
"$D8" --min-api 21 \
    --lib "$ANDROID_JAR" \
    --classpath "$ROOT/build/contract" \
    --output "$ROOT/build/out" \
    "$ROOT/build/plugin.jar"

cp "$ROOT/build/out/classes.dex" "$ROOT/plugin.dex"
echo ">> plugin.dex: $(stat -c%s "$ROOT/plugin.dex") bytes"

SHA256="$(sha256sum "$ROOT/plugin.dex" | cut -d' ' -f1)"
echo ">> sha256: $SHA256"

cat > "$ROOT/manifest.json" <<EOF
{
  "id": "moai_ar",
  "nombre": "Moai Argentina",
  "version": "1.2.1",
  "minContrato": 1,
  "maxContrato": 1,
  "clase": "com.infomak.moai.ar.MoaiArPlugin",
  "sha256": "$SHA256",
  "canales": [
    {
      "id": "canal_7_salta",
      "nombre": "7 Salta",
      "logo": "https://play-lh.googleusercontent.com/wqC28g5axDfQhkUhcALzgqvyF8bCwyCr06knFxa0FS0d0zy5lQG_9uC_ZQu-HJ-f9oXdFr4QJjGPZAUscuEwSQ",
      "categoria": "Aire",
      "pais": "Argentina"
    },
    {
      "id": "caze_fhd",
      "nombre": "CAZÉ TV FHD",
      "logo": "https://i.postimg.cc/XJjjwygm/cazetv-logo-0-2048x2048-Easy-Resize-com-(1).jpg",
      "categoria": "Entretenimiento",
      "pais": "Argentina"
    },
    {
      "id": "unicanal_flow",
      "nombre": "Unicanal Flow",
      "logo": "https://banners.femon.net/banners/6978d540a14188.24291079.png",
      "categoria": "Entretenimiento",
      "pais": "Argentina"
    }
  ]
}
EOF
echo ">> manifest.json generado"
echo "OK"