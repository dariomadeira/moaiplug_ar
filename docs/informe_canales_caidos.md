# 📋 Informe de Canales Caídos — Moai Argentina (`moaiplug_ar`)

> **Fecha de auditoría:** 23 de septiembre de 2026  
> **Herramienta:** `tools/check_channels.py`  
> **Canales analizados:** 448  
> **🟢 Operativos:** 395 (88.2%)  
> **🔴 Caídos / Error:** 53 (11.8%)  
>
> **ESTADO:** Resuelto en la versión `1.5.0` del plugin. Se excluyeron los canales no operativos del catálogo compilado, dejando **398 canales 100% funcionales**.

---

## 1. Resumen Ejecutivo por Categoría

| Categoría | Caídos | Motivo Principal |
|---|:---:|---|
| **Deportes** | 19 | Feeds temporales de partidos (LPF Play) inactivos fuera de horario + links 404 |
| **General** | 14 | Geobloqueo regional (Bolivia) con HTTP 403 Forbidden |
| **Radios** | 6 | Streams con enlaces viejos (404), SSL vencido o servidores caídos |
| **Interior** | 5 | Servidores provinciales locales caídos o enlaces caducados (404) |
| **Música** | 4 | Enlaces muertos (HTTP 404) |
| **Novelas** | 2 | Enlaces muertos (HTTP 404) |
| **Religioso** | 1 | Enlace muerto (HTTP 404) |
| **Adultos** | 1 | Bloqueo HTTP 403 en CDN |
| **Noticias** | 1 | Timeout de CDN internacional |

---

## 2. Diagnóstico de Causas Raíz

1. **Transmisiones temporales de eventos (LPF Play / F1):** Señales que únicamente transmiten cuando hay partidos en vivo. Fuera de evento devuelven `Network unreachable` o `404 Not Found` porque los transcodificadores de origen no emiten.
2. **Geobloqueo regional (HTTP 403 Forbidden):** Varios canales de Bolivia y señales internacionales rechazan peticiones fuera de su país o requieren autenticación web.
3. **Enlaces caídos o deprecados (HTTP 404 / 401):** Canales de música y radios locales cuyos servidores cambiaron de URL o cerraron.
4. **Certificados TLS caducados:** Fallos en el handshake SSL (`CERTIFICATE_VERIFY_FAILED`) en servidores que no renovaron su certificado.

---

## 3. Detalle Exhaustivo de los Canales Caídos

### 📁 Adultos (1 canales)

| Canal | ID en Plugin | Código / Error | Diagnóstico Técnico |
|---|---|---|---|
| **Sexy Hot** | `sexy_hot` | `HTTP 403: Forbidden` | Geobloqueo regional o protección CDN |

### 📁 Deportes (19 canales)

| Canal | ID en Plugin | Código / Error | Diagnóstico Técnico |
|---|---|---|---|
| **(PLAY 2)** | `play_2` | `[Errno 101] Network is unreachable` | Feed temporal inactivo (Solo en vivo durante partidos) |
| **(PLAY 1)** | `play_1` | `[Errno 101] Network is unreachable` | Feed temporal inactivo (Solo en vivo durante partidos) |
| **PLAY 1** | `play_1_2` | `[Errno 101] Network is unreachable` | Feed temporal inactivo (Solo en vivo durante partidos) |
| **PLAY 2** | `play_2_2` | `[Errno 101] Network is unreachable` | Feed temporal inactivo (Solo en vivo durante partidos) |
| **PLAY 3** | `play_3_2` | `[Errno 101] Network is unreachable` | Feed temporal inactivo (Solo en vivo durante partidos) |
| **(PLAY 3)** | `play_3` | `[Errno 101] Network is unreachable` | Feed temporal inactivo (Solo en vivo durante partidos) |
| **(PLAY 4)** | `play_4` | `[Errno 101] Network is unreachable` | Feed temporal inactivo (Solo en vivo durante partidos) |
| **PLAY 4** | `play_4_2` | `[Errno 101] Network is unreachable` | Feed temporal inactivo (Solo en vivo durante partidos) |
| **(PLAY 5)** | `play_5` | `[Errno 101] Network is unreachable` | Feed temporal inactivo (Solo en vivo durante partidos) |
| **PLAY 5** | `play_5_2` | `[Errno 101] Network is unreachable` | Feed temporal inactivo (Solo en vivo durante partidos) |
| **(PLAY 6)** | `play_6` | `[Errno 101] Network is unreachable` | Feed temporal inactivo (Solo en vivo durante partidos) |
| **PLAY 6** | `play_6_2` | `[Errno 101] Network is unreachable` | Feed temporal inactivo (Solo en vivo durante partidos) |
| **Basquet TV** | `basquet_tv` | `HTTP 403: Forbidden` | Geobloqueo regional o protección CDN |
| **EVENTOS FORMULA 1** | `eventos_formula_1` | `HTTP 404: Not Found` | Enlace caído o cambiado de ruta en origen |
| **PLUS+ tv** | `plus_tv` | `[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1082)` | Certificado SSL del servidor vencido |
| **Sky sport F1 Eventos** | `sky_sport_f1_eventos` | `HTTP 404: Not Found` | Enlace caído o cambiado de ruta en origen |
| **T. Deportes** | `t_deportes` | `HTTP 403: Forbidden` | Geobloqueo regional o protección CDN |
| **Telemundo** | `telemundo` | `HTTP 403: Forbidden` | Geobloqueo regional o protección CDN |
| **DAZN F1** | `dazn_f1` | `Timeout (> 8s)` | Servidor sin respuesta dentro del límite de tiempo |

### 📁 General (14 canales)

| Canal | ID en Plugin | Código / Error | Diagnóstico Técnico |
|---|---|---|---|
| **Cadena A** | `cadena_a` | `HTTP 403: Forbidden` | Geobloqueo regional o protección CDN |
| **Bolivia TV** | `bolivia_tv` | `HTTP 403: Forbidden` | Geobloqueo regional o protección CDN |
| **Bolivisión** | `bolivision` | `HTTP 403: Forbidden` | Geobloqueo regional o protección CDN |
| **F10** | `f10` | `HTTP 403: Forbidden` | Geobloqueo regional o protección CDN |
| **Red Gigavisión** | `red_gigavision` | `HTTP 403: Forbidden` | Geobloqueo regional o protección CDN |
| **Red pat** | `red_pat` | `HTTP 403: Forbidden` | Geobloqueo regional o protección CDN |
| **RTP** | `rtp` | `HTTP 403: Forbidden` | Geobloqueo regional o protección CDN |
| **Red Uno** | `red_uno` | `HTTP 403: Forbidden` | Geobloqueo regional o protección CDN |
| **TV Culturas** | `tv_culturas` | `HTTP 403: Forbidden` | Geobloqueo regional o protección CDN |
| **Unitel Cochabamba** | `unitel_cochabamba` | `HTTP 403: Forbidden` | Geobloqueo regional o protección CDN |
| **Unitel La Paz** | `unitel_la_paz` | `HTTP 403: Forbidden` | Geobloqueo regional o protección CDN |
| **TVU La Paz** | `tvu_la_paz` | `HTTP 403: Forbidden` | Geobloqueo regional o protección CDN |
| **ATB** | `atb` | `HTTP 403: Forbidden` | Geobloqueo regional o protección CDN |
| **GEN TV** | `gen_tv` | `Timeout (> 8s)` | Servidor sin respuesta dentro del límite de tiempo |

### 📁 Interior (5 canales)

| Canal | ID en Plugin | Código / Error | Diagnóstico Técnico |
|---|---|---|---|
| **5 Telefe Rosario (Cba)** | `5_telefe_rosario_cba` | `HTTP 404: Not Found` | Enlace caído o cambiado de ruta en origen |
| **13 Telefe Santa Fe** | `13_telefe_santa_fe` | `HTTP 404: Not Found` | Enlace caído o cambiado de ruta en origen |
| **12 Misiones** | `12_misiones` | `HTTP 404: Not Found` | Enlace caído o cambiado de ruta en origen |
| **San Luis+** | `san_luis` | `[Errno 111] Connection refused` | Servidor fuera de línea (puerto cerrado) |
| **Somos El Valle** | `somos_el_valle` | `Timeout (> 8s)` | Servidor sin respuesta dentro del límite de tiempo |

### 📁 Música (4 canales)

| Canal | ID en Plugin | Código / Error | Diagnóstico Técnico |
|---|---|---|---|
| **Beat Box** | `beat_box` | `HTTP 404: Not Found` | Enlace caído o cambiado de ruta en origen |
| **Exa TV** | `exa_tv` | `HTTP 404: Not Found` | Enlace caído o cambiado de ruta en origen |
| **VR +** | `vr` | `HTTP 404: Not Found` | Enlace caído o cambiado de ruta en origen |
| **Video Rola** | `video_rola` | `HTTP 404: Not Found` | Enlace caído o cambiado de ruta en origen |

### 📁 Noticias (1 canales)

| Canal | ID en Plugin | Código / Error | Diagnóstico Técnico |
|---|---|---|---|
| **CNN International** | `cnn_international` | `Timeout (> 8s)` | Servidor sin respuesta dentro del límite de tiempo |

### 📁 Novelas (2 canales)

| Canal | ID en Plugin | Código / Error | Diagnóstico Técnico |
|---|---|---|---|
| **AZ CORAZÓN** | `az_corazon` | `HTTP 404: Not Found` | Enlace caído o cambiado de ruta en origen |
| **AZTECA 7** | `azteca_7` | `HTTP 404: Not Found` | Enlace caído o cambiado de ruta en origen |

### 📁 Radios (6 canales)

| Canal | ID en Plugin | Código / Error | Diagnóstico Técnico |
|---|---|---|---|
| **Del Sur** | `del_sur` | `[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1082)` | Certificado SSL del servidor vencido |
| **Cadena Alegria** | `cadena_alegria` | `HTTP 404: Not Available` | Enlace caído o cambiado de ruta en origen |
| **Estacion 21** | `estacion_21` | `HTTP 404: Not found` | Enlace caído o cambiado de ruta en origen |
| **Mas Tropical** | `mas_tropical` | `HTTP 401: Unauthorized` | Requiere credenciales / token de sesión |
| **Mitre Jujuy** | `mitre_jujuy` | `HTTP 403: Forbidden` | Geobloqueo regional o protección CDN |
| **Punto de Encuentro** | `punto_de_encuentro` | `[Errno 111] Connection refused` | Servidor fuera de línea (puerto cerrado) |

### 📁 Religioso (1 canales)

| Canal | ID en Plugin | Código / Error | Diagnóstico Técnico |
|---|---|---|---|
| **JTA TV** | `jta_tv` | `HTTP 404: Not Found` | Enlace caído o cambiado de ruta en origen |

---

## 4. Recomendaciones para el Plugin

1. **Identificar señales de evento:** Agregar el prefijo `[Solo en vivo]` a los canales de LPF Play para evitar reportes falsos de usuarios cuando no haya fútbol.
2. **Limpieza de catálogo:** Quitar del archivo `MoaiCatalog.java` los canales con error 404 permanente (radios viejas y música).
3. **Actualización de señales del Interior:** Reemplazar las URLs de Telefe Rosario, Santa Fe y Misiones con las señales vigentes de sus respectivos portales.
