#!/usr/bin/env python3
"""Genera MoaiCatalog.java (catálogo embebido) y manifest.json desde la
copia reparada de pascua (assets/master.json).

Reglas:
  - País: se deduce del nombre del grupo. Grupos explicitamente de un país
    -> ese país. Los genéricos -> "Argentina".
  - Categoría: reglas booleanas (noticias/música/deportes/etc.) sobre el
    nombre del canal (y en 2º plano el grupo). Fallback "General".
  - Se filtran canales basura (".apk", "apk GRATUITA", "Removido de FLOW").
"""
import json
import re
import sys
import unicodedata

MASTER = "/home/apogeo/pascua/assets/master.json"

# id -> (nombre normalizado, prefijo de categoría por grupo)
GROUP_PAIS = {
    "PARAGUAY": "Paraguay",
    "URUGUAY": "Uruguay",
    "ARGENTINA": "Argentina",
    "BOLIVIA": "Bolivia",
    "INTERIOR DE ARGENTINA": "Argentina",
    "INTERNACIONALES": "Internacional",
    "LISTA DE WORLDTV2": "General",
    "ADULTOS": "Adultos",
    "DECODER": "General",
}

# Categoria por grupo (si el grupo mismo describe categoria)
GROUP_CAT = {
    "DEPORTE": "Deportes",
    "DEPORTES": "Deportes",
    "NOTICIAS": "Noticias",
    "MUSICALES": "Música",
    "RADIOS ONLINE": "Música",
    "CINE": "Cine",
    "CULTURALES": "Cultural",
    "INFANTILES": "Infantil",
    "RELiGIOSOS": "Religioso",
}


def norm(s):
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9 ]+", " ", s).strip()
    return s


def slug(s):
    s = norm(s).replace(" ", "_").lower()
    s = re.sub(r"_+", "_", s).strip("_")
    return s if s else "canal"


BAZA = [
    (r"\.apk\b", r"apk gratuita", r"removido de flow"),
    (r"playstore", r"tutorial", r"descargap", r"instalar"),
]


def is_junk(name):
    n = name.lower()
    for rx in BAZA[0]:
        if re.search(rx, n):
            return True
    return False


def guess_pais(grupo):
    clean = norm(grupo).upper()
    for key, pais in GROUP_PAIS.items():
        if key in clean:
            return pais
    for key, cat in GROUP_CAT.items():
        if key in clean:
            return "Argentina"
    return "Argentina"


def guess_cat(name, grupo):
    n = norm(name).upper()
    g = norm(grupo).upper()
    # Palmera de reglas por preferencia (categoría, keywords)
    rules = [
        ("Deportes", "DEPORT", "SPORTS", "ESPN", "FUTBOL", "GOLF", "NBA",
         "BOX", "WRESTLING", "POKER", "TENNIS", "RUGBY", "BASKET"),
        ("Noticias", "NOTICIA", "N24", "C5N", "TELENOCHE", "CN24", "INFO", "TN "),
        ("Música", "MUSIC", "MTV", "VIDEO HITS", "FANATICS", "QUIERO"),
        ("Cine y Series", "PELICULA", "CINE", "MOVIE", "FILM", "CANAL DE LAS ESTRELLAS"),
        ("Infantil", "INFANT", "NICK", "DISNEY", "BOOMERANG", "TOON", "CARTOON",
         "JUNIOR", "CANAL 11", "PAKA"),
        ("Cocina", "COCINA", "GOURMET"),
        ("Cultural", "CULTUR", "ENCUENTRO", "TEC", "FILO"),
        ("Religioso", "RELIGIO", "IGLESIA", "CATOLICA", "EBENEZER", "CRIST"),
        ("Documental", "DOCU", "HISTORY", "NATGEO", "NATIONAL", "DISCOVERY", "ANIMAL"),
        ("Comedia", "COMEDY", "TELENOVELA", "NOVELA", "PASIONES", "SERIES"),
    ]
    for cat, *kws in rules:
        for kw in kws:
            if kw in n or kw in g:
                return cat
    # Grupos que ya describen
    for cat, kw in [("Noticias", "NOTICIAS"), ("Música", "MUSIC"),
                    ("Música", "RADIO"), ("Cine y Series", "CINE"),
                    ("Deportes", "DEPORTE"), ("Deportes", "DEPORTES")]:
        if kw in g:
            return cat
    return "General"


