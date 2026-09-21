#!/usr/bin/env python3
"""Genera MoaiCatalog.java (catálogo embebido) y ult_canales.json / manifest.json
desde la copia reparada de pascua (assets/master.json).

Estructura de Grupos y Subgrupos:
  - Clasificación directa y precisa por grupo de origen en master.json.
  - Asignación estricta de País (Argentina, Internacional, Paraguay, Uruguay, Bolivia, Brasil, Canadá).
  - Asignación de Categoría alineada a la UI de moai3 (Aire, Interior, Noticias, Deportes,
    Cine y Series, Infantil, Cultural, Novelas, Música, Radios, Cocina, Religioso, Adultos).
  - Ordenamiento lógico por relevancia dentro de cada categoría (canales principales primero).
  - Filtro exhaustivo de basura (links telegram, apks, tutoriales).
  - Actualización masiva de logos hacia fuentes CDN estables (tv-logos raw GitHub).
"""
import json
import re
import sys
import unicodedata

MASTER = "/home/apogeo/pascua/assets/master.json"

# Configuración declarativa de los 30 grupos de master.json
GROUP_CONFIG = {
    "📺  Lista de worldtv2": {"skip": True},
    "📺  PARAGUAY": {"pais": "Paraguay", "cat": "General"},
    "📺  URUGUAY": {"pais": "Uruguay", "cat": "General"},
    "📺  ARGENTINA": {"pais": "Argentina", "cat": "Aire"},
    "📺  NOTICIAS": {"pais": "Argentina", "cat": "Noticias"},
    "📺  INTERIOR DE ARGENTINA": {"pais": "Argentina", "cat": "Interior"},
    "📺  DEPORTE DE ARGENTINA": {"pais": "Argentina", "cat": "Deportes"},
    "📺 Dsports": {"pais": "Argentina", "cat": "Deportes"},
    "📺  LPF PLAY": {"pais": "Argentina", "cat": "Deportes"},
    "📺  DEPORTE INTERNACIONAL": {"pais": "Internacional", "cat": "Deportes"},
    "📺  TNT SPORTS REINO UNIDO": {"pais": "Internacional", "cat": "Deportes"},
    "📺  HBO & UNIVERSAL": {"pais": "Argentina", "cat": "Cine y Series"},
    "📺  CINE & SERIES": {"pais": "Argentina", "cat": "Cine y Series"},
    "📺  INFANTILES": {"pais": "Argentina", "cat": "Infantil"},
    "📺  CULTURALES": {"pais": "Argentina", "cat": "Cultural"},
    "📺  NOVELAS": {"pais": "Argentina", "cat": "Novelas"},
    "📺  COCINA": {"pais": "Argentina", "cat": "Cocina"},
    "📺  RELIGIOSOS": {"pais": "Argentina", "cat": "Religioso"},
    "📺  MUSICALES": {"pais": "Argentina", "cat": "Música"},
    "📺️  RADIOS ONLINE": {"pais": "Argentina", "cat": "Radios"},
    "📺  INTERNACIONALES": {"pais": "Internacional", "cat": "General"},
    "DEPORTES ESPN SUR": {"pais": "Argentina", "cat": "Deportes"},
    "⚽ 🥅⛳🏎️🏇🏻DEPORTES VARIADOS": {"pais": "Internacional", "cat": "Deportes"},
    "⚽ DEPORTES BRASIL": {"pais": "Brasil", "cat": "Deportes"},
    "🎾🏓DEPORTES, TENNIS, PADEL, NBA, GOLF🏌‍♀️": {"pais": "Internacional", "cat": "Deportes"},
    "🏁DEPORTE MOTOR🏎": {"pais": "Internacional", "cat": "Deportes"},
    "🥋DEPORTES DE COMBATES🥊": {"pais": "Internacional", "cat": "Deportes"},
    "📺 BOLIVIA": {"pais": "Bolivia", "cat": "General"},
    "📺  TSN🇨🇦": {"pais": "Canadá", "cat": "Deportes"},
    "ADULTOS": {"pais": "Argentina", "cat": "Adultos"},
}

# CDNs estables
TV_AR = "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/argentina"
TV_LAM = "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/world-latin-america"
TV_ES = "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/spain"
TV_CA = "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/canada"
TV_BR = "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/brazil"
TV_US = "https://raw.githubusercontent.com/tv-logo/tv-logos/refs/heads/main/countries/united-states"

LOGO_OVERRIDES = {
    # Aire Argentina
    "telefe": f"{TV_AR}/telefe-ar.png",
    "telefe_internacional": f"{TV_AR}/telefe-ar.png",
    "el_trece": f"{TV_AR}/eltrece-ar.png",
    "el_trece_internacional": f"{TV_AR}/eltrece-ar.png",
    "america_tv": f"{TV_AR}/america-ar.png",
    "elnueve": f"{TV_AR}/elnueve-ar.png",
    "tv_publica": f"{TV_AR}/television-publica-ar.png",
    "net_tv": f"{TV_AR}/net-tv-ar.png",
    "canal_de_la_ciudad": f"{TV_AR}/canal-de-la-ciudad-ar.png",
    "canal_rural": f"{TV_AR}/canal-rural-ar.png",
    "telemax": f"{TV_AR}/telemax-ar.png",
    "argentinisima": f"{TV_AR}/argentinisima-satelital-ar.png",
    "construir_tv": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a2/Construir_TV_logo.png/240px-Construir_TV_logo.png",
    "garage_tv": f"{TV_AR}/el-garage-tv-ar.png",
    "metro": f"{TV_AR}/metro-ar.png",

    # Noticias Argentina
    "tn": f"{TV_AR}/tn-todo-noticias-ar.png",
    "c5n": f"{TV_AR}/c5n-ar.png",
    "la_nacion": f"{TV_AR}/la-nacion-mas-ar.png",
    "a24": f"{TV_AR}/a24-ar.png",
    "cronica_tv": f"{TV_AR}/cronica-hd-ar.png",
    "canal_26": f"{TV_AR}/canal-26-ar.png",
    "ip_noticias": f"{TV_AR}/ip-noticias-ar.png",
    "argentina_12": f"{TV_AR}/argentina-12-ar.png",

    # Canales provinciales (Interior)
    "10_mar_del_plata": f"{TV_AR}/canal-10-ar.png",
    "13_corrientes": f"{TV_AR}/13max-hd-ar.png",
    "13_telefe_santa_fe": f"{TV_AR}/telefe-ar.png",
    "4_san_juan": f"{TV_AR}/canal-4-ar.png",
    "7_mendoza": f"{TV_AR}/canal-7-hd-ar.png",
    "7_neuquen": f"{TV_AR}/telefe-neuquen-ar.png",
    "7_salta": f"{TV_AR}/canal-7-hd-ar.png",
    "7_sgo_estero": f"{TV_AR}/canal-7-hd-ar.png",
    "8_mar_del_plata": f"{TV_AR}/canal-8-mar-del-plata-ar.png",
    "8_telefe_cordoba": f"{TV_AR}/telefe-ar.png",
    "8_tucuman": f"{TV_AR}/canal-ocho-ar.png",
    "9_bahia_blanca": f"{TV_AR}/canal-9-televida-ar.png",
    "9_nordeste": f"{TV_AR}/canal-9-televida-ar.png",
    "9_parana": f"{TV_AR}/canal-9-televida-ar.png",
    "11_salta": f"{TV_AR}/telefe-ar.png",

    # Deportes Argentina / LAM
    "tyc_sports": f"{TV_AR}/tyc-sports-ar.png",
    "tyc_sports_2": f"{TV_AR}/tyc-sports-2-ar.png",
    "tyc_sports_3": f"{TV_AR}/tyc-sports-3-ar.png",
    "tyc_sports_fan": f"{TV_AR}/tyc-sports-ar.png",
    "tyc_sports_internacional": f"{TV_AR}/tyc-sports-ar.png",
    "espn_premium": f"{TV_AR}/espn-premium-ar.png",
    "tnt_sports_premium": f"{TV_AR}/tnt-sports-ar.png",
    "tnt_sports": f"{TV_AR}/tnt-sports-ar.png",
    "espn": f"{TV_AR}/espn-ar.png",
    "espn_2": f"{TV_AR}/espn-2-ar.png",
    "espn_3": f"{TV_AR}/espn-3-ar.png",
    "espn_4": f"{TV_LAM}/espn-4-lam.png",
    "espn_5": f"{TV_LAM}/espn-5-lam.png",
    "espn_6": f"{TV_LAM}/espn-6-lam.png",
    "espn_7": f"{TV_LAM}/espn-7-lam.png",
    "espn_2_2": f"{TV_AR}/espn-2-ar.png",
    "espn_3_2": f"{TV_AR}/espn-3-ar.png",
    "espn_4_2": f"{TV_LAM}/espn-4-lam.png",
    "espn_5_2": f"{TV_LAM}/espn-5-lam.png",
    "espn_8_the_ocho": f"{TV_AR}/espn-ar.png",
    "fox_sports": f"{TV_AR}/fox-sports-ar.png",
    "fox_sports_2": f"{TV_AR}/fox-sports-2-ar.png",
    "fox_sports_3": f"{TV_AR}/fox-sports-3-ar.png",
    "deportv": f"{TV_AR}/deportv-ar.png",
    "america_sports": f"{TV_AR}/america-sports-ar.png",
    "claro_sports": f"{TV_LAM}/claro-sports-lam.png",
    "bein_sports_1": f"{TV_US}/bein-sports-us.png",
    "bein_sports_2": f"{TV_US}/bein-sports-2-us.png",
    "bein_sports_3": f"{TV_US}/bein-sports-3-us.png",

    # Cine y Series / Entretenimiento
    "comedy_central": f"{TV_AR}/comedy-central-ar.png",
    "sony_channel": f"{TV_AR}/sony-channel-ar.png",
    "sony_movies": f"{TV_US}/sony-movies-us.png",
    "space": f"{TV_AR}/space-ar.png",
    "tlnovelas": f"{TV_LAM}/tlnovelas-lam.png",
    "tnt_novelas": f"{TV_LAM}/tnt-novelas-lam.png",

    # Canadá (TSN)
    "tsn_1": f"{TV_CA}/tsn-1-ca.png",
    "tsn_2": f"{TV_CA}/tsn-2-ca.png",
    "tsn_3": f"{TV_CA}/tsn-3-ca.png",
    "tsn_4": f"{TV_CA}/tsn-4-ca.png",
    "tsn_5": f"{TV_CA}/tsn-5-ca.png",
    "tsn_the_ocho": f"{TV_CA}/tsn-ca.png",

    # Brasil
    "tv_globo": f"{TV_BR}/globo-br.png",
    "rede_record": f"{TV_BR}/record-br.png",
    "band_news_tv": f"{TV_BR}/band-news-br.png",
    "sportv": f"{TV_BR}/sportv-br.png",
    "sportv_2": f"{TV_BR}/sportv2-br.png",
    "sportv_3": f"{TV_BR}/sportv3-br.png",
    "premiere": f"{TV_BR}/premiere-br.png",

    # España
    "antena_3": f"{TV_ES}/antena-3-es.png",
    "tv_galicia": f"{TV_ES}/galicia-es.png",

    # Paraguay
    "snt": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/77/SNT_2013.png/240px-SNT_2013.png",
    "paravision": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4f/Paravision_2004.png/240px-Paravision_2004.png",
    "paraguay_tv": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/00/ParaguayTV2019.png/240px-ParaguayTV2019.png",
}

JUNK_PATTERNS = [
    r"\.apk\b", r"apk gratuita", r"removido de flow",
    r"playstore", r"tutorial", r"descargap", r"instalar",
    r"^t\.me/", r"worldtv"
]


def norm(s):
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9 ]+", " ", s).strip()
    return s


def slug(s):
    s = norm(s).replace(" ", "_").lower()
    s = re.sub(r"_+", "_", s).strip("_")
    return s if s else "canal"


def is_junk(name):
    n = name.lower().strip()
    for rx in JUNK_PATTERNS:
        if re.search(rx, n):
            return True
    return False


def clean_logo(cid, name, logo):
    if cid in LOGO_OVERRIDES:
        return LOGO_OVERRIDES[cid]
    n = norm(name).upper()
    # Casos genéricos basados en nombre
    if "DSPORTS 2" in n or "DSPORTS2" in n:
        return f"{TV_LAM}/dsports2-lam.png"
    if "DSPORTS +" in n or "DSPORTS PLUS" in n:
        return f"{TV_LAM}/dsports-plus-lam.png"
    if "DSPORTS" in n:
        return f"{TV_LAM}/dsports-lam.png"

    if "nocookie.net" in logo or logo.startswith("data:"):
        return ""
    return logo


def channel_priority(item):
    """Orden de relevancia dentro de cada grupo para que en la TV aparezcan
    primero los canales troncales más vistos."""
    cat = item["categoria"]
    n = norm(item["nombre"]).upper()
    
    if cat == "Aire":
        if "TELEFE" in n and "INTERNACIONAL" not in n: return (1, n)
        if "TRECE" in n and "INTERNACIONAL" not in n: return (2, n)
        if "AMERICA" in n and "SPORTS" not in n and "TUCUMAN" not in n: return (3, n)
        if "NUEVE" in n or "CANAL 9" in n: return (4, n)
        if "PUBLICA" in n: return (5, n)
        if "NET TV" in n: return (6, n)
        if "BRAVO" in n: return (7, n)
        if "CIUDAD" in n: return (8, n)
        return (20, n)
    
    if cat == "Noticias":
        if n == "TN" or "TODO NOTICIAS" in n: return (1, n)
        if "C5N" in n: return (2, n)
        if "LA NACION" in n or "LN" in n: return (3, n)
        if "A24" in n: return (4, n)
        if "CRONICA" in n: return (5, n)
        if "CANAL 26" in n: return (6, n)
        if "IP NOTICIAS" in n: return (7, n)
        return (20, n)
        
    if cat == "Deportes":
        # Troncales y packs de fútbol
        if "TYC SPORTS" in n and "INTERNACIONAL" not in n and "FAN" not in n: return (1, n)
        if "ESPN PREMIUM" in n: return (2, n)
        if "TNT SPORTS" in n: return (3, n)
        if n == "ESPN": return (4, n)
        if "ESPN 2" in n: return (5, n)
        if "ESPN 3" in n: return (6, n)
        if "ESPN 4" in n: return (7, n)
        if "FOX SPORTS" in n: return (8, n)
        if "DSPORTS" in n: return (9, n)
        if "LPF" in n or "PLAY" in n: return (10, n)
        if "DEPORTV" in n: return (11, n)
        return (30, n)

    if cat == "Cine y Series":
        if "HBO" in n: return (1, n)
        if "UNIVERSAL" in n: return (2, n)
        return (20, n)

    return (50, n)


