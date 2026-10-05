#!/usr/bin/env python3
"""Importa el catálogo de moaiplug_free a una instantánea JSON reproducible.

El repo hermano `moaiplug_free` guarda sus canales como literales Java en
`FreeCatalog.java` (generados a su vez por iptv-org/countries/ar.m3u). Este
script extrae esas filas y las deja en `tools/data/canales_free.json`, que es
lo único que lee `generate_catalog.py`.

Es un paso MANUAL y explícito: `build.sh` no lo ejecuta (el build no debe
depender del repo hermano). Para reimportar:

    python3 tools/import_free_catalog.py

Cada fila importada trae `id`, `nombre`, `logo`, `categoria`, `pais` y `url`,
tal cual en el origen. La deduplicación contra el catálogo AR, el saneado de
nombres/categorías y los logos son responsabilidad de `generate_catalog.py`.
"""
import argparse
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_FREE_REPO = "/home/apogeo/moai/moaiplug_free"
DEFAULT_OUT = os.path.join(ROOT, "tools", "data", "canales_free.json")

# new Channel("id", "nombre", "logo", "categoria", "pais", "url"),
ROW_RE = re.compile(
    r'new Channel\(\s*"((?:[^"\\]|\\.)*)"\s*,\s*"((?:[^"\\]|\\.)*)"\s*,'
    r'\s*"((?:[^"\\]|\\.)*)"\s*,\s*"((?:[^"\\]|\\.)*)"\s*,'
    r'\s*"((?:[^"\\]|\\.)*)"\s*,\s*"((?:[^"\\]|\\.)*)"\s*\)'
)

# Categorías tal cual las usa moai3 (generate_catalog.CATEGORY_PRIORITY).
CATEGORIAS_VALIDAS = {
    "Aire", "Interior", "Noticias", "Deportes", "Cine y Series", "Infantil",
    "Cultural", "Novelas", "Cocina", "Música", "Radios", "Religioso",
    "General", "Adultos",
}
# El catálogo Free escribe la categoría sin acento.
CATEGORIA_ALIASES = {"Musica": "Música"}


def unescape(s):
    return (s.replace('\\"', '"').replace("\\\\", "\\"))


def parse_catalog(path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    rows = []
    for m in ROW_RE.finditer(src):
        cid, nombre, logo, categoria, pais, url = [
            unescape(g) for g in m.groups()
        ]
        rows.append({
            "id": cid,
            "nombre": nombre,
            "logo": logo,
            "categoria": CATEGORIA_ALIASES.get(categoria, categoria),
            "pais": pais,
            "url": url,
        })
    return src, rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--free-repo", default=DEFAULT_FREE_REPO,
                    help="repo moaiplug_free (default: %(default)s)")
    ap.add_argument("--out", default=DEFAULT_OUT,
                    help="destino del snapshot (default: tools/data/canales_free.json)")
    ap.add_argument("--stdout", action="store_true",
                    help="no escribir archivo, imprimir el JSON")
    args = ap.parse_args()

    src_path = os.path.join(
        args.free_repo, "src/plugin/java/com/infomak/moai/free/FreeCatalog.java")
    if not os.path.isfile(src_path):
        sys.exit(f"No encontré {src_path} (¿repo moaiplug_free movido?)")

    src, rows = parse_catalog(src_path)
    if not rows:
        sys.exit(f"No extraje ningún canal de {src_path}")

    errores = []
    vistos = set()
    for r in rows:
        if not r["id"] or not r["url"]:
            errores.append(f"{r['id'] or '?'}: id/url vacío")
        if r["id"] in vistos:
            errores.append(f"{r['id']}: id duplicado dentro del origen")
        vistos.add(r["id"])
        if r["categoria"] not in CATEGORIAS_VALIDAS:
            errores.append(f"{r['id']}: categoría desconocida {r['categoria']!r}")
    if errores:
        sys.exit("Catálogo inválido:\n  " + "\n  ".join(errores))

    payload = {
        "origen": "moaiplug_free/src/plugin/java/com/infomak/moai/free/FreeCatalog.java",
        "origen_sha256": hashlib.sha256(src.encode("utf-8")).hexdigest(),
        "total": len(rows),
        "canales": rows,
    }

    if args.stdout:
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f">> {len(rows)} canales importados de moaiplug_free -> {args.out}")
    print(f">> sha256 FreeCatalog.java: {payload['origen_sha256'][:16]}…")


if __name__ == "__main__":
    main()