LOGO_OVERRIDES = {
    # Nacionales / Canales de Aire Argentina
    "telefe": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/argentina/telefe-ar.png",
    "telefe_internacional": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/argentina/telefe-ar.png",
    "el_trece_internacional": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/argentina/eltrece-ar.png",
    "net_tv": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/argentina/net-tv-ar.png",
    "construir_tv": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a2/Construir_TV_logo.png/240px-Construir_TV_logo.png",
    # Canales provinciales
    "10_mar_del_plata": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/argentina/canal-10-ar.png",
    "13_corrientes": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/argentina/13max-hd-ar.png",
    "13_telefe_santa_fe": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/argentina/telefe-ar.png",
    "4_san_juan": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/argentina/canal-4-ar.png",
    "7_mendoza": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/argentina/canal-7-hd-ar.png",
    "7_neuquen": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/argentina/telefe-neuquen-ar.png",
    "7_sgo_estero": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/argentina/canal-7-hd-ar.png",
    "8_mar_del_plata": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/argentina/canal-8-mar-del-plata-ar.png",
    "8_telefe_cordoba": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/argentina/telefe-ar.png",
    "8_tucuman": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/argentina/canal-ocho-ar.png",
    "9_bahia_blanca": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/argentina/canal-9-televida-ar.png",
    "9_nordeste": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/argentina/canal-9-televida-ar.png",
    "9_parana": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/argentina/canal-9-televida-ar.png",
    # Deportes
    "espn_premium": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/argentina/espn-premium-ar.png",
    "espn_5": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/argentina/espn-ar.png",
    "espn_2_2": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/argentina/espn-2-ar.png",
    "espn_3_2": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/argentina/espn-3-ar.png",
    "espn_4_2": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/world-latin-america/espn-4-lam.png",
    "espn_5_2": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/world-latin-america/espn-5-lam.png",
    "espn_6": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/world-latin-america/espn-6-lam.png",
    "espn_7": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/world-latin-america/espn-7-lam.png",
    "bein_sports_1": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/united-states/bein-sports-us.png",
    "bein_sports_2": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/united-states/bein-sports-2-us.png",
    "bein_sports_3": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/united-states/bein-sports-3-us.png",
    # Cine y Series / Entretenimiento
    "comedy_central": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/argentina/comedy-central-ar.png",
    "sony_channel": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/argentina/sony-channel-ar.png",
    "sony_movies": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/united-states/sony-movies-us.png",
    "space": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/argentina/space-ar.png",
    "tlnovelas": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/world-latin-america/tlnovelas-lam.png",
    "tnt_novelas": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/world-latin-america/tnt-novelas-lam.png",
    # Internacionales
    "tv_globo": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/brazil/globo-br.png",
    "rede_record": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/brazil/record-br.png",
    "band_news_tv": "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/brazil/band-news-br.png",
    # Paraguay
    "snt": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/77/SNT_2013.png/240px-SNT_2013.png",
    "paravision": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4f/Paravision_2004.png/240px-Paravision_2004.png",
    "paraguay_tv": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/00/ParaguayTV2019.png/240px-ParaguayTV2019.png",
}


def clean_logo(cid, logo):
    if cid in LOGO_OVERRIDES:
        return LOGO_OVERRIDES[cid]
    if "nocookie.net" in logo:
        # Servidor Wikia/Logopedia bloqueado con HTTP 403 por Cloudflare Anti-bot
        return ""
    return logo


def main():
    with open(MASTER, encoding="utf-8") as f:
        data = json.load(f)

    rows = []  # (id, nombre, logo, cat, pais, type, url, drm, headers, flow)
    seen_ids = set()

    for cat in data.get("categories", []):
        grupo = cat.get("name", "")
        pais = guess_pais(grupo)
        for item in cat.get("samples", []):
            name = (item.get("name") or "").strip()
            if not name or is_junk(name):
                continue
            type_ = (item.get("type") or "HLS").upper()
            url = (item.get("original_url") or "").strip()
            if not url:
                continue
            logo = (item.get("icono") or "").strip()
            if logo.startswith("data:"):
                logo = ""
            drm = (item.get("drm_license_uri") or "").strip()
            headers = item.get("headers") or {}
            headers = {str(k): str(v) for k, v in headers.items()}
            categoria = guess_cat(name, grupo)
            base = slug(name)
            cid = base
            i = 1
            while cid in seen_ids:
                i += 1
                cid = f"{base}_{i}"
            seen_ids.add(cid)
            logo = clean_logo(cid, logo)
            rows.append({
                "id": cid,
                "nombre": name,
                "logo": logo,
                "categoria": categoria,
                "pais": pais,
                "type": type_,
                "url": url,
                "drm": drm,
                "headers": headers,
            })

    print(f"Total canales generados: {len(rows)}")
    _write_java(rows)
    _write_manifest(rows)


