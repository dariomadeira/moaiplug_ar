#!/usr/bin/env python3
"""
Herramienta de diagnóstico para verificar los logos del catálogo de moaiplug_ar.

A diferencia de check_channels.py (que prueba el stream), esto descarga una
muestra de cada logo y valida que el servidor responda 200/206 con un
content-type de imagen real (no una página de error HTML de Cloudflare).

Uso:
    python3 tools/check_logos.py
    python3 tools/check_logos.py --limit 20
    python3 tools/check_logos.py --failed-only
    python3 tools/check_logos.py --cat Noticias
    python3 tools/check_logos.py --output logos.json
    python3 tools/check_logos.py --print-urls        # imprime id<TAB>logo de los fallados
"""

import argparse
import concurrent.futures
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import quote, urlsplit, urlunsplit

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
)

# Wikimedia bloquea (HTTP 429) los User-Agent genéricos de navegador: su
# política de robots pide un UA descriptivo con contacto. Sin esto, la mitad
# de los logos de upload.wikimedia.org da 429 y parece que están caídos.
WIKIMEDIA_HOSTS = ("upload.wikimedia.org", "commons.wikimedia.org", "thumb.wikimedia.org")
# Ancho de la miniatura que pedimos a Special:FilePath. 250px alcanza para
# los logos de la grilla del reproductor y pesa poco.
WIKIMEDIA_WIDTH = 250

WIKIMEDIA_UA = "moaiplug_ar-logos-audit/1.0 (https://github.com/; canal TV catalog check)"

# Wikimedia rechaza /thumb/ con anchos no estandar: devuelve HTTP 400
# "Use thumbnail sizes listed on https://w.wiki/GHai". Y los anchos validos
# varian por archivo (120/250/330/500/1280/1920 para unos, 320 para ninguno),
# asi que adivinar no sirve. Special:FilePath?width=N si o si genera la
# miniatura correcta para cualquier N.
WIKIMEDIA_THUMB_RE = re.compile(
    r"^https?://upload\.wikimedia\.org/wikipedia/commons/thumb/"
    r"(?:[0-9a-f]{1,2}/){1,3}([^/]+?)/\d+px-", re.I
)


# Mismo regex que check_channels.py: lee el catálogo embebido en el .java,
# que es la fuente de verdad de lo que viaja en el plugin.dex.
CATALOG_PATTERN = re.compile(
    r'\{\s*"([^"]+)",\s*"([^"]+)",\s*"([^"]*)",\s*"([^"]*)",\s*"([^"]*)",\s*"([^"]*)",\s*"([^"]+)",\s*"([^"]*)",\s*new String\[\]\s*\{([^}]*)\}\s*\}'
)

IMAGE_TYPES = ("image/",)
# Algunos CDNs sirven application/octet-stream para .png legitimo.
OCTET_OK = ("image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif",
            "image/svg+xml", "image/x-icon", "image/vnd.microsoft.icon",
            "image/avif", "application/octet-stream", "binary/octet-stream", "")


def load_channels_from_catalog():
    repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    catalog_path = os.path.join(
        repo_dir, "src/plugin/java/com/infomak/moai/ar/MoaiCatalog.java"
    )

    if not os.path.exists(catalog_path):
        raise FileNotFoundError(f"No se encontró {catalog_path}")

    with open(catalog_path, "r", encoding="utf-8") as f:
        content = f.read()

    channels = []
    for m in CATALOG_PATTERN.findall(content):
        cid, name, logo, cat, pais, ctype, url, drm, raw_headers = m
        channels.append(
            {"id": cid, "nombre": name, "logo": logo, "categoria": cat, "pais": pais}
        )
    return channels


def _is_image(content_type, sample):
    """True si la respuesta parece una imagen y no una página de error."""
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct.startswith(IMAGE_TYPES):
        return True
    # Content-Type ausente/ambiguo: nos fiamos de la firma binaria.
    if ct in OCTET_OK or ct == "":
        return not sample.lstrip()[:64].lower().startswith((
            b"<!doctype", b"<html", b"<?xml", b"<script",
        ))
    return False


