#!/usr/bin/env python3
"""Genera MoaiCatalog.java (catálogo embebido) y ult_canales.json / manifest.json
desde la copia reparada de pascua (assets/master.json) + el catálogo fusionado
de moaiplug_free (tools/data/canales_free.json).

Estructura de Grupos y Subgrupos:
  - Clasificación directa y precisa por grupo de origen en master.json.
  - Asignación estricta de País (Argentina, Internacional, Paraguay, Uruguay, Bolivia, Brasil, Canadá).
  - Asignación de Categoría alineada a la UI de moai3 (Aire, Interior, Noticias, Deportes,
    Cine y Series, Infantil, Cultural, Novelas, Música, Radios, Cocina, Religioso, Adultos).
  - Ordenamiento lógico por relevancia dentro de cada categoría (canales principales primero).
  - Filtro exhaustivo de basura (links telegram, apks, tutoriales).
  - Actualización masiva de logos hacia fuentes CDN estables (tv-logos raw GitHub).
  - Fusión de moaiplug_free (v1.6.0): se suman SOLO los canales ausentes; en
    cualquier duplicado gana el canal de pascua/AR (nada de lo que ya funciona
    se toca). El diff queda en build/informe_merge_free.json.
"""
import json
import os
import re
import sys
import unicodedata
from urllib.parse import quote, urlsplit, urlunsplit

ROOT = "/home/apogeo/moai/moaiplug_ar"
MASTER = "/home/apogeo/pascua/assets/master.json"
# Instantánea del catálogo de moaiplug_free (ver tools/import_free_catalog.py).
FREE_SNAPSHOT = os.path.join(ROOT, "tools", "data", "canales_free.json")
MERGE_REPORT = os.path.join(ROOT, "build", "informe_merge_free.json")

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

# Canales caídos o con streams permanentemente rotos auditados
EXCLUDED_CHANNEL_IDS = {
    # Novelas (HTTP 404)
    "az_corazon", "azteca_7",
    # Música (HTTP 404)
    "beat_box", "exa_tv", "vr", "video_rola",
    # Radios (HTTP 404 / 401 / SSL caducado / Servidor fuera de línea)
    "del_sur", "cadena_alegria", "estacion_21", "mas_tropical", "mitre_jujuy", "punto_de_encuentro",
    # Deportes (LPF Play inactivos / Astra expirado / izzigo / peacock 403 / dazn timeout)
    "play_1", "play_1_2", "play_2", "play_2_2", "play_3", "play_3_2",
    "play_4", "play_4_2", "play_5", "play_5_2", "play_6", "play_6_2",
    "basquet_tv", "eventos_formula_1", "plus_tv", "sky_sport_f1_eventos",
    "t_deportes", "telemundo", "dazn_f1",
    # Interior (HTTP 404 / Conexión rechazada)
    "5_telefe_rosario_cba", "13_telefe_santa_fe", "12_misiones", "san_luis",
    # General / Bolivia (Geobloqueo regional HTTP 403)
    "cadena_a", "bolivia_tv", "bolivision", "f10", "red_gigavision", "red_pat",
    "rtp", "red_uno", "tv_culturas", "unitel_cochabamba", "unitel_la_paz",
    "tvu_la_paz", "atb",
    # Adultos (HTTP 403)
    "sexy_hot",
    # Religioso (HTTP 404)
    "jta_tv",
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
    "construir_tv": "https://upload.wikimedia.org/wikipedia/commons/f/f3/LogoCTVpng.png",
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
    "snt": "https://upload.wikimedia.org/wikipedia/commons/6/6a/SNT_2013_logotype.png",
    "paravision": "https://upload.wikimedia.org/wikipedia/commons/b/bd/Paravision_logo.png",
    "paraguay_tv": "https://upload.wikimedia.org/wikipedia/commons/1/10/Paraguay_TV_logo.png",
}

JUNK_PATTERNS = [
    r"\.apk\b", r"apk gratuita", r"removido de flow",
    r"playstore", r"tutorial", r"descargap", r"instalar",
    r"^t\.me/", r"worldtv"
]

