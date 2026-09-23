#!/usr/bin/env python3
"""
Herramienta de diagnóstico para verificar el estado de los canales de moaiplug_ar.

Prueba la resolución y respuesta real del stream (HLS .m3u8 o DASH .mpd),
incluyendo la generación dinámica del token de Flow CDN y validación de manifest.

Uso:
    python3 tools/check_channels.py
    python3 tools/check_channels.py --limit 20
    python3 tools/check_channels.py --cat Noticias
    python3 tools/check_channels.py --search espn
    python3 tools/check_channels.py --failed-only
    python3 tools/check_channels.py --output reporte.json
"""

import argparse
import concurrent.futures
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urljoin, urlparse

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
)

FLOW_SEED_URLS = [
    "https://chromecast.cvattv.com.ar/live/c6eds/Viajar/SA_Live_dash_cenc/Viajar.mpd",
    "https://cdn-py.cvattv.com.ar/live/c6eds/EWTN/SA_Live_dash_enc/EWTN.mpd",
    "https://cdn-py.cvattv.com.ar/live/c4eds/UNICANAL_C4/SA_Live_dash_enc/UNICANAL_C4.mpd",
    "https://cdn-py.cvattv.com.ar/live/c4eds/TELEFUTURO_C4/SA_Live_dash_enc/TELEFUTURO_C4.mpd",
]

FLOW_MARKERS = [
    "cvattv.com.ar",
    "cvattv.com.py",
    "flow.com.ar",
    "flow.com.py",
    "cdn-token.app.flow.com.ar",
]

PATH_PATTERN = re.compile(r"(live/c\d+eds/[^?#]*)")
PATH_PATTERN_ALT = re.compile(r"(c\d+eds/[^?#]*)")
TOK_PATTERN = re.compile(r"/(tok_[^/]+)")

# Cache global de token Flow
g_cached_token = None
g_cached_time = 0


def probe_flow_seed(seed_url):
    current = seed_url
    for _ in range(5):
        req = urllib.request.Request(current, headers={"User-Agent": DEFAULT_UA})

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        opener = urllib.request.build_opener(NoRedirect)
        try:
            resp = opener.open(req, timeout=10)
            loc = resp.headers.get("Location")
            if not loc:
                loc = current
        except urllib.error.HTTPError as e:
            loc = e.headers.get("Location")
            if not loc:
                return None
        except Exception:
            return None

        m = TOK_PATTERN.search(loc)
        if m:
            parsed = urlparse(loc)
            return parsed.netloc.split(":")[0], m.group(1)
        current = urljoin(current, loc)
    return None


def get_flow_token():
    global g_cached_token, g_cached_time
    now = time.time()
    if g_cached_token and (now - g_cached_time) < 50:
        return g_cached_token

    for seed in FLOW_SEED_URLS:
        tok = probe_flow_seed(seed)
        if tok:
            g_cached_token = tok
            g_cached_time = now
            return tok
    return None


def extract_flow_path(url):
    m = PATH_PATTERN.search(url)
    if m:
        return m.group(1)
    m2 = PATH_PATTERN_ALT.search(url)
    if m2:
        return "live/" + m2.group(1)
    return ""


def is_flow(url):
    low = url.lower()
    return any(marker in low for marker in FLOW_MARKERS)


