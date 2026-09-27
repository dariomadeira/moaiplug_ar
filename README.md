# Moai Argentina — plugin .dex (Contrato moai v1)

Plugin del motor moai3 que aporta canales de Argentina resueltos con el
**enfoque de resolución de pascua** (el motor Dart de `~/pascua`). El plugin
**solo resuelve** la señal; el motor de moai3 la reproduce tal cual.

## Catálogo

**398 canales** de Argentina y Latinaamérica, agrupados por país y categoría
(Aire, Noticias, Deportes, Interior, Radios, Cine y Series, Infantil, Cultural,
Novelas, Música, Cocina, Religioso, Adultos). El catálogo es **derivativo**: lo
genera `tools/generate_catalog.py` desde `~/pascua/assets/master.json` y nunca
se edita a mano.

| Método de resolución | Qué hace |
|---|---|
| **HLS directo** | Entrega la `.m3u8` tal cual con su `User-Agent` |
| **ClearKey** | DASH CENC; convierte `kid:…,k:…` a una **data URI** JSON local (el motor lo consume sin red) |
| **Flow CDN** | Obtiene un token `tok_` por probe de seeds + redirects, lo cachea 45–60 s, y reescribe la URL |

El plugin **solo resuelve** la señal: no reproduce, no descifra, no re-scraping
por reloj (`ttlMs = 0`).

## Logos

362 de los 398 canales tienen un logo verificado en vivo; los 36 restantes
muestran el ícono por defecto de la app. **Ninguna URL del catálogo está rota**
(auditado con `tools/check_logos.py`, 0 fallos).

Dos detalles que importan al momento de elegir un CDN:

- **Wikimedia Commons** rechaza `/thumb/` con anchos no estándar (HTTP 400), y
  los anchos válidos cambian según el archivo. El generador los reescribe a
  `Special:FilePath?width=250`, que siempre funciona.
- **User-Agent**: Wikimedia devuelve 429 a los UA genéricos de navegador. Al
  auditar hay que usar un UA descriptivo o la mitad de los logos parece caída.

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
| version       | `1.5.1`                                           |
| minContrato   | 1                                                 |
| maxContrato   | 1                                                 |
| canales       | 398 canales (100% operativos)                     |
| con logo      | 362 verificados en vivo (36 sin logo)              |
| canalInicial  | `telefe` → Telefe (Argentina)                     |
