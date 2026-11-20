#!/usr/bin/env python3
"""Busca mejores versiones de logos en tv-logos y Wikimedia Commons.

Para cada id pedido junta candidatos de:
  - tv-logo/tv-logos (GitHub): PNG transparentes en alta resolución. Se
    compara el nombre del canal con el nombre de archivo, priorizando la
    carpeta del país del canal.
  - Wikimedia Commons: búsqueda de archivos "<nombre> logo".

No cambia nada del catálogo: escribe build/logo_candidates.json y
build/logo_candidates.html, una página para elegir a mano el mejor de cada
canal. La página arma el JSON para pegar en tools/data/logo_overrides.json.

Uso:
    py -3 tools/find_logo_candidates.py --ids-file build/logos_a_mejorar.txt
    py -3 tools/find_logo_candidates.py --ids telefe,tn
"""
import argparse
import concurrent.futures
import difflib
import json
import os
import re
import ssl
import subprocess
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from build_logos import _ssl_context  # noqa: E402  (mismo bundle de CA)

MANIFEST = os.path.join(ROOT, "manifest.json")
INDEX = os.path.join(ROOT, "assets", "logos", "index.json")
TREE_CACHE = os.path.join(ROOT, "build", "tvlogos_tree.json")
OUT_JSON = os.path.join(ROOT, "build", "logo_candidates.json")
OUT_HTML = os.path.join(ROOT, "build", "logo_candidates.html")

TV_RAW = "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/"
UA = "moaiplug_ar-logos/1.0 (https://github.com/dariomadeira/moaiplug_ar)"

# Carpetas de tv-logos que se miran según el país del canal (en orden).
COUNTRY_DIRS = {
    "Argentina": ["argentina", "world-latin-america"],
    "Paraguay": ["paraguay", "world-latin-america"],
    "Uruguay": ["uruguay", "world-latin-america"],
    "Bolivia": ["bolivia", "world-latin-america"],
    "Brasil": ["brazil"],
    "Canadá": ["canada", "united-states"],
    "Internacional": ["world-latin-america", "international", "united-states",
                      "united-kingdom", "spain", "world-europe"],
}
# Sufijos de calidad o de estado que vienen en los nombres del catálogo.
NOISE = {"hd", "fhd", "uhd", "sd", "4k", "720p", "1080p", "480p", "360p",
         "240p", "not", "24", "7", "tv", "canal", "la", "el", "de", "del",
         "the", "y", "and", "latin", "america", "latinoamerica", "south",
         "sur", "ar", "arg", "lam", "logo", "live", "en", "vivo"}
ALL_STOP = NOISE | {"channel"}


def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = s.lower().replace("&", " and ").replace("+", " plus ")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def tokens(s, drop=NOISE):
    return [t for t in norm(s).split() if t not in drop]


# --------------------------------------------------------------------------
# tv-logos
# --------------------------------------------------------------------------

def load_tree(refresh=False):
    if not refresh and os.path.exists(TREE_CACHE):
        with open(TREE_CACHE, encoding="utf-8") as f:
            return json.load(f)
    # El árbol recursivo del repo es enorme: se baja solo la carpeta de cada
    # país que usamos (un tree no recursivo por carpeta).
    def gh_tree(ref):
        raw = subprocess.run(
            ["gh", "api", f"repos/tv-logo/tv-logos/git/trees/{ref}"],
            check=True, capture_output=True, timeout=120).stdout
        return json.loads(raw)["tree"]

    print(">> bajando listado de tv-logos (gh api)…")
    wanted = {d for dirs in COUNTRY_DIRS.values() for d in dirs}
    root = {x["path"]: x["sha"] for x in gh_tree("main")}
    countries = {x["path"]: x["sha"] for x in gh_tree(root["countries"])
                 if x["type"] == "tree"}
    paths = []
    for d in sorted(wanted & set(countries)):
        stack = [(f"countries/{d}", countries[d])]
        while stack:
            prefix, sha = stack.pop()
            for x in gh_tree(sha):
                p = f"{prefix}/{x['path']}"
                if x["type"] == "tree":
                    stack.append((p, x["sha"]))
                elif p.lower().endswith(".png"):
                    paths.append(p)
        print(f"   {d}: {sum(1 for p in paths if p.startswith('countries/' + d + '/'))}")
    os.makedirs(os.path.dirname(TREE_CACHE), exist_ok=True)
    with open(TREE_CACHE, "w", encoding="utf-8") as f:
        json.dump(paths, f)
    return paths


def index_tree(paths):
    """{carpeta_país: [(path, tokens_del_archivo, nombre_normalizado)]}"""
    by_dir = {}
    for p in paths:
        parts = p.split("/")
        if len(parts) < 3 or parts[0] != "countries":
            continue
        country = parts[1]
        stem = os.path.splitext(parts[-1])[0]
        # Quita el sufijo de país: "telefe-ar" -> "telefe".
        stem = re.sub(r"-(ar|lam|py|uy|bo|br|us|uk|ca|es|int|eu|mx|cl|co|pe)$",
                      "", stem)
        variant = ""
        m = re.search(r"-(white|black|dark|light|alt|color|mono|hz|vertical)\b",
                      stem)
        if m:
            variant = m.group(1)
        toks = tokens(stem.replace("-", " "))
        by_dir.setdefault(country, []).append((p, toks, " ".join(toks), variant))
    return by_dir


def score(name_toks, file_toks):
    if not name_toks or not file_toks:
        return 0.0
    a, b = set(name_toks), set(file_toks)
    jac = len(a & b) / len(a | b)
    seq = difflib.SequenceMatcher(None, " ".join(name_toks),
                                  " ".join(file_toks)).ratio()
    # Los números (canal 7, 13, 9) tienen que coincidir.
    na = {t for t in a if t.isdigit()}
    nb = {t for t in b if t.isdigit()}
    if na != nb and (na or nb):
        return min(jac, seq) * 0.4
    return 0.55 * jac + 0.45 * seq


def tvlogos_candidates(channel, by_dir, limit=3):
    name_toks = tokens(channel["nombre"]) or tokens(channel["id"].replace("_", " "))
    id_toks = tokens(channel["id"].replace("_", " "))
    dirs = COUNTRY_DIRS.get(channel.get("pais"), ["world-latin-america"])
    found = []
    for rank, d in enumerate(dirs):
        for path, ftoks, _, variant in by_dir.get(d, []):
            s = max(score(name_toks, ftoks), score(id_toks, ftoks))
            s -= 0.04 * rank          # prefiere la carpeta del país
            if variant in ("white", "dark", "black", "mono"):
                s -= 0.03             # versiones monocromo: menos preferidas
            if s >= 0.55:
                found.append((s, path))
    found.sort(reverse=True)
    out, seen = [], set()
    for s, path in found:
        if path in seen:
            continue
        seen.add(path)
        out.append({"source": "tv-logos", "url": TV_RAW + urllib.parse.quote(path),
                    "title": path.split("/", 1)[1], "score": round(s, 3)})
        if len(out) >= limit:
            break
    return out


# --------------------------------------------------------------------------
# Wikimedia Commons
# --------------------------------------------------------------------------

def _get_json(url, ctx, tries=3):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=25, context=ctx) as r:
                return json.load(r)
        except Exception:  # noqa: BLE001
            if attempt == tries - 1:
                raise
            time.sleep(2 * (attempt + 1))


def commons_candidates(channel, ctx, limit=3):
    name = re.sub(r"\b(\d{3,4}p|not 24/7|not_24_7|HD|FHD)\b", "",
                  channel["nombre"], flags=re.I).strip(" *-")
    q = f'{name} logo'
    params = {
        "action": "query", "format": "json", "generator": "search",
        "gsrnamespace": 6, "gsrsearch": q, "gsrlimit": 8,
        "prop": "imageinfo", "iiprop": "url|size|mime", "iiurlwidth": 600,
    }
    data = _get_json("https://commons.wikimedia.org/w/api.php?"
                     + urllib.parse.urlencode(params), ctx)
    pages = sorted((data.get("query") or {}).get("pages", {}).values(),
                   key=lambda p: p.get("index", 99))
    name_toks = tokens(name, ALL_STOP)
    out = []
    for p in pages:
        ii = (p.get("imageinfo") or [{}])[0]
        if ii.get("mime") not in ("image/png", "image/svg+xml", "image/webp"):
            continue  # JPG: casi siempre fotos, no logos
        title = p["title"].split(":", 1)[-1]
        t_toks = tokens(os.path.splitext(title)[0], ALL_STOP)
        s = score(name_toks, t_toks)
        if s < 0.35:
            continue
        # thumburl sirve PNG aunque el original sea SVG (moai3 no lee SVG).
        url = ii.get("thumburl") or ii.get("url")
        out.append({"source": "commons", "url": url, "title": title,
                    "score": round(s, 3),
                    "size": f"{ii.get('width')}×{ii.get('height')}"})
        if len(out) >= limit:
            break
    return out


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ids", default="")
    ap.add_argument("--ids-file", default="")
    ap.add_argument("--refresh-tree", action="store_true")
    ap.add_argument("--no-commons", action="store_true")
    args = ap.parse_args()

    ids = [s.strip() for s in args.ids.split(",") if s.strip()]
    if args.ids_file:
        with open(args.ids_file, encoding="utf-8") as f:
            ids += [l.strip() for l in f if l.strip()]
    with open(MANIFEST, encoding="utf-8") as f:
        channels = {c["id"]: c for c in json.load(f)["canales"]}
    index = {}
    if os.path.exists(INDEX):
        with open(INDEX, encoding="utf-8") as f:
            index = json.load(f)
    missing = [i for i in ids if i not in channels]
    if missing:
        print("AVISO: ids que no están en el manifest:", ", ".join(missing))
    ids = [i for i in ids if i in channels]

    by_dir = index_tree(load_tree(args.refresh_tree))
    ctx = _ssl_context()

    def work(cid):
        c = channels[cid]
        cands = tvlogos_candidates(c, by_dir)
        if not args.no_commons:
            try:
                cands += commons_candidates(c, ctx)
            except Exception as e:  # noqa: BLE001
                print(f"   {cid}: commons falló ({e})")
        current = (index.get(cid) or {}).get("sig", {}).get("source") or c["logo"]
        cands = [x for x in cands if x["url"] != current]
        return cid, {"nombre": c["nombre"], "pais": c.get("pais"),
                     "actual": current, "candidatos": cands}

    result = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        for n, (cid, r) in enumerate(ex.map(work, ids), 1):
            result[cid] = r
            print(f"   [{n}/{len(ids)}] {cid}: {len(r['candidatos'])} candidatos")

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    write_html(result)
    con = sum(1 for r in result.values() if r["candidatos"])
    print(f">> {con}/{len(result)} canales con al menos un candidato")
    print(f">> elegir en: {OUT_HTML}")


def write_html(result):
    from html import escape
    cards = []
    for cid, r in result.items():
        opts = [f'''<label class="opt"><input type="radio" name="{cid}" value="" checked>
<div class="imgs"><div class="bg l"><img src="../assets/logos/light/{cid}.png" alt="" onerror="this.src='{escape(r['actual'])}'"></div>
<div class="bg d"><img src="../assets/logos/dark/{cid}.png" alt="" onerror="this.src='{escape(r['actual'])}'"></div></div>
<span>actual</span></label>''']
        for c in r["candidatos"]:
            meta = escape(f"{c['source']} · {c['title']}" + (f" · {c['size']}" if c.get("size") else ""))
            opts.append(f'''<label class="opt"><input type="radio" name="{cid}" value="{escape(c['url'])}">
<div class="imgs"><div class="bg l"><img loading="lazy" src="{escape(c['url'])}" alt=""></div>
<div class="bg d"><img loading="lazy" src="{escape(c['url'])}" alt=""></div></div>
<span title="{meta}">{meta}</span></label>''')
        q = urllib.parse.quote(f'{r["nombre"]} logo png')
        cards.append(f'''<section class="card" data-id="{cid}">
<header><b>{escape(r["nombre"])}</b> <code>{cid}</code> <small>{escape(r.get("pais") or "")}</small>
<a href="https://www.google.com/search?tbm=isch&q={q}" target="_blank" rel="noopener">buscar en Google</a></header>
<div class="opts">{"".join(opts)}
<label class="opt man"><input type="radio" name="{cid}" value="__manual__"><input class="url" placeholder="pegar otra URL…"><span>otra URL</span></label>
</div></section>''')
    html = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Elegir logos</title>
<style>
:root{--bg:#e9e9ec;--card:#fff;--ink:#16161a;--mute:#66666e;--acc:#2f6fed}
body{margin:0;font:14px system-ui,sans-serif;background:var(--bg);color:var(--ink)}
.top{position:sticky;top:0;z-index:2;background:var(--ink);color:#fff;padding:10px 16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.top button{background:var(--acc);color:#fff;border:0;border-radius:6px;padding:8px 14px;font-weight:600;cursor:pointer}
main{padding:16px;display:grid;gap:12px}
.card{background:var(--card);border-radius:10px;padding:10px 12px}
.card header{display:flex;gap:8px;align-items:baseline;flex-wrap:wrap;margin-bottom:8px}
.card header a{margin-left:auto;font-size:12px;color:var(--acc)}
code,small{color:var(--mute);font-size:12px}
.opts{display:flex;gap:10px;overflow-x:auto;padding-bottom:4px}
.opt{flex:0 0 190px;border:2px solid transparent;border-radius:8px;padding:6px;cursor:pointer;display:flex;flex-direction:column;gap:4px}
.opt:has(input:checked){border-color:var(--acc);background:#eef3fe}
.opt>input[type=radio]{position:absolute;opacity:0}
.imgs{display:grid;grid-template-columns:1fr 1fr;gap:4px}
.bg{aspect-ratio:1;border-radius:6px;display:flex;align-items:center;justify-content:center}
.bg img{max-width:86%;max-height:86%}
.l{background:#f5f5f5}.d{background:#121212}
.opt span{font-size:11px;color:var(--mute);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.man{justify-content:center}.man .url{width:100%;box-sizing:border-box;padding:6px;border:1px solid #ccc;border-radius:6px}
textarea{width:100%;height:160px;font:12px monospace}
.out{display:none;padding:0 16px 16px}.out.on{display:block}
</style></head><body>
<div class="top"><b>Elegir logos</b><span id="cnt"></span><button id="gen">Generar JSON de overrides</button></div>
<div class="out" id="out"><p>Pegá esto dentro de <code>tools/data/logo_overrides.json</code> (o pasámelo y lo aplico):</p><textarea id="ta" readonly></textarea></div>
<main>""" + "\n".join(cards) + """</main>
<script>
const KEY='moai-logo-picks';
let picks={};try{picks=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){}
for(const [id,v] of Object.entries(picks)){
  const sec=document.querySelector(`[data-id="${id}"]`);if(!sec)continue;
  const r=[...sec.querySelectorAll('input[type=radio]')].find(x=>x.value===v.value);
  if(r){r.checked=true;if(v.value==='__manual__')sec.querySelector('.url').value=v.url||''}
}
function save(){const o={};for(const sec of document.querySelectorAll('.card')){
  const r=sec.querySelector('input[type=radio]:checked');if(!r||!r.value)continue;
  o[sec.dataset.id]={value:r.value,url:r.value==='__manual__'?sec.querySelector('.url').value.trim():r.value}}
  picks=o;try{localStorage.setItem(KEY,JSON.stringify(o))}catch(e){}
  document.getElementById('cnt').textContent=Object.keys(o).length+' elegidos'}
document.addEventListener('change',save);document.addEventListener('input',e=>{if(e.target.classList.contains('url')){e.target.closest('.opt').querySelector('input[type=radio]').checked=true;save()}});
document.getElementById('gen').onclick=()=>{const o={};for(const [id,v] of Object.entries(picks)){if(v.url)o[id]={source:v.url}}
  const s=JSON.stringify(o,null,2);document.getElementById('ta').value=s.slice(1,-1).trim()+',';
  document.getElementById('out').classList.add('on');window.scrollTo(0,0)};
save();
</script></body></html>"""
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    main()
