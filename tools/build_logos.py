#!/usr/bin/env python3
"""Descarga los logos del catálogo y genera versiones para tema claro y oscuro.

Para cada canal del manifest.json:
  1. Baja el logo original (con caché en build/logo_cache/).
  2. Lo normaliza: si es una imagen opaca sobre un lienzo blanco o negro liso,
     quita ese lienzo; recorta y centra en un PNG cuadrado de SIZE px.
     Si el lienzo es de color (un "tile" de marca, p.ej. letras blancas sobre
     rojo) o una foto, lo deja entero con esquinas redondeadas.
  3. Mide el contraste del contorno del logo contra el fondo de cada tema:
       - tema oscuro: las partes negras/grises "expuestas" (las que tocan el
         fondo, no las que están dentro de un escudo de color) pasan a blanco.
       - tema claro: las partes blancas expuestas pasan a gris oscuro.
     Si recolorear no alcanza (p.ej. un logo azul marino en tema oscuro), le
     pone una placa redondeada detrás.
  4. Escribe assets/logos/{light,dark}/<id>.png y assets/logos/index.json.
  5. Con --apply-manifest agrega logoLight / logoDark al manifest.json
     (el campo "logo" no se toca: moai3 lo sigue usando tal cual).

Correcciones manuales en tools/data/logo_overrides.json, por id:
    {"<id>": {"source": "https://...",          # otro logo de origen
              "bg": "auto|remove|tile",          # qué hacer con el lienzo
              "light": "auto|keep|recolor|plate",
              "dark":  "auto|keep|recolor|plate"}}

Uso:
    py -3 tools/build_logos.py                    # procesa lo que cambió
    py -3 tools/build_logos.py --force            # reprocesa todo
    py -3 tools/build_logos.py --only telefe,tn   # solo esos ids
    py -3 tools/build_logos.py --apply-manifest   # además actualiza manifest.json

Además deja build/logos_preview.html para revisar todo sobre ambos fondos.
"""
import argparse
import concurrent.futures
import hashlib
import io
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from collections import deque
from urllib.parse import quote, urlsplit, urlunsplit

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "manifest.json")
OUT_DIR = os.path.join(ROOT, "assets", "logos")
INDEX = os.path.join(OUT_DIR, "index.json")
OVERRIDES = os.path.join(ROOT, "tools", "data", "logo_overrides.json")
CACHE = os.path.join(ROOT, "build", "logo_cache")
PREVIEW = os.path.join(ROOT, "build", "logos_preview.html")

RAW_BASE = ("https://raw.githubusercontent.com/dariomadeira/moaiplug_ar/"
            "refs/heads/main/assets/logos")

# Versión del algoritmo: subirla obliga a reprocesar todo.
ALGO_VERSION = 6
SIZE = 384          # lado del PNG final
CONTENT = 0.86      # fracción del lienzo que ocupa el logo
WORK_MAX = 480      # resolución de trabajo para el análisis

# Fondos de referencia de cada tema (los típicos de Material).
BG_DARK = (18, 18, 18)
BG_LIGHT = (245, 245, 245)
PLATE_FOR_DARK = (236, 236, 236)   # placa clara, para usar en tema oscuro
PLATE_FOR_LIGHT = (38, 38, 38)     # placa oscura, para usar en tema claro

BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36")
# Wikimedia devuelve 429 a UAs genéricos de navegador (ver check_logos.py).
WIKIMEDIA_UA = "moaiplug_ar-logos/1.0 (https://github.com/dariomadeira/moaiplug_ar)"
WIKIMEDIA_HOSTS = ("upload.wikimedia.org", "commons.wikimedia.org", "thumb.wikimedia.org")


# --------------------------------------------------------------------------
# Descarga
# --------------------------------------------------------------------------

def _percent_encode(url):
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc,
                       quote(parts.path, safe="/%:@&=+$,~()!*'"),
                       parts.query, parts.fragment))