def load_channels_from_catalog():
    repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    catalog_path = os.path.join(
        repo_dir, "src/plugin/java/com/infomak/moai/ar/MoaiCatalog.java"
    )

    if not os.path.exists(catalog_path):
        raise FileNotFoundError(f"No se encontró {catalog_path}")

    with open(catalog_path, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = re.compile(
        r'\{\s*"([^"]+)",\s*"([^"]+)",\s*"([^"]*)",\s*"([^"]*)",\s*"([^"]*)",\s*"([^"]*)",\s*"([^"]+)",\s*"([^"]*)",\s*new String\[\]\s*\{([^}]*)\}\s*\}'
    )
    matches = pattern.findall(content)

    channels = []
    for m in matches:
        cid, name, logo, cat, pais, ctype, url, drm, raw_headers = m
        headers = {}
        # Parse headers: "Origin", "...", "Referer", "..."
        h_items = re.findall(r'"([^"]*)"', raw_headers)
        for i in range(0, len(h_items) - 1, 2):
            headers[h_items[i]] = h_items[i + 1]

        channels.append(
            {
                "id": cid,
                "nombre": name,
                "logo": logo,
                "categoria": cat,
                "pais": pais,
                "tipo": ctype,
                "url": url,
                "drm": drm,
                "headers": headers,
            }
        )
    return channels


def resolve_channel(channel):
    url = channel["url"]
    headers = dict(channel["headers"])
    headers.setdefault("User-Agent", DEFAULT_UA)

    if is_flow(url):
        tok = get_flow_token()
        if not tok:
            return None, headers, "Error: no se pudo obtener token Flow CDN"
        rel_path = extract_flow_path(url)
        url = f"https://{tok[0]}/{tok[1]}/{rel_path}"
        headers["Origin"] = "https://portal.app.flow.com.ar"
        headers["Referer"] = "https://portal.app.flow.com.ar/"

    return url, headers, None


def check_single_channel(channel, timeout=8):
    cid = channel["id"]
    name = channel["nombre"]
    cat = channel["categoria"]

    start = time.time()
    resolved_url, headers, err = resolve_channel(channel)
    if err:
        latency = round((time.time() - start) * 1000)
        return {
            "id": cid,
            "nombre": name,
            "categoria": cat,
            "status": "FAIL",
            "code": 0,
            "latency_ms": latency,
            "error": err,
            "url": resolved_url or channel["url"],
        }

    try:
        req = urllib.request.Request(resolved_url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = resp.status
            content_sample = resp.read(1024)
            latency = round((time.time() - start) * 1000)

            # Validar contenido de streaming
            is_valid_manifest = False
            text_sample = content_sample.decode("utf-8", errors="ignore")
            if "#EXTM3U" in text_sample:
                is_valid_manifest = True
            elif "<MPD" in text_sample or "urn:mpeg:dash" in text_sample:
                is_valid_manifest = True
            elif code == 200 and len(content_sample) > 0:
                is_valid_manifest = True

            if code == 200 and is_valid_manifest:
                return {
                    "id": cid,
                    "nombre": name,
                    "categoria": cat,
                    "status": "OK",
                    "code": code,
                    "latency_ms": latency,
                    "error": None,
                    "url": resolved_url,
                }
            else:
                return {
                    "id": cid,
                    "nombre": name,
                    "categoria": cat,
                    "status": "FAIL",
                    "code": code,
                    "latency_ms": latency,
                    "error": f"Contenido inesperado (tamaño: {len(content_sample)} bytes)",
                    "url": resolved_url,
                }
    except urllib.error.HTTPError as e:
        latency = round((time.time() - start) * 1000)
        return {
            "id": cid,
            "nombre": name,
            "categoria": cat,
            "status": "FAIL",
            "code": e.code,
            "latency_ms": latency,
            "error": f"HTTP {e.code}: {e.reason}",
            "url": resolved_url,
        }
    except urllib.error.URLError as e:
        latency = round((time.time() - start) * 1000)
        reason = str(e.reason)
        if "timed out" in reason.lower():
            reason = "Timeout (> " + str(timeout) + "s)"
        return {
            "id": cid,
            "nombre": name,
            "categoria": cat,
            "status": "FAIL",
            "code": 0,
            "latency_ms": latency,
            "error": reason,
            "url": resolved_url,
        }
    except Exception as e:
        latency = round((time.time() - start) * 1000)
        return {
            "id": cid,
            "nombre": name,
            "categoria": cat,
            "status": "FAIL",
            "code": 0,
            "latency_ms": latency,
            "error": str(e),
            "url": resolved_url,
        }


def main():
    parser = argparse.ArgumentParser(
        description="Analiza y verifica el estado en vivo de los canales de moaiplug_ar."
    )
    parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=20,
        help="Número de hilos concurrentes (default: 20)",
    )
    parser.add_argument(
        "--timeout",
        "-t",
        type=int,
        default=8,
        help="Timeout por canal en segundos (default: 8)",
    )
    parser.add_argument(
        "--limit", "-l", type=int, default=0, help="Limitar cantidad de canales a probar"
    )
    parser.add_argument(
        "--cat", "-c", type=str, default=None, help="Filtrar por categoría (ej: Noticias, Aire, Deportes)"
    )
    parser.add_argument(
        "--search", "-s", type=str, default=None, help="Buscar por nombre o ID de canal"
    )
    parser.add_argument(
        "--failed-only", action="store_true", help="Mostrar únicamente los canales caídos/fallidos"
    )
    parser.add_argument(
        "--output", "-o", type=str, default=None, help="Ruta de archivo JSON para exportar resultados"
    )

    args = parser.parse_args()

    channels = load_channels_from_catalog()
    total_in_plugin = len(channels)

    if args.cat:
        cat_lower = args.cat.lower()
        channels = [c for c in channels if cat_lower in c["categoria"].lower()]

    if args.search:
        s_lower = args.search.lower()
        channels = [
            c
            for c in channels
            if s_lower in c["nombre"].lower() or s_lower in c["id"].lower()
        ]

    if args.limit > 0:
        channels = channels[: args.limit]

    print("=" * 68)
    print("   🛰️  ANALIZADOR DE CANALES — MOAI ARGENTINA (moaiplug_ar)")
    print("=" * 68)
    print(f"Total en catálogo: {total_in_plugin} canales")
    print(f"A comprobar ahora: {len(channels)} canales")
    print(f"Hilos paralelos:   {args.workers} | Timeout: {args.timeout}s")
    print("-" * 68)

    # Pre-calentar token de Flow
    print("🔑 Obteniendo token inicial de Flow CDN...", end=" ", flush=True)
    tok = get_flow_token()
    if tok:
        print(f"OK ({tok[0]})")
    else:
        print("⚠️ Advertencia: No se pudo obtener token Flow previo.")
    print("-" * 68)

    results = []
    ok_count = 0
    fail_count = 0

    start_total = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_to_ch = {
            executor.submit(check_single_channel, ch, args.timeout): ch
            for ch in channels
        }

        idx = 0
        for future in concurrent.futures.as_completed(future_to_ch):
            idx += 1
            res = future.result()
            results.append(res)

            if res["status"] == "OK":
                ok_count += 1
                if not args.failed_only:
                    print(
                        f"[{idx:3d}/{len(channels):3d}] 🟢 OK   ({res['latency_ms']:4d}ms) | [{res['categoria'][:10]:10s}] {res['nombre']}"
                    )
            else:
                fail_count += 1
                code_str = f"HTTP {res['code']}" if res["code"] else "FAIL"
                print(
                    f"[{idx:3d}/{len(channels):3d}] 🔴 {code_str:8s} | [{res['categoria'][:10]:10s}] {res['nombre']} -> {res['error']}"
                )

    total_time = round(time.time() - start_total, 2)
    pct = round((ok_count / len(channels) * 100), 1) if channels else 0

    print("=" * 68)
    print("                     📊 RESUMEN FINAL")
    print("=" * 68)
    print(f" Canales analizados: {len(channels)}")
    print(f" 🟢 Operativos (OK):  {ok_count} ({pct}%)")
    print(f" 🔴 Caídos/Error:    {fail_count}")
    print(f" ⏱️  Tiempo total:    {total_time} segundos")
    print("=" * 68)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "total": len(channels),
                    "ok": ok_count,
                    "fail": fail_count,
                    "ok_percent": pct,
                    "duration_sec": total_time,
                    "channels": results,
                },
                f,
                indent=2,
                ensure_ascii=False,
            )
        print(f"💾 Reporte guardado en: {args.output}\n")


if __name__ == "__main__":
    main()