def main():
    with open(MASTER, encoding="utf-8") as f:
        data = json.load(f)

    rows = []
    seen_ids = set()

    for cat_obj in data.get("categories", []):
        gname = cat_obj.get("name", "")
        cfg = GROUP_CONFIG.get(gname, {})
        if cfg.get("skip"):
            continue

        base_pais = cfg.get("pais", "Argentina")
        base_cat = cfg.get("cat", "General")

        for item in cat_obj.get("samples", []):
            name = (item.get("name") or "").strip()
            if not name or is_junk(name):
                continue
            type_ = (item.get("type") or "HLS").upper()
            url = (item.get("original_url") or "").strip()
            if not url:
                continue
            logo = (item.get("icono") or "").strip()
            drm = (item.get("drm_license_uri") or "").strip()
            headers = item.get("headers") or {}
            headers = {str(k): str(v) for k, v in headers.items()}

            pais = base_pais
            categoria = base_cat

            # Refinamientos puntuales por canal
            n_up = norm(name).upper()
            if "BOXEO" in n_up or "FIGHT" in n_up or "HARD KNOCKS" in n_up:
                categoria = "Deportes"
            elif gname == "📺  PARAGUAY" and ("TIGO SPORTS" in n_up or "DEPORTES" in n_up):
                categoria = "Deportes"
            elif gname == "📺  URUGUAY" and ("DSPORTS" in n_up or "VTV PLUS" in n_up):
                categoria = "Deportes"
            elif gname == "📺  INTERNACIONALES" and ("CNN" in n_up or "24H" in n_up or "NEWS" in n_up):
                categoria = "Noticias"
            elif gname == "📺  INTERNACIONALES" and ("BARCA TV" in n_up or "GOL" in n_up or "SPORT" in n_up):
                categoria = "Deportes"

            base = slug(name)
            cid = base
            i = 1
            while cid in seen_ids:
                i += 1
                cid = f"{base}_{i}"
            seen_ids.add(cid)

            logo = clean_logo(cid, name, logo)

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

    CATEGORY_PRIORITY = {
        "Aire": 1,
        "Noticias": 2,
        "Deportes": 3,
        "Cine y Series": 4,
        "Infantil": 5,
        "Cultural": 6,
        "Novelas": 7,
        "Cocina": 8,
        "Música": 9,
        "Radios": 10,
        "Religioso": 11,
        "Interior": 12,
        "General": 13,
        "Adultos": 999,
    }

    # Ordenamiento: primero por País, luego por Categoría (Adultos al final), y dentro por relevancia
    # Manteniendo Argentina primero
    def sort_key(r):
        p_order = 0 if r["pais"] == "Argentina" else 1
        cat_prio = CATEGORY_PRIORITY.get(r["categoria"], 50)
        prio, norm_n = channel_priority(r)
        return (p_order, r["pais"], cat_prio, r["categoria"], prio, norm_n)

    rows.sort(key=sort_key)

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