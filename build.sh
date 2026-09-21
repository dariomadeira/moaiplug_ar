#!/usr/bin/env bash
# Compila el plugin .dex del contrato moai v1 y regenera manifest.json
# (con sha256 del dex) en la raíz del repo.
#
# Requisitos: JDK 8+ y Android SDK con build-tools (d8).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
SDK="${ANDROID_HOME:-$HOME/Android/Sdk}"
BUILD_TOOLS="${ANDROID_BUILD_TOOLS:-$SDK/build-tools/36.0.0}"
PLUGIN_VERSION="${PLUGIN_VERSION:-1.4.2}"

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

echo ">> Generando catálogo (MoaiCatalog.java + ult_canales.json)"
python3 "$ROOT/tools/generate_catalog.py"

echo ">> Limpiando build/"
rm -rf "$ROOT/build/contract" "$ROOT/build/plugin" "$ROOT/build/out"
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

echo ">> Generando manifest.json"
python3 - "$ROOT" "$PLUGIN_VERSION" "$SHA256" <<'PYEOF'
import json, os, sys
root, version, sha256 = sys.argv[1], sys.argv[2], sys.argv[3]

with open(os.path.join(root, "build", "ult_canales.json"), encoding="utf-8") as f:
    canales = json.load(f)

manifest = {
    "id": "moai_ar",
    "tag": "ar",
    "nombre": "Moai Argentina",
    "version": version,
    "minContrato": 1,
    "maxContrato": 1,
    "clase": "com.infomak.moai.ar.MoaiArPlugin",
    "sha256": sha256,
    "canalInicial": "telefe",
    "canales": canales,
}
with open(os.path.join(root, "manifest.json"), "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)

print(f">> manifest.json: {len(canales)} canales, version {version}, sha256 {sha256[:12]}…")
PYEOF
echo "OK"