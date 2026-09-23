#!/usr/bin/env python3
"""
Genera el informe Markdown docs/informe_canales_caidos.md a partir de caidos.json.
"""

import json
import os

repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
caidos_path = os.path.join(repo_dir, "caidos.json")
output_path = os.path.join(repo_dir, "docs/informe_canales_caidos.md")

with open(caidos_path, "r", encoding="utf-8") as f:
    data = json.load(f)

channels = data.get("channels", [])
failed = [c for c in channels if c.get("status") == "FAIL"]
total = data.get("total", len(channels))
ok_count = data.get("ok", total - len(failed))
ok_pct = data.get("ok_percent", round(ok_count / total * 100, 1))

by_cat = {}
for c in failed:
    by_cat.setdefault(c.get("categoria", "Sin categoría"), []).append(c)

md = []
md.append("# 📋 Informe de Canales Caídos — Moai Argentina (`moaiplug_ar`)\n\n")
md.append(f"> **Fecha de auditoría:** 23 de septiembre de 2026  \n")
md.append(f"> **Herramienta:** `tools/check_channels.py`  \n")
md.append(f"> **Canales analizados:** {total}  \n")
md.append(f"> **🟢 Operativos:** {ok_count} ({ok_pct}%)  \n")
md.append(f"> **🔴 Caídos / Error:** {len(failed)} ({round(len(failed)/total*100, 1)}%)  \n\n")

md.append("---\n\n")
md.append("## 1. Resumen Ejecutivo por Categoría\n\n")
md.append("| Categoría | Caídos | Motivo Principal |\n")
md.append("|---|:---:|---|\n")

motivos_resumen = {
    "Deportes": "Feeds temporales de partidos (LPF Play) inactivos fuera de horario + links 404",
    "General": "Geobloqueo regional (Bolivia) con HTTP 403 Forbidden",
    "Radios": "Streams con enlaces viejos (404), SSL vencido o servidores caídos",
    "Interior": "Servidores provinciales locales caídos o enlaces caducados (404)",
    "Música": "Enlaces muertos (HTTP 404)",
    "Novelas": "Enlaces muertos (HTTP 404)",
    "Adultos": "Bloqueo HTTP 403 en CDN",
    "Religioso": "Enlace muerto (HTTP 404)",
    "Noticias": "Timeout de CDN internacional",
}

for cat, items in sorted(by_cat.items(), key=lambda x: -len(x[1])):
    md.append(f"| **{cat}** | {len(items)} | {motivos_resumen.get(cat, 'Errores de conexión')} |\n")

md.append("\n---\n\n")
md.append("## 2. Diagnóstico de Causas Raíz\n\n")
md.append("1. **Transmisiones temporales de eventos (LPF Play / F1):** Señales que únicamente transmiten cuando hay partidos en vivo. Fuera de evento devuelven `Network unreachable` o `404 Not Found` porque los transcodificadores de origen no emiten.\n")
md.append("2. **Geobloqueo regional (HTTP 403 Forbidden):** Varios canales de Bolivia y señales internacionales rechazan peticiones fuera de su país o requieren autenticación web.\n")
md.append("3. **Enlaces caídos o deprecados (HTTP 404 / 401):** Canales de música y radios locales cuyos servidores cambiaron de URL o cerraron.\n")
md.append("4. **Certificados TLS caducados:** Fallos en el handshake SSL (`CERTIFICATE_VERIFY_FAILED`) en servidores que no renovaron su certificado.\n\n")

md.append("---\n\n")
md.append("## 3. Detalle Exhaustivo de los Canales Caídos\n\n")

for cat, items in sorted(by_cat.items()):
    md.append(f"### 📁 {cat} ({len(items)} canales)\n\n")
    md.append("| Canal | ID en Plugin | Código / Error | Diagnóstico Técnico |\n")
    md.append("|---|---|---|---|\n")
    for c in items:
        nombre = c.get("nombre", "")
        cid = c.get("id", "")
        err = c.get("error", "")
        code = c.get("code", 0)
        code_str = f"HTTP {code}" if code else "Error Red"

        if "Network is unreachable" in err:
            diag = "Feed temporal inactivo (Solo en vivo durante partidos)"
        elif "404" in err:
            diag = "Enlace caído o cambiado de ruta en origen"
        elif "403" in err:
            diag = "Geobloqueo regional o protección CDN"
        elif "401" in err:
            diag = "Requiere credenciales / token de sesión"
        elif "SSL" in err or "CERTIFICATE" in err:
            diag = "Certificado SSL del servidor vencido"
        elif "Connection refused" in err:
            diag = "Servidor fuera de línea (puerto cerrado)"
        elif "Timeout" in err:
            diag = "Servidor sin respuesta dentro del límite de tiempo"
        else:
            diag = "Fallo de conexión"

        md.append(f"| **{nombre}** | `{cid}` | `{err}` | {diag} |\n")
    md.append("\n")

md.append("---\n\n")
md.append("## 4. Recomendaciones para el Plugin\n\n")
md.append("1. **Identificar señales de evento:** Agregar el prefijo `[Solo en vivo]` a los canales de LPF Play para evitar reportes falsos de usuarios cuando no haya fútbol.\n")
md.append("2. **Limpieza de catálogo:** Quitar del archivo `MoaiCatalog.java` los canales con error 404 permanente (radios viejas y música).\n")
md.append("3. **Actualización de señales del Interior:** Reemplazar las URLs de Telefe Rosario, Santa Fe y Misiones con las señales vigentes de sus respectivos portales.\n")

os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, "w", encoding="utf-8") as f:
    f.write("".join(md))

print(f"Informe generado con éxito en: {output_path}")