# Logos verificados como MUERTOS con tools/check_logos.py (HTTP 404/403 o
# servidor que cierra la conexion). No hay override posible: se emiten vacios
# para que la app dibuje el logo por defecto en vez de una imagen rota.
#   - i.postimg.cc/.../6583*.webp : postimg rejects la conexion (h scraped)
#   - allegrohd.com/images/logo3.png : 404 Not Found
#   - lu5am.com/wp-content/... : 403 Forbidden (hotlink protection)
DEAD_LOGO_IDS = {
    "cinema", "comedy", "crime", "reality",
    "hbo_multicamara", "4_posadas",
    "allegro", "lu5_de_neuquen",
}

# /thumb/ de Wikimedia devuelve HTTP 400 si el ancho no es uno de los
# estandar, y los anchos validos cambian segun el archivo (para
# Norte_Grande_Federal valen 120/250/330/500/1280/1920; 320 no val nunca).
# Special:FilePath?width=N si genera la miniatura correcta para cualquier N.
WIKIMEDIA_THUMB_RE = re.compile(
    r"^https?://upload\.wikimedia\.org/wikipedia/commons/thumb/"
    r"(?:[0-9a-f]{1,2}/){1,3}([^/]+?)/\d+px-", re.I
)
WIKIMEDIA_WIDTH = 250


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
    if cid in DEAD_LOGO_IDS:
        return ""
    if cid in LOGO_OVERRIDES:
        return normalize_logo_url(LOGO_OVERRIDES[cid])
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
    return normalize_logo_url(logo)


def normalize_logo_url(url):
    """Deja la URL en una forma que el player y los CDNs puedan cargar."""
    if not url:
        return url
    # Anchos de /thumb/ de Wikimedia -> Special:FilePath (siempre valido).
    m = WIKIMEDIA_THUMB_RE.match(url)
    if m:
        return (f"https://commons.wikimedia.org/wiki/Special:FilePath/"
                f"{m.group(1)}?width={WIKIMEDIA_WIDTH}")
    # El master.json trae no-ASCII crudo en el path (p.ej. "CNN_en_Español.png").
    # Sin percent-encoding, la carga falla con UnicodeEncodeError.
    parts = urlsplit(url)
    return urlunsplit((
        parts.scheme, parts.netloc,
        quote(parts.path, safe="/%:@&=+$,~()!*'"),
        parts.query, parts.fragment,
    ))


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


# ------------------------------------------------- fusión con moaiplug_free
# Los nombres de Free traen el sufijo de calidad ("Canal 5 (1080p)") y avisos
# de disponibilidad ("[Not 24/7]", "[Geo-blocked]"); AR los muestra limpios.
# Para comparar identidades se quitan ambos, para mostrar solo la calidad.
QUALITY_TAIL_RE = re.compile(r"\s*[\(\[]\s*\d{3,4}\s*[pi]\s*[\)\]]\s*$", re.I)
NOTE_TAIL_RE = re.compile(
    r"\s*\[\s*(?:not\s*24/7|geo-?blocked|geo-?block)\s*\]\s*$", re.I)

# Variante regional de un canal que AR ya tiene, con otro nombre. free -> AR.
FREE_ALIASES = {
    "metrotv": "metro",
    "telefebuenosaires": "telefe",
    "telefesalta": "11salta",
    "unifetv": "unife",
    "adultswimlatinamerica": "adultswim",
    "disneychannellatinamerica": "disneychannel",
    "disneychannellatinamericapanregionalhd": "disneychannel",
    "disneyjrlatinamericasouth": "disneyjunior",
    "disneyjrlatinamericasouthhd": "disneyjunior",
    "comedycentrallatinamerica": "comedycentral",
}

# Etiqueta de país entre paréntesis: es ruido para comparar identidades
# ("Telefe (Argentina)" y "Telefe" son el mismo canal).
GEO_TAG_RE = re.compile(
    r"\(\s*(?:argentina|uruguay|paraguay|bolivia|brasil|chile|peru|"
    r"internacional|latam|latinoamerica)\s*\)", re.I)

# Los canales de Free que caen en "General" (su categoría iptv-org es genérica)
# pero son de una ciudad/provincia: moai3 los muestra en "Interior", como los
# que ya vienen de pascua ("8 Mar del Plata", "4 San Juan", ...).
FREE_LOCAL_RE = re.compile(
    r"\b(?:formosa|la pampa|las heras|pinamar|esquel|jujuy|teleaire|"
    r"villa dolores|morteros|la costa|mar del plata|puan|santa clara|"
    r"villa maza|pulpo|ciudad magica|magica|celta|senillosa|sicardi|"
    r"villa mantero|bariloche|ushuaia|fueguina|gualeguay|venado tuerto|"
    r"tacural|rafaela|salta|chepes|neuquen|santa fe|resistencia|san juan|"
    r"corrientes|misiones|posadas|entre rios|catamarca|mendoza|rosario|"
    r"cordoba|tucuman|buenos aires)\b", re.I)

FREE_JUNK_RE = re.compile(
    r"t\.me/|whatsapp|telegram|\.apk\b|playstore|blogspot|facebook\.com|"
    r"pastebin", re.I)

# Canales de Free caídos al auditarlos en vivo con tools/check_channels.py.
# Mismo criterio que EXCLUDED_CHANNEL_IDS: no entran al catálogo.
FREE_EXCLUDED_CHANNEL_IDS = {
    # HTTP 404 (playlist borrada en el origen)
    "eco_tv", "litus_tv_720p_not_24_7",
    # HTTP 403 (Cloudflare / CDN rechaza el origen o bloquea la región)
    "el_siete_1080p", "telefe_tucuman_1080p",
}


def clean_free_name(nombre):
    """Quita el sufijo de calidad, los avisos y el etiqueta de país."""
    s = (nombre or "").strip()
    prev = None
    while prev != s:
        prev = s
        s = NOTE_TAIL_RE.sub("", s.strip())
        s = QUALITY_TAIL_RE.sub("", s.strip())
        s = GEO_TAG_RE.sub("", s.strip())
    return re.sub(r"\s{2,}", " ", s).strip() or (nombre or "").strip()


def channel_key(nombre, cid=""):
    """Clave de identidad de un canal: sin calidad, avisos, país ni espacios.

    "Canal 8 Mar del Plata (720p) [Not 24/7]" y "8 Mar del Plata" dan la misma
    clave ("8mardelplata"); "4 San Juan" y "8 San Juan" no.
    """
    s = norm(clean_free_name(nombre)).lower().replace(" ", "")
    if s.startswith("canal"):
        s = s[5:]
    return s or cid


def guess_type(url):
    path = urlsplit(url).path.lower()
    if path.endswith(".m3u8"):
        return "HLS"
    if path.endswith(".mpd"):
        return "DASH"
    if path.endswith(".ts"):
        return "MPEGTS"
    return "DIRECT"


def merge_free_channels(rows):
    """Agrega a `rows` los canales de moaiplug_free que AR no tiene.

    Gana siempre el catálogo AR: se descarta un canal de Free si coincide el
    id, la URL exacta o la identidad del canal (nombre canónico o alias).
    Devuelve (nuevos, descartados) para el informe de merge.
    """
    if not os.path.isfile(FREE_SNAPSHOT):
        print(f"[aviso] no existe {FREE_SNAPSHOT}: se omite la fusión de "
              f"moaiplug_free (ver tools/import_free_catalog.py)")
        return [], []

    with open(FREE_SNAPSHOT, encoding="utf-8") as f:
        libres = json.load(f).get("canales", [])

    seen_ids = {r["id"] for r in rows}
    seen_urls = {r["url"].strip().lower() for r in rows}
    keys = {}
    for r in rows:
        keys.setdefault(channel_key(r["nombre"], r["id"]), r["id"])

    nuevos, descartados = [], []
    for c in libres:
        cid = c.get("id", "").strip()
        nombre = (c.get("nombre") or "").strip()
        url = (c.get("url") or "").strip()
        if not cid or not url or not nombre:
            descartados.append({"id": cid, "nombre": nombre,
                                "motivo": "incompleto"})
            continue
        if cid in FREE_EXCLUDED_CHANNEL_IDS:
            descartados.append({"id": cid, "nombre": nombre,
                                "motivo": "caído en la auditoría"})
            continue
        if FREE_JUNK_RE.search(url) or FREE_JUNK_RE.search(nombre):
            descartados.append({"id": cid, "nombre": nombre,
                                "motivo": "enlace no reproducible"})
            continue
        if cid in seen_ids:
            descartados.append({"id": cid, "nombre": nombre,
                                "motivo": "id duplicado", "gana": cid})
            continue
        if url.lower() in seen_urls:
            match = next(r["id"] for r in rows
                         if r["url"].strip().lower() == url.lower())
            descartados.append({"id": cid, "nombre": nombre,
                                "motivo": "url duplicada", "gana": match})
            continue

        key = channel_key(nombre, cid)
        gana = FREE_ALIASES.get(key) or (keys.get(key))
        if gana:
            descartados.append({
                "id": cid, "nombre": nombre,
                "motivo": ("alias de un canal de AR"
                           if key in FREE_ALIASES else "mismo canal"),
                "gana": gana,
            })
            continue

        # Id libre y único: se sanea por si el origen trajera algo raro.
        new_id = cid if re.fullmatch(r"[a-z0-9_]+", cid) else slug(cid)
        while new_id in seen_ids:
            new_id += "_2"

        cat = c.get("categoria") or "General"
        nombre_limpio = clean_free_name(nombre)
        if FREE_LOCAL_RE.search(nombre_limpio):
            cat = "Interior"

        row = {
            "id": new_id,
            "nombre": nombre_limpio,
            "logo": clean_logo(new_id, nombre, (c.get("logo") or "").strip()),
            "categoria": cat,
            "pais": c.get("pais") or "Argentina",
            "type": guess_type(url),
            "url": url,
            "drm": "",
            "headers": {},
        }
        rows.append(row)
        nuevos.append({"id": new_id, "nombre": row["nombre"],
                       "categoria": row["categoria"], "tipo": row["type"]})
        seen_ids.add(new_id)
        seen_urls.add(url.lower())
        keys[key] = new_id
    return nuevos, descartados


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

            if cid in EXCLUDED_CHANNEL_IDS:
                continue

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

    # Fusión con moaiplug_free (después del filtro de exclusión, para que la
    # comparación sea contra el catálogo AR final; el orden se aplica después).
    nuevos, descartados = merge_free_channels(rows)

    # Ordenamiento: primero por País, luego por Categoría (Adultos al final), y dentro por relevancia
    # Manteniendo Argentina primero
    def sort_key(r):
        p_order = 0 if r["pais"] == "Argentina" else 1
        cat_prio = CATEGORY_PRIORITY.get(r["categoria"], 50)
        prio, norm_n = channel_priority(r)
        return (p_order, r["pais"], cat_prio, r["categoria"], prio, norm_n)

    rows.sort(key=sort_key)

    print(f"Total canales generados: {len(rows)}")
    if nuevos or descartados:
        print(f"Fusión moaiplug_free: +{len(nuevos)} nuevos, "
              f"{len(descartados)} duplicados (gana AR)")
        _write_merge_report(rows, nuevos, descartados)
    _write_java(rows)
    _write_manifest(rows)


def _write_merge_report(rows, nuevos, descartados):
    os.makedirs(os.path.dirname(MERGE_REPORT), exist_ok=True)
    with open(MERGE_REPORT, "w", encoding="utf-8") as f:
        json.dump({
            "total_final": len(rows),
            "total_ar_previo": len(rows) - len(nuevos),
            "importados_de_free": len(nuevos),
            "descartados_gana_ar": len(descartados),
            "nuevos": nuevos,
            "descartados": descartados,
        }, f, ensure_ascii=False, indent=2)
    print(f"Informe de fusión: {MERGE_REPORT}")


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