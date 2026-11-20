# Moai Argentina — plugin .dex (Contrato moai v1)

Plugin del motor moai3 que aporta canales de Argentina resueltos con el
**enfoque de resolución de pascua** (el motor Dart de `~/pascua`). El plugin
**solo resuelve** la señal; el motor de moai3 la reproduce tal cual.

## Catálogo

**501 canales** de Argentina y Latinaamérica, agrupados por país y categoría
(Aire, Noticias, Deportes, Interior, Radios, Cine y Series, Infantil, Cultural,
Novelas, Música, Cocina, Religioso, Adultos). El catálogo es **derivativo**: lo
genera `tools/generate_catalog.py` desde dos fuentes y nunca se edita a mano.

| Origen | Qué aporta |
|---|---|
| `~/pascua/assets/master.json` | Base histórica: 398 canales, con Flow CDN y ClearKey |
| `tools/data/canales_free.json` | Instantánea de `moaiplug_free`: 149 canales HLS directos |

En la fusión **gana siempre el canal de AR**: uno de Free solo entra si no
coincide el `id`, la URL ni la identidad del canal (nombre canónico o alias
curado). Con los 149 de Free entran **103 canales nuevos** y se descartan 46
(id/URL/nombre repetidos, alias, 4 caídos en la auditoría y el HLS
duplicado de Argentinisima Satelital). El detalle queda en
`build/informe_merge_free.json` y el orden relativo de los canales de AR no se
altera.

| Método de resolución | Qué hace |
|---|---|
| **HLS directo** | Entrega la `.m3u8` tal cual con su `User-Agent` |
| **DASH / ClearKey** | DASH CENC; convierte `kid:…,k:…` a una **data URI** JSON local (el motor lo consume sin red) |
| **Flow CDN** | Obtiene un token `tok_` por probe de seeds + redirects, lo cachea 45–60 s, y reescribe la URL |
| **directo** | MP4, MP3/AAC y URLs que redirigen a un `.m3u8`: sin pista de MIME, ExoPlayer deduce el tipo |

`resolve()` clasifica el formato por extensión (`hls`, `dash`, `mpegts`,
`directo`), que es lo que espera `moai3`; antes todo lo que no era `.m3u8` se
marcaba DASH y las radios/MP4 se rompían.

El plugin **solo resuelve** la señal: no reproduce, no descifra, no re-scraping
por reloj (`ttlMs = 0`).

### Estado en vivo (auditoría 05-10-2026)

498 de 502 canales responden (`tools/check_channels.py`): los 104 importados
funcionan. Los 4 caídos son de AR y vinieron caídos después de la v1.5.0
(`9_santa_cruz` 404, `rock_pop` 404, `love_nature` y `mi_coche_clasico` 403 de
`jmp2.uk`); se dejan como están para no tocar lo que ya estaba instalado.

## Fusión con `moaiplug_free`

El build **no** depende del repo hermano. Para reimportar:

```bash
python3 tools/import_free_catalog.py      # moaiplug_free -> tools/data/canales_free.json
./build.sh                               # regenera catálogo, dex y manifest
```

El importador valida ids únicos, URLs y categorías antes de escribir el snapshot.
`generate_catalog.py` avisa (y no falla) si el snapshot no está.

## Logos

466 de los 502 canales tienen un logo verificado en vivo; los 36 restantes
muestran el ícono por defecto de la app. **Ninguna URL del catálogo está rota**
(auditado con `tools/check_logos.py`, 0 fallos).

Dos detalles que importan al momento de elegir un CDN:

- **Wikimedia Commons**: `Special:FilePath` devuelve HTML wiki (no SVG). El
  generador lo reescribe a `thumb.php?f=…&w=250`, que sirve PNG y no termina
  en `.svg` (moai3 no intenta parsear HTML como SVG).
- **User-Agent**: Wikimedia devuelve 429 a los UA genéricos de navegador. Al
  auditar hay que usar un UA descriptivo o la mitad de los logos parece caída.

### Logos para tema claro y oscuro

`tools/build_logos.py` baja cada logo y genera dos PNG de 384×384 servidos desde
este repo (`assets/logos/light/<id>.png` y `assets/logos/dark/<id>.png`). El
manifest los publica en dos campos nuevos; `logo` **no cambia**, así que las
versiones actuales de moai3 siguen igual:

```json
"logo":      "<origen de siempre>",
"logoLight": ".../assets/logos/light/telefe.png?v=57f1067e",
"logoDark":  ".../assets/logos/dark/telefe.png?v=57f1067e"
```

El `?v=` cambia cuando cambia la imagen, para que la app no muestre una copia
vieja de su caché. Si un canal no tiene versión generada, ambos campos repiten
`logo`.

Qué hace con cada logo:

- **Lienzo liso**: un logo sobre fondo blanco o negro liso pierde ese fondo. Si
  el fondo es de color (un "tile" de marca) o es una foto, se conserva entero
  con esquinas redondeadas.
- **Recoloreado**: en tema oscuro, el texto negro o gris que toca el fondo pasa
  a blanco y los colores muy oscuros (azul marino, bordó) se aclaran sin cambiar
  el tono. En tema claro, el texto blanco pasa a gris oscuro. Lo que está dentro
  de una insignia (letras blancas en un círculo negro) no se toca.
- **Placa**: solo si casi todo el logo desaparece contra el fondo, va sobre una
  placa redondeada.

Correcciones a mano en `tools/data/logo_overrides.json` (por id: `source`, `bg`,
`light`, `dark`). Para revisar, abrir `build/logos_preview.html`, que muestra
original, claro y oscuro de cada canal sobre ambos fondos.

```bash
py -3 tools/build_logos.py --apply-manifest   # Windows (python3 en Linux)
```

Solo reprocesa lo que cambió (`--force` para todo, `--only id1,id2` para
algunos). Si el build cambia la URL de origen de un logo, correr `./build.sh` y
después `build_logos.py --apply-manifest`.

## Instalación en moai3

Desde **Fuentes** en la app, pegar cualquiera de estas URLs (HTTPS):

- `https://raw.githubusercontent.com/dariomadeira/moaiplug_ar/refs/heads/main/manifest.json`
- `https://raw.githubusercontent.com/dariomadeira/moaiplug_ar/refs/heads/main/plugin.dex`

El host deriva el archivo gemelo automáticamente y verifica el `sha256`
siempre-on del dex contra `manifest.json`.

**Actualizaciones**: moai3 compara el *string* de versión del manifest remoto
contra el instalado (`PluginUpdateService.isNewer`) y ofrece el update al abrir
la app. Por eso hay que subir la versión en los tres lugares —`build.sh`,
`MoaiArPlugin.manifest()` y el `manifest.json` generado— antes de pushear: si se
pushea un build nuevo con la misma versión, la app no lo detecta.


## Construcción

```bash
./build.sh
```

Genera `plugin.dex` y `manifest.json` (con `sha256`) en la raíz. Requiere
JDK 8+ y Android SDK (avanzado por `ANDROID_HOME` o `~/Android/Sdk`, default
build-tools 36.0.0).

### Autotest en JVM

```bash
java -cp build/plugin:build/contract com.infomak.moai.ar.MoaiArPlugin
```

### Comprobar estado de los canales en vivo

```bash
python3 tools/check_channels.py
# o filtrar por categoría / búsqueda:
python3 tools/check_channels.py --cat Deportes
python3 tools/check_channels.py --search espn
python3 tools/check_channels.py --failed-only
```

### Auditar los logos

```bash
python3 tools/check_logos.py --failed-only
python3 tools/check_logos.py --host wikimedia --workers 3 --delay 0.6
python3 tools/check_logos.py --only telefe,el_trece --output reporte.json
```

A diferencia de `check_channels.py` (que prueba el stream), esto descarga una
muestra de cada logo y valida que el servidor responda con una imagen real y no
con una página de error. Bajá los `--workers` y sumá `--delay` para CDNs que
limitan requests.

## Contrato

Compila contra `com.infomak.moai.contract` (stubs Java en
`src/contract/java/`). En runtime las clases del contrato las provee la app
(parent-first classloader); **no viajan en el .dex**. La clase del plugin es
`com.infomak.moai.ar.MoaiArPlugin` (constructor público sin argumentos).

| Campo         | Valor                                             |
|---------------|---------------------------------------------------|
| id            | `moai_ar`                                         |
| tag           | `ar`                                              |
| version       | `1.8.0`                                           |
| minContrato   | 1                                                 |
| maxContrato   | 1                                                 |
| canales       | 501 canales                                       |
| con logo      | 466 verificados en vivo (36 sin logo)              |
| canalInicial  | `telefe` → Telefe (Argentina)                     |