def _escape_java(s):
    return (s.replace("\\", "\\\\").replace('"', '\\"').
            replace("\n", "\\n"))


def _write_java(rows):
    out = ["package com.infomak.moai.ar;",
           "",
           "import java.util.ArrayList;",
           "import java.util.LinkedHashMap;",
           "import java.util.List;",
           "import java.util.Map;",
           "",
           "/**",
           " * Catálogo generado por tools/generate_catalog.py — NO editar a mano.",
           " * Rebuild: bash build.sh",
           " */",
           "public final class MoaiCatalog {",
           "    private MoaiCatalog() {}",
           "",
           "    public static final int SIZE = %d;" % len(rows),
           "",
           "    public static class Entrada {",
           "        public final String id;",
           "        public final String nombre;",
           "        public final String logo;",
           "        public final String categoria;",
           "        public final String pais;",
           "        public final String type;",
           "        public final String url;",
           "        public final String drm;",
           "        public final Map<String, String> headers;",
           "        Entrada(String id, String nombre, String logo, String categoria,",
           "                String pais, String type, String url, String drm,",
           "                Map<String, String> headers) {",
           "            this.id = id; this.nombre = nombre; this.logo = logo;",
           "            this.categoria = categoria; this.pais = pais;",
           "            this.type = type; this.url = url; this.drm = drm;",
           "            this.headers = headers;",
           "        }",
           "    }",
           "",
           "    private static final Object[][] DATA = {"]

    for r in rows:
        flat = []
        for k, v in r["headers"].items():
            flat.append(_escape_java(k))
            flat.append(_escape_java(v))
        hdrs = 'new String[] { %s }' % (', '.join('"%s"' % s for s in flat))
        out.append(
            '        { "%s", "%s", "%s", "%s", "%s", "%s", "%s", "%s", '
            % (_escape_java(r["id"]), _escape_java(r["nombre"]),
               _escape_java(r["logo"]), _escape_java(r["categoria"]),
               _escape_java(r["pais"]), _escape_java(r["type"]),
               _escape_java(r["url"]), _escape_java(r["drm"]))
            + hdrs + " },")

    out += [
        "    };",
        "",
        "    public static List<Entrada> all() {",
        "        List<Entrada> list = new ArrayList<Entrada>(SIZE);",
"        for (Object[] row : DATA) {",
            "            Map<String, String> headers = new LinkedHashMap<String, String>();",
            "            String[] hh = (String[]) row[8];",
            "            for (int h = 0; h < hh.length; h += 2) { headers.put(hh[h], hh[h + 1]); }",
            "            list.add(new Entrada((String) row[0], (String) row[1], (String) row[2],",
            "                (String) row[3], (String) row[4], (String) row[5], (String) row[6],",
            "                (String) row[7], headers));",
        "        }",
        "        return list;",
        "    }",
        "",
        "    public static Entrada byId(String id) {",
        "        for (Entrada e : all()) { if (e.id.equals(id)) return e; }",
        "        return null;",
        "    }",
        "}",
    ]
    path = ("/home/apogeo/moai/moaiplug_ar/src/plugin/java/com/infomak/"
            "moai/ar/MoaiCatalog.java")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print(f"Escribí {path}")


def _write_manifest(rows):
    canales = [
        {
            "id": r["id"],
            "nombre": r["nombre"],
            "logo": r["logo"],
            "categoria": r["categoria"],
            "pais": r["pais"],
        }
        for r in rows
    ]
    path = "/home/apogeo/moai/moaiplug_ar/build/ult_canales.json"
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(canales, f, ensure_ascii=False, indent=2)
    print(f"Canales manifest: {len(canales)} -> {path}")


if __name__ == "__main__":
    main()