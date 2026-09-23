# MoaiAr Plugin — Spec (contrato moai v1)

Plugin `moai_ar` del motor moai3. **Solo resuelve la señal**; la app la
reproduce. El catálogo (398 canales 100% operativos, v1.5.0) se genera desde la copia reparada
de pascua (`~/pascua/assets/master.json`) aplicando el filtro de exclusión auditado
(`EXCLUDED_CHANNEL_IDS` en `generate_catalog.py`), y viaja en `manifest.json`; el dex
aporta el resolver.

## Automation
- id: `moai_ar` · tag: `ar` · clase: `com.infomak.moai.ar.MoaiArPlugin`
- minContrato / maxContrato: `1`
- Ruta build: `./build.sh` (1 comando → `plugin.dex` + `manifest.json` con sha256)
- Autotest JVM: `java -cp build/plugin:build/contract com.infomak.moai.ar.MoaiArPlugin`

## Goals

- **G1**: Entregar a la app una URL de reproducción lista para HLS o DASH por
  cada canal del catálogo, con headers y DRM asociados.
- **G2**: Sustituir DRM Widevine CENC por ClearKey (claves `kid` de pascua),
  local (data URI) o vía licencia externa, para que el motor moai3 reproduzca
  sin servidor de licencias propio.
- **G3**: Resolver el token CDN de Flow (FlowTokenManager) con la misma
  estrategia que pascua: probe de seeds, seguimiento de redirects y extracción
  de `tok_`, cacheando el token ~45-60 s.
- **G4**: Mantener el catálogo generado (no editado a mano): una sola fuente
  (`master.json`) produce `MoaiCatalog.java` + `manifest.json`
  (build-time).
- **G5**: El resolver no debe depender de procesos servidor ni scrapers por
  reloj: la señal sale del payload del catálogo, no de re-scraping.

## Non-Goals

- **NG1**: No verifica en resolve-time que el m3u8 responda `#EXTM3U` (a
  diferencia de `moaiplug_daddylive`): entrega la URL tal cual (modo "DIRECTO"
  de pascua). Un canal caído falla en reproducción, no en resolución.
- **NG2**: No re-resuelve ni cachea por reloj: `ttlMs` siempre `0` (sin hint
  de vida para el host).
- **NG3**: No implementa Widevine nativo / L1: solo **ClearKey** (`tipo="clearkey"`).
- **NG4**: No descifra contenido ni elimina DRM.
- **NG5**: No admite canales fuera de `master.json`: el catálogo es derivativo.
- **NG6**: No sirve los ids `stream-N` de Daddylive ni otros layouts ajenos a
  pascua.

## Requirements

### Requirement: Build de catálogo (single command)

`./build.sh` SHALL regenerar el catálogo y los artefactos en un solo paso, en
este orden: `tools/generate_catalog.py` → compilar stubs del contrato →
compilar plugin contra `android.jar` (build-tools 36.0.0, JDK 8+) → `d8
--min-api 21` → `classes.dex` → copiar a `plugin.dex` → recalcular `sha256` →
escribir `manifest.json` (id, tag, nombre, version, min/maxContrato, clase,
sha256, canalInicial, canales).

#### Scenario: Rebuild tras cambio de catálogo
- **WHEN** `./build.sh` corre y `master.json` cambió
- **THEN** `MoaiCatalog.java` se regenera, `ult_canales.json` se reescribe y
  `manifest.json` refleja el nuevo `sha256` del dex y la misma lista de canales.

### Requirement: Generación de catálogo desde master.json

`tools/generate_catalog.py` SHALL mapear cada grupo de `master.json.categories`
según `GROUP_CONFIG` (30 grupos) a país y categoría, filtrar basura
(`JUNK_PATTERNS`: apks, telegram, tutorials, worldtv), excluir los canales con
streams no operativos o caducados (`EXCLUDED_CHANNEL_IDS`), generar `id` slug únicos
(sufijo `_2`, `_3`… ante duplicados), limpiar logos (`LOGO_OVERRIDES` hacia CDN
GitHub `tv-logo`; `nocookie.net`/`data:` → `""`) y ordenar por
país (Argentina primero) → categoría (`CATEGORY_PRIORITY`, **Adultos = 999 al
final**) → relevancia (`channel_priority`).

#### Scenario: Canal con nombre duplicado
- **WHEN** dos canales producen el mismo slug
- **THEN** el segundo recibe sufijo numérico (`_2`) y ambos conservan su URL y
  headers originales.

#### Scenario: Canal no operativo en auditoría
- **WHEN** un canal tiene su ID en `EXCLUDED_CHANNEL_IDS`
- **THEN** no se agrega al catálogo compilado ni al manifest, garantizando 100% de operatividad.