def _fixup_logo_url(url):
    """Normaliza URLs que fallan por formato, no por estar caidas."""
    m = WIKIMEDIA_THUMB_RE.match(url)
    if m:
        fname = m.group(1)
        return f"https://commons.wikimedia.org/wiki/Special:FilePath/{fname}?width={WIKIMEDIA_WIDTH}"
    return url


def _percent_encode(url):
    """Percent-encodea la parte path de la URL (el catálogo trae 'ñ' cruda)."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    path = quote(parts.path, safe="/%:@&=+$,~")
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))


def check_single_logo(channel, timeout=10, retries=1, verbose=False):
    """Descarga una muestra del logo. Regresa dict con status/code/error."""
    cid = channel["id"]
    logo = (channel["logo"] or "").strip()

    if not logo:
        return {
            "id": cid, "nombre": channel["nombre"], "categoria": channel["categoria"],
            "status": "EMPTY", "code": 0, "error": "sin logo en el catálogo", "logo": "",
        }

    if not logo.startswith("http://") and not logo.startswith("https://"):
        return {
            "id": cid, "nombre": channel["nombre"], "categoria": channel["categoria"],
            "status": "FAIL", "code": 0,
            "error": f"URL no http(s): {logo[:60]}", "logo": logo,
        }

    probe = _fixup_logo_url(logo)
    # El catálogo trae URLs crudas con no-ASCII (ej. "CNN_en_Español.png").
    # urllib lanza UnicodeEncodeError al abrirlas -> hay que percent-encodear.
    probe = _percent_encode(probe)
    wikimedia = any(h in probe for h in WIKIMEDIA_HOSTS)
    ua = WIKIMEDIA_UA if wikimedia else DEFAULT_UA

    start = time.time()
    last_err = None
    last_code = 0

    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(probe, headers={
                "User-Agent": ua,
                "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
            })
            # Range para no bajar la imagen entera.
            req.add_header("Range", "bytes=0-1023")

            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                code = resp.status
                ctype = resp.headers.get("Content-Type", "")
                sample = resp.read(1024)
                latency = round((time.time() - start) * 1000)

            if code in (200, 206) and _is_image(ctype, sample):
                return {
                    "id": cid, "nombre": channel["nombre"],
                    "categoria": channel["categoria"], "status": "OK", "code": code,
                    "content_type": ctype, "bytes": len(sample),
                    "latency_ms": latency, "error": None, "logo": logo,
                    "probed_url": probe if probe != logo else None,
                }

            last_code = code
            last_err = f"HTTP {code} content-type={ctype or 'n/d'}"

        except urllib.error.HTTPError as e:
            last_code = e.code
            last_err = f"HTTP {e.code}: {e.reason}"
        except Exception as e:
            reason = str(getattr(e, "reason", e))
            if "timed out" in reason.lower() or "timed out" in str(e).lower():
                reason = f"Timeout (> {timeout}s)"
            last_err = reason

        if attempt < retries:
            time.sleep(0.6)

    return {
        "id": cid, "nombre": channel["nombre"], "categoria": channel["categoria"],
        "status": "FAIL", "code": last_code,
        "latency_ms": round((time.time() - start) * 1000),
        "error": last_err, "logo": logo, "probed_url": probe,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Verifica que los logos del catálogo de moaiplug_ar carguen de verdad."
    )
    parser.add_argument("--workers", "-w", type=int, default=24,
                        help="Hilos concurrentes (default: 24)")
    parser.add_argument("--timeout", "-t", type=int, default=10,
                        help="Timeout por logo en segundos (default: 10)")
    parser.add_argument("--retries", "-r", type=int, default=1,
                        help="Reintentos por logo (default: 1)")
    parser.add_argument("--limit", "-l", type=int, default=0)
    parser.add_argument("--cat", "-c", type=str, default=None)
    parser.add_argument("--search", "-s", type=str, default=None)
    parser.add_argument("--host", type=str, default=None,
                        help="Filtrar por host del logo (ej: wikimedia, postimg)")
    parser.add_argument("--only", type=str, default=None,
                        help="Coma-separados ids de canal a comprobar")
    parser.add_argument("--delay", type=float, default=0.0,
                        help="Pausa por request en segundos (serio con CDNs)")
    parser.add_argument("--failed-only", action="store_true")
    parser.add_argument("--output", "-o", type=str, default=None)
    parser.add_argument("--print-urls", action="store_true",
                        help="Al final imprime 'id<TAB>logo' de cada fallo (para bulk-edit)")

    args = parser.parse_args()

    # Los nombres traen acentos/banderas; sin esto el print revienta con
    # UnicodeEncodeError en la consola y aborta el reporte.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    channels = load_channels_from_catalog()
    total_in_plugin = len(channels)

    if args.cat:
        cl = args.cat.lower()
        channels = [c for c in channels if cl in c["categoria"].lower()]
    if args.search:
        sl = args.search.lower()
        channels = [c for c in channels
                    if sl in c["nombre"].lower() or sl in c["id"].lower()]
    if args.host:
        hl = args.host.lower()
        channels = [c for c in channels
                    if hl in (c["logo"] or "").lower()]
    if args.only:
        wanted = {x.strip() for x in args.only.split(",") if x.strip()}
        channels = [c for c in channels if c["id"] in wanted]
    if args.limit > 0:
        channels = channels[: args.limit]

    sin_logo = sum(1 for c in channels if not (c["logo"] or "").strip())

    print("=" * 74)
    print("   🖼️  VERIFICADOR DE LOGOS — MOAI ARGENTINA (moaiplug_ar)")
    print("=" * 74)
    print(f"Total en catálogo:  {total_in_plugin} canales")
    print(f"A comprobar ahora:  {len(channels)}  (de ellos {sin_logo} sin logo en catálogo)")
    print(f"Hilos paralelos:    {args.workers} | Timeout: {args.timeout}s | Reintentos: {args.retries}")
    print("-" * 74)

    results = []
    ok_count = fail_count = 0
    start_total = time.time()

    def run(ch):
        if args.delay:
            time.sleep(args.delay)
        return check_single_logo(ch, args.timeout, args.retries)

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(run, ch): ch for ch in channels}
        idx = 0
        for future in concurrent.futures.as_completed(futures):
            idx += 1
            res = future.result()
            results.append(res)

            if res["status"] == "OK":
                ok_count += 1
                if not args.failed_only:
                    print(f"[{idx:3d}/{len(channels):3d}] 🟢 OK   ({res.get('latency_ms',0):5d}ms) "
                          f"| [{res['categoria'][:10]:10s}] {res['nombre']}")
            elif res["status"] == "EMPTY":
                print(f"[{idx:3d}/{len(channels):3d}] ⚪ VACÍO | [{res['categoria'][:10]:10s}] {res['nombre']}")
            else:
                fail_count += 1
                code_str = f"HTTP {res['code']}" if res["code"] else "FAIL"
                print(f"[{idx:3d}/{len(channels):3d}] 🔴 {code_str:8s} | "
                      f"[{res['categoria'][:10]:10s}] {res['nombre']} -> {res['error']}")

    total_time = round(time.time() - start_total, 2)
    pct = round((ok_count / len(channels) * 100), 1) if channels else 0

    print("=" * 74)
    print("                     📊 RESUMEN FINAL")
    print("=" * 74)
    print(f" Canales analizados:   {len(channels)}")
    print(f" 🟢 Logos OK:         {ok_count} ({pct}%)")
    print(f" 🔴 Logos caídos:     {fail_count}")
    print(f" ⚪ Sin logo (vacío):  {sin_logo}")
    print(f" ⏱️  Tiempo total:      {total_time} segundos")
    print("=" * 74)

    if args.print_urls and fail_count:
        print("\n--- ID<TAB>LOGO (fallados) ---")
        for r in sorted(results, key=lambda x: x["id"]):
            if r["status"] == "FAIL":
                print(f"{r['id']}\t{r['logo']}")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump({
                "total": len(channels),
                "ok": ok_count,
                "fail": fail_count,
                "empty": sin_logo,
                "ok_percent": pct,
                "duration_sec": total_time,
                "channels": results,
            }, f, indent=2, ensure_ascii=False)
        print(f"💾 Reporte guardado en: {args.output}\n")


if __name__ == "__main__":
    main()