def _ssl_context():
    """Contexto TLS verificado con un paquete de CA actualizado.

    El almacén de certificados de Windows puede traer cadenas vencidas (pasa
    con Let's Encrypt YE1/YR1): Python responde "certificate has expired" ante
    sitios válidos. Se prefiere, en orden: SSL_CERT_FILE, certifi, el bundle
    de Git for Windows y por último el del sistema. Siempre se verifica.
    """
    candidates = [os.environ.get("SSL_CERT_FILE")]
    try:
        import certifi
        candidates.append(certifi.where())
    except ImportError:
        pass
    for base in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                 os.environ.get("LOCALAPPDATA", "") + r"\Programs"):
        candidates.append(os.path.join(base, "Git", "mingw64", "etc", "ssl",
                                       "certs", "ca-bundle.crt"))
    for path in candidates:
        if path and os.path.exists(path):
            return ssl.create_default_context(cafile=path)
    return ssl.create_default_context()


def fetch(url, retries=2, timeout=20):
    """Devuelve los bytes del logo, usando la caché en disco."""
    os.makedirs(CACHE, exist_ok=True)
    key = hashlib.sha1(url.encode("utf-8")).hexdigest()
    path = os.path.join(CACHE, key + ".bin")
    if os.path.exists(path) and os.path.getsize(path) > 0:
        with open(path, "rb") as f:
            return f.read()
    probe = _percent_encode(url)
    ua = WIKIMEDIA_UA if any(h in probe for h in WIKIMEDIA_HOSTS) else BROWSER_UA
    last = None
    ctx = _ssl_context()
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(probe, headers={
                "User-Agent": ua, "Accept": "image/*,*/*;q=0.8"})
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
                data = r.read()
            if data.lstrip()[:64].lower().startswith((b"<!doctype", b"<html")):
                raise ValueError("el servidor devolvió HTML, no una imagen")
            with open(path, "wb") as f:
                f.write(data)
            return data
        except Exception as e:  # noqa: BLE001 — reportamos cualquier fallo
            last = e
            if isinstance(e, urllib.error.HTTPError) and e.code in (403, 404, 410):
                break
            if "CERTIFICATE_VERIFY_FAILED" in str(e):
                break  # certificado vencido/inválido: reintentar no sirve
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"descarga fallida: {last}")


# --------------------------------------------------------------------------
# Color
# --------------------------------------------------------------------------

def _lin(c):
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


_LIN = [_lin(float(i)) for i in range(256)]


def lum(r, g, b):
    """Luminancia relativa WCAG (0..1)."""
    return 0.2126 * _LIN[r] + 0.7152 * _LIN[g] + 0.0722 * _LIN[b]


def contrast(l1, l2):
    hi, lo = (l1, l2) if l1 > l2 else (l2, l1)
    return (hi + 0.05) / (lo + 0.05)


L_BG_DARK = lum(*BG_DARK)
L_BG_LIGHT = lum(*BG_LIGHT)


# --------------------------------------------------------------------------
# Procesamiento
# --------------------------------------------------------------------------

def load_image(data):
    img = Image.open(io.BytesIO(data))
    try:
        img.seek(0)  # GIF/WebP animado: primer cuadro
    except EOFError:
        pass
    if img.mode in ("P", "LA", "L", "1") and "transparency" in img.info:
        img = img.convert("RGBA")
    img = img.convert("RGBA")
    img.thumbnail((WORK_MAX, WORK_MAX), Image.LANCZOS)
    return img


def _border_indices(w, h):
    for x in range(w):
        yield x
        yield (h - 1) * w + x
    for y in range(1, h - 1):
        yield y * w
        yield y * w + w - 1


def remove_canvas(img, mode):
    """Quita el lienzo liso blanco/negro conectado al borde.

    Devuelve (imagen, kind) con kind en {"alpha", "removed", "tile"}.
    """
    w, h = img.size
    px = list(img.getdata())
    transparent = sum(1 for p in px if p[3] < 200)
    if transparent > 0.01 * len(px) and mode != "remove":
        return img, "alpha"
    if mode == "tile":
        return img, "tile"

    border = [px[i] for i in _border_indices(w, h)]
    # Color dominante del borde (cuantizado a 16 niveles por canal).
    buckets = {}
    for r, g, b, _ in border:
        k = (r >> 4, g >> 4, b >> 4)
        buckets[k] = buckets.get(k, 0) + 1
    (qr, qg, qb), n = max(buckets.items(), key=lambda kv: kv[1])
    ref = [p for p in border if (p[0] >> 4, p[1] >> 4, p[2] >> 4) == (qr, qg, qb)]
    br = sum(p[0] for p in ref) // len(ref)
    bgc = sum(p[1] for p in ref) // len(ref)
    bb = sum(p[2] for p in ref) // len(ref)

    def dist(p):
        return max(abs(p[0] - br), abs(p[1] - bgc), abs(p[2] - bb))

    uniform = sum(1 for p in border if dist(p) <= 40) / len(border)
    chroma = max(br, bgc, bb) - min(br, bgc, bb)
    l_bg = lum(br, bgc, bb)
    achromatic_canvas = chroma < 24 and (l_bg > 0.75 or l_bg < 0.02)
    if mode != "remove" and (uniform < 0.85 or not achromatic_canvas):
        return img, "tile"
    # Una foto sobre fondo negro (p.ej. un banner) no es un logo sobre un
    # lienzo: tiene cientos de colores distintos. Esos quedan como tile.
    colors = {(p[0] >> 4, p[1] >> 4, p[2] >> 4) for p in px
              if max(abs(p[0] - br), abs(p[1] - bgc), abs(p[2] - bb)) > 40}
    if mode != "remove" and len(colors) > 700:
        return img, "tile"

    # Flood fill desde el borde: lo que se parece al lienzo pasa a transparente;
    # la franja de transición queda semitransparente (antialias).
    HARD, SOFT = 36, 96
    alpha = [p[3] for p in px]
    seen = bytearray(len(px))
    q = deque()
    for i in _border_indices(w, h):
        if dist(px[i]) <= HARD and not seen[i]:
            seen[i] = 1
            q.append(i)
    removed = 0
    while q:
        i = q.popleft()
        alpha[i] = 0
        removed += 1
        x, y = i % w, i // w
        for j in ((i - 1) if x > 0 else -1, (i + 1) if x < w - 1 else -1,
                  (i - w) if y > 0 else -1, (i + w) if y < h - 1 else -1):
            if j < 0 or seen[j]:
                continue
            d = dist(px[j])
            if d <= HARD:
                seen[j] = 1
                q.append(j)
            elif d < SOFT:
                seen[j] = 1
                alpha[j] = min(alpha[j], int(255 * (d - HARD) / (SOFT - HARD)))
    if removed > 0.97 * len(px):
        return img, "tile"  # se iba todo: no era un lienzo
    out = Image.new("RGBA", (w, h))
    out.putdata([(p[0], p[1], p[2], a) for p, a in zip(px, alpha)])
    return out, "removed"


def trim(img):
    bbox = img.getchannel("A").point(lambda a: 255 if a > 20 else 0).getbbox()
    return img.crop(bbox) if bbox else img


def edge_stats(px, w, h, l_bg, threshold):
    """Fracción del contorno visible con poco contraste contra l_bg."""
    poor = total = 0
    for i, p in enumerate(px):
        if p[3] < 128:
            continue
        x, y = i % w, i // w
        edge = (x == 0 or y == 0 or x == w - 1 or y == h - 1
                or px[i - 1][3] < 128 or px[i + 1][3] < 128
                or px[i - w][3] < 128 or px[i + w][3] < 128)
        if not edge:
            continue
        total += 1
        if contrast(lum(p[0], p[1], p[2]), l_bg) < threshold:
            poor += 1
    return (poor / total) if total else 0.0, total


def exposed(px, w, h, pred):
    """Índices de píxeles que cumplen pred y están conectados al fondo.

    Las letras negras de un logo tocan el fondo y quedan marcadas; las letras
    negras dentro de un escudo amarillo no, y se respetan.

    Se analiza cada zona conectada por separado: si es una forma sólida y
    grande (un círculo o recuadro negro con texto blanco adentro) es el fondo
    de una insignia y no se toca, porque recolorearla borraría el texto.
    Los píxeles semitransparentes (antialias) se corrigen pero no propagan,
    para que el recoloreado no se "filtre" hacia adentro por un borde suave.
    """
    n = len(px)
    visible = sum(1 for p in px if p[3] >= 128) or 1
    seen = bytearray(n)
    out = []

    def is_edge(i):
        x, y = i % w, i // w
        return (x == 0 or y == 0 or x == w - 1 or y == h - 1
                or px[i - 1][3] < 128 or px[i + 1][3] < 128
                or px[i - w][3] < 128 or px[i + w][3] < 128)

    for s in range(n):
        p = px[s]
        if seen[s] or p[3] == 0 or not pred(p):
            continue
        if p[3] < 128:
            seen[s] = 1
            out.append(s)          # antialias: se corrige, no propaga
            continue
        if not is_edge(s):
            continue
        comp = []
        q = deque([s])
        seen[s] = 1
        x0 = y0 = 1 << 30
        x1 = y1 = -1
        while q:
            i = q.popleft()
            comp.append(i)
            x, y = i % w, i // w
            x0, x1, y0, y1 = min(x0, x), max(x1, x), min(y0, y), max(y1, y)
            for j in ((i - 1) if x > 0 else -1, (i + 1) if x < w - 1 else -1,
                      (i - w) if y > 0 else -1, (i + w) if y < h - 1 else -1):
                if j >= 0 and not seen[j] and px[j][3] >= 128 and pred(px[j]):
                    seen[j] = 1
                    q.append(j)
        if len(comp) > 0.02 * visible:
            # ¿Hay contenido visible de otro color dentro de su caja? Si sí,
            # es el fondo de una insignia (círculo negro con "SC" blanco).
            # Letras gruesas sin nada adentro (FX, HBO) se recolorean igual.
            mark = set(comp)
            inner = 0
            for yy in range(y0, y1 + 1):
                row = yy * w
                for xx in range(x0, x1 + 1):
                    k = row + xx
                    if k not in mark and px[k][3] >= 128 and not pred(px[k]):
                        inner += 1
            if inner > 0.08 * len(comp):
                continue  # fondo de insignia: no se toca
        out.extend(comp)
    return out


def _chroma(p):
    return max(p[0], p[1], p[2]) - min(p[0], p[1], p[2])


def is_dark_poor(p):
    """Para tema oscuro: grises oscuros, y cualquier color que casi no se
    distinga del fondo negro (azul marino, bordó, violeta muy oscuro)."""
    l = lum(p[0], p[1], p[2])
    return (_chroma(p) < 48 and l < 0.20) or contrast(l, L_BG_DARK) < 2.0


def is_dark_poor_forced(p):
    """Como is_dark_poor pero más amplio, para cuando se pide "recolor" a
    mano: también aclara azules o rojos medios (p.ej. El País)."""
    l = lum(p[0], p[1], p[2])
    return (_chroma(p) < 48 and l < 0.20) or contrast(l, L_BG_DARK) < 3.0


def is_light_neutral(p):
    """Para tema claro: solo blancos y grises claros. Los colores claros
    (amarillo, celeste) se dejan: son parte de la marca y se reconocen."""
    return _chroma(p) < 32 and lum(p[0], p[1], p[2]) > 0.70


def _lighten(r, g, b, target=3.0):
    """Aclara un color oscuro conservando el tono hasta tener contraste
    `target` contra el fondo oscuro."""
    import colorsys
    hh, ll, ss = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    while ll < 0.95:
        ll = min(0.95, ll + 0.04)
        nr, ng, nb = (int(round(c * 255)) for c in colorsys.hls_to_rgb(hh, ll, ss))
        if contrast(lum(nr, ng, nb), L_BG_DARK) >= target:
            return nr, ng, nb
    return nr, ng, nb


def recolor(img, pred, to_light):
    """Corrige los píxeles expuestos con poco contraste (mantiene el alfa).

    Grises: se invierte la luminosidad (negro -> casi blanco y al revés).
    Colores oscuros (solo tema oscuro): se aclaran conservando el tono.
    """
    w, h = img.size
    px = list(img.getdata())
    idx = exposed(px, w, h, pred)
    for i in idx:
        r, g, b, a = px[i]
        if to_light and _chroma(px[i]) >= 48:
            px[i] = _lighten(r, g, b) + (a,)
            continue
        v = (r + g + b) // 3
        nv = 255 - v
        # Un negro puro queda en casi-blanco y un blanco en casi-negro, no en
        # los extremos, para que no "queme" sobre el fondo.
        nv = max(nv, 200) if to_light else min(nv, 40)
        px[i] = (nv, nv, nv, a)
    out = Image.new("RGBA", (w, h))
    out.putdata(px)
    visible = sum(1 for p in px if p[3] >= 128) or 1
    return out, len(idx) / visible


def variant(img, theme, mode):
    """Devuelve (imagen, acción) para un tema."""
    w, h = img.size
    px = list(img.getdata())
    # thr: contraste mínimo del contorno para no tocar nada.
    # severe: por debajo de esto el logo casi desaparece -> placa.
    # El amarillo o el naranja sobre blanco tienen poco contraste "WCAG" pero
    # se reconocen bien: por eso la placa usa un umbral mucho más bajo.
    if theme == "dark":
        l_bg, thr, severe, pred, to_light = L_BG_DARK, 1.9, 1.35, is_dark_poor, True
    else:
        l_bg, thr, severe, pred, to_light = L_BG_LIGHT, 1.5, 1.2, is_light_neutral, False

    if mode == "keep":
        return img, "keep"
    if mode == "plate":
        return img, "plate"
    poor, _ = edge_stats(px, w, h, l_bg, thr)
    # Umbral bajo: un texto chico invisible es poco contorno frente a un
    # isotipo grande, pero igual hay que corregirlo. Recolorear solo toca lo
    # que no se ve, así que es seguro dispararlo seguido.
    if mode == "auto" and poor < 0.06:
        return img, "keep"
    if mode == "recolor":
        forced = is_dark_poor_forced if theme == "dark" else pred
        return recolor(img, forced, to_light)[0], "recolor"
    rec, share = recolor(img, pred, to_light)
    best, action = (rec, "recolor") if share > 0.02 else (img, "keep")
    # La placa se decide por ÁREA, no por contorno: un reborde blanco
    # alrededor de una insignia de color se pierde sobre fondo claro, pero la
    # insignia se sigue viendo. Placa solo si casi todo el logo desaparece.
    if area_poor(list(best.getdata()), l_bg, severe) < 0.55:
        return best, action
    return img, "plate"


def area_poor(px, l_bg, threshold):
    """Fracción del área visible con contraste menor a threshold contra l_bg."""
    poor = total = 0
    for p in px:
        if p[3] < 128:
            continue
        total += 1
        if contrast(lum(p[0], p[1], p[2]), l_bg) < threshold:
            poor += 1
    return poor / total if total else 0.0


def compose(img, action, theme, kind):
    """Centra el logo en el lienzo final (con placa o tile si corresponde)."""
    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    box = int(SIZE * CONTENT)
    w, h = img.size
    if kind == "tile":
        scale = box / max(w, h)
        nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
        logo = img.resize((nw, nh), Image.LANCZOS)
        mask = Image.new("L", (nw, nh), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            (0, 0, nw - 1, nh - 1), radius=int(min(nw, nh) * 0.12), fill=255)
        logo.putalpha(mask)
        canvas.alpha_composite(logo, ((SIZE - nw) // 2, (SIZE - nh) // 2))
        return canvas
    if action == "plate":
        inner = int(box * 0.82)  # deja aire dentro de la placa
        scale = inner / max(w, h)
        nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
        pad = int(box * 0.09)
        pw, ph = nw + 2 * pad, nh + 2 * pad
        x0, y0 = (SIZE - pw) // 2, (SIZE - ph) // 2
        fill = PLATE_FOR_DARK if theme == "dark" else PLATE_FOR_LIGHT
        ImageDraw.Draw(canvas).rounded_rectangle(
            (x0, y0, x0 + pw - 1, y0 + ph - 1),
            radius=int(min(pw, ph) * 0.22), fill=fill + (255,))
        logo = img.resize((nw, nh), Image.LANCZOS)
        canvas.alpha_composite(logo, (x0 + pad, y0 + pad))
        return canvas
    scale = box / max(w, h)
    nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
    logo = img.resize((nw, nh), Image.LANCZOS)
    canvas.alpha_composite(logo, ((SIZE - nw) // 2, (SIZE - nh) // 2))
    return canvas


def png_bytes(img):
    """PNG optimizado: paleta de 256 colores con alfa si no se nota la
    diferencia (logos planos), RGBA completo si no (fotos, degradés)."""
    full = io.BytesIO()
    img.save(full, "PNG", optimize=True)
    pal = img.quantize(256, method=Image.Quantize.FASTOCTREE,
                       dither=Image.Dither.NONE)
    back = pal.convert("RGBA")
    a, b = img.getdata(), back.getdata()
    err = sum(abs(p[0] - q[0]) + abs(p[1] - q[1]) + abs(p[2] - q[2])
              + abs(p[3] - q[3]) for p, q in zip(a, b) if p[3] or q[3])
    vis = sum(1 for p in a if p[3]) or 1
    if err / vis > 6:   # error medio por píxel visible: se notaría
        return full.getvalue()
    small = io.BytesIO()
    pal.save(small, "PNG", optimize=True)
    return min(small.getvalue(), full.getvalue(), key=len)


def process(data, ov):
    img = load_image(data)
    img, kind = remove_canvas(img, ov.get("bg", "auto"))
    img = trim(img)
    result = {"kind": kind}
    outputs = {}
    for theme in ("light", "dark"):
        if kind == "tile":
            v, action = img, "tile"
        else:
            v, action = variant(img, theme, ov.get(theme, "auto"))
        outputs[theme] = png_bytes(compose(v, action, theme, kind))
        result[theme] = action
    return result, outputs


# --------------------------------------------------------------------------
# Orquestación
# --------------------------------------------------------------------------

def _load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_file(path, data, tries=5):
    """Escritura atómica con reintentos: en Windows el antivirus, el indexador
    o un navegador con la vista previa abierta bloquean archivos un instante."""
    if os.path.exists(path):
        with open(path, "rb") as f:
            if f.read() == data:
                return
    tmp = path + ".tmp"
    for attempt in range(tries):
        try:
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, path)
            return
        except OSError:
            if attempt == tries - 1:
                raise
            time.sleep(0.5 * (attempt + 1))


def _job(args):
    cid, source, ov = args
    try:
        data = fetch(source)
        info, outputs = process(data, ov)
        info["source_sha1"] = hashlib.sha1(data).hexdigest()
        return cid, info, outputs, None
    except Exception as e:  # noqa: BLE001
        return cid, None, None, f"{type(e).__name__}: {e}"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--apply-manifest", action="store_true")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 4)
    args = ap.parse_args()

    manifest = _load_json(MANIFEST, None)
    overrides = {k: v for k, v in _load_json(OVERRIDES, {}).items()
                 if not k.startswith("_")}
    index = _load_json(INDEX, {})
    only = {s.strip() for s in args.only.split(",") if s.strip()}

    jobs = []
    for c in manifest["canales"]:
        cid = c["id"]
        if only and cid not in only:
            continue
        ov = overrides.get(cid, {})
        source = ov.get("source") or c.get("logo") or ""
        if not source:
            index.pop(cid, None)
            continue
        prev = index.get(cid)
        sig = {"source": source, "algo": ALGO_VERSION,
               "ov": {k: v for k, v in ov.items() if k != "source"}}
        if (not args.force and prev and prev.get("sig") == sig
                and all(os.path.exists(os.path.join(OUT_DIR, t, cid + ".png"))
                        for t in ("light", "dark"))):
            continue
        jobs.append((cid, source, ov, sig))

    print(f">> {len(jobs)} logos para procesar ({args.workers} procesos)")
    for t in ("light", "dark"):
        os.makedirs(os.path.join(OUT_DIR, t), exist_ok=True)

    errors = {}
    done = 0
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as ex:
        sigs = {cid: sig for cid, _, _, sig in jobs}
        for cid, info, outputs, err in ex.map(
                _job, [(c, s, o) for c, s, o, _ in jobs], chunksize=2):
            done += 1
            if err:
                errors[cid] = err
                index[cid] = {"sig": sigs[cid], "error": err}
                print(f"   [{done}/{len(jobs)}] {cid}: ERROR {err}")
                continue
            for theme, data in outputs.items():
                write_file(os.path.join(OUT_DIR, theme, cid + ".png"), data)
                info[theme + "_sha1"] = hashlib.sha1(data).hexdigest()
            info["sig"] = sigs[cid]
            index[cid] = info
            print(f"   [{done}/{len(jobs)}] {cid}: {info['kind']} "
                  f"light={info['light']} dark={info['dark']}")

    # Borra PNGs de canales que ya no están en el catálogo.
    ids = {c["id"] for c in manifest["canales"]}
    for t in ("light", "dark"):
        for name in os.listdir(os.path.join(OUT_DIR, t)):
            if name.endswith(".png") and name[:-4] not in ids:
                os.remove(os.path.join(OUT_DIR, t, name))
    index = {k: index[k] for k in sorted(index) if k in ids}
    with open(INDEX, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=1, sort_keys=True)

    if args.apply_manifest:
        apply_manifest(manifest, index)
    write_preview(manifest, index)

    ok = sum(1 for v in index.values() if "error" not in v)
    print(f">> logos OK: {ok}, con error: {sum(1 for v in index.values() if 'error' in v)}")
    print(f">> vista previa: {PREVIEW}")
    return 0


def theme_urls(cid, info):
    """URLs de manifest para un canal, o None si no hay versión generada."""
    if not info or "error" in info:
        return None
    return {
        "logoLight": f"{RAW_BASE}/light/{cid}.png?v={info['light_sha1'][:8]}",
        "logoDark": f"{RAW_BASE}/dark/{cid}.png?v={info['dark_sha1'][:8]}",
    }


def apply_manifest(manifest, index):
    canales = []
    for c in manifest["canales"]:
        out = {}
        for k, v in c.items():
            if k in ("logoLight", "logoDark"):
                continue
            out[k] = v
            if k == "logo":
                urls = theme_urls(c["id"], index.get(c["id"]))
                # Sin versión generada: ambos temas usan el logo original.
                out["logoLight"] = urls["logoLight"] if urls else c["logo"]
                out["logoDark"] = urls["logoDark"] if urls else c["logo"]
        canales.append(out)
    manifest["canales"] = canales
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f">> manifest.json actualizado con logoLight/logoDark")


def write_preview(manifest, index):
    from html import escape
    rows = []
    for c in manifest["canales"]:
        cid = c["id"]
        info = index.get(cid) or {}
        if not c.get("logo") and cid not in index:
            status = "sin logo"
        elif "error" in info:
            status = "error: " + info["error"]
        else:
            status = f"{info.get('kind')} · claro: {info.get('light')} · oscuro: {info.get('dark')}"
        src = escape(c.get("logo") or "")
        lp = f"../assets/logos/light/{cid}.png"
        dp = f"../assets/logos/dark/{cid}.png"
        ok = info and "error" not in info
        rows.append(f"""<div class="card" data-k="{escape(info.get('kind',''))} {escape(info.get('light',''))} {escape(info.get('dark',''))}{' err' if not ok else ''}">
<div class="name"><b>{escape(c['nombre'])}</b> <code>{cid}</code></div>
<div class="cells">
<div class="cell light"><img src="{src}" loading="lazy" alt=""><span>original</span></div>
<div class="cell dark"><img src="{src}" loading="lazy" alt=""><span>original</span></div>
<div class="cell light">{'<img src="%s" loading="lazy" alt="">' % lp if ok else ''}<span>claro</span></div>
<div class="cell dark">{'<img src="%s" loading="lazy" alt="">' % dp if ok else ''}<span>oscuro</span></div>
</div><div class="st">{escape(status)}</div></div>""")
    html = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Logos claro/oscuro</title><style>
body{font:14px system-ui,sans-serif;margin:16px;background:#ddd;color:#111}
.bar{position:sticky;top:0;background:#ddd;padding:8px 0;z-index:1}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:12px}
.card{background:#fff;border-radius:10px;padding:10px}
.cells{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin:6px 0}
.cell{aspect-ratio:1;border-radius:8px;display:flex;flex-direction:column;align-items:center;justify-content:center;position:relative}
.cell img{max-width:80%;max-height:70%}
.cell span{position:absolute;bottom:3px;font-size:10px;opacity:.6}
.light{background:#f5f5f5;color:#111}.dark{background:#121212;color:#eee}
.st{font-size:12px;color:#555}code{font-size:11px;color:#666}
</style></head><body><div class="bar">Filtro: <input id="f" placeholder="recolor, plate, tile, err…">
 <span id="n"></span></div><div class="grid">""" + "\n".join(rows) + """</div>
<script>
const f=document.getElementById('f'),n=document.getElementById('n'),cs=[...document.querySelectorAll('.card')];
function go(){const q=f.value.trim().toLowerCase();let k=0;for(const c of cs){const v=!q||c.dataset.k.includes(q)||c.textContent.toLowerCase().includes(q);c.style.display=v?'':'none';k+=v}n.textContent=k+' canales'}
f.oninput=go;go();</script></body></html>"""
    os.makedirs(os.path.dirname(PREVIEW), exist_ok=True)
    with open(PREVIEW, "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    sys.exit(main())