#### Scenario: Logo caído u origen basura
- **WHEN** un canal usa logo `nocookie.net` o `data:`
- **THEN** el catálogo emite `logo=""` y la app muestra el logo por defecto.

### Requirement: Autoridad de canales y versionado

El host SHALL leer la lista de canales desde `manifest.json` (`canales` +
`canalInicial: telefe`); el dex embebido (`manifest()`) queda como fallback y
coincide en versión e ids. La versión SHALL ser unificada en `1.5.0` en `build.sh`
(env `PLUGIN_VERSION`, default `1.5.0`), `manifest.json` y en `MoaiArPlugin.manifest()`.

#### Scenario: Host carga el plugin
- **WHEN** se agrega la fuente (URLs de `manifest.json`/`plugin.dex`)
- **THEN** el host deriva el gemelo, verifica el `sha256`, lee los 398 canales
  del `manifest.json` y resuelve con el dex.

### Requirement: Lookup de canal

`resolve()` SHALL devolver la entrada del canal vía `MoaiCatalog.byId(id)`.

#### Scenario: Canal desconocido
- **WHEN** `channelId` no existe en el catálogo
- **THEN** lanza `IllegalArgumentException("MoaiAr: canal desconocido …")`.

### Requirement: Headers de entrega

El `ResolveResult` SHALL incluir `User-Agent` Chrome 133 (Windows) fusionado
con los headers por-canal del catálogo.

#### Scenario: Canal con headers propios
- **WHEN** el canal define `headers` en `master.json`
- **THEN** esos headers se agregan por encima del UA por defecto.

### Requirement: Resolución Flow CDN

Un canal es Flow SHALL detectarse por marcadores
(`cvattv.com.ar`, `cvattv.com.py`, `flow.com.ar`, `flow.com.py`,
`cdn-token.app.flow.com.ar`). Para Flow, el resolver SHALL obtener un token
firme a `FlowTokenManager`: probar `FLOW_SEED_URLS` (orden fijo, seed
`chromecast/Viajar` primero), seguir redirects manualmente (máx. 5,
`followRedirects=false`), extraer `tok_[…]` del `Location`, y construir
`https://{host}/{tok}/{relPath}` re-cortando el path con `live/c\d+eds/[^?#]*`.
SHALL añadir `Origin`/`Referer: https://portal.app.flow.com.ar/` e incorporar el
token al resto de headers. El token SHALL cachearse (static, synchronized)
con TTL aleatorio **45–60 s**.

#### Scenario: Seed redirige a edge con tok
- **WHEN** se proba `chromecast/Viajar.mpd` y su `Location` contiene `/tok_…`
- **THEN** se cachea `{host, tok}` y se entrega la URL con token para el canal Flow.

#### Scenario: Ninguna seed responde
- **WHEN** las 4 seeds fallan o no aportan `tok_`
- **THEN** `resolve()` lanza `RuntimeException("no se obtuvo token Flow CDN")`.

### Requirement: Selección de formato

El formato SHALL ser `hls` si la URL termina en `.m3u8` (o contiene `.m3u8?`),
`dash` en caso contrario.

#### Scenario: Canal HLS directo (7 Salta)
- **WHEN** el canal apunta a `…/canal7salta.m3u8`
- **THEN** `format="hls"`, sin DRM, sin token, headers mínimos.

#### Scenario: Canal DASH CENC (Cazé FHD)
- **WHEN** el canal apunta a un MPD
- **THEN** `format="dash"` y `drm` con licencia ClearKey.

### Requirement: Conversión de DRM a ClearKey

`drmFor` SHALL convertir la licencia del catálogo: vacío → `null` (sin DRM);
`https?://…` → `DrmInfo("clearkey", url)` (femon/Widevine tal cual); formato
`kid:…,k:…` (con `keyid:`/`key:` también) → `DrmInfo("clearkey",
"data:application/json," + {"keys":[…],"type":"temporary"})` (local, sin red).
Casos con prefijo raro (solo `kid` sin `k:`) se asignan como `kid` directo.

#### Scenario: Licencia inline local
- **WHEN** el catálogo trae `kid:<b64url>,k:<b64url>`
- **THEN** se emite una data URI JSON ClearKey que el motor consume vía
  `LocalMediaDrmCallback` sin llamada externa.

#### Scenario: Licencia externa
- **WHEN** el catálogo trae una URL HTTPS
- **THEN** se pasa tal cual como `licenceUrl` de tipo `clearkey`.

### Requirement: Sin hint de vida

`resolve()` SHALL devolver `ttlMs = 0L`: el host NO cachea la resolución; cada
apertura llama de nuevo al plugin (sin proceso servidor).

#### Scenario: Reapertura de canal
- **WHEN** el usuario reabre un canal dentro de la sesión
- **THEN** se entrega un `ResolveResult` fresco; para Flow el token reutiliza
  la caché estática si aún es válido (≤ 60 s).