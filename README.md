# Moai Argentina — plugin .dex (Contrato moai v1)

Plugin del motor moai3 que aporta canales de Argentina resueltos con el
**enfoque de resolución de pascua** (el motor Dart de `~/pascua`). El plugin
**solo resuelve** la señal; el motor de moai3 la reproduce tal cual.

## Canales

| id | Canal | Resolución | DRM | Estado |
|----|-------|------------|-----|--------|
| `canal_7_salta` | 7 Salta | DIRECTA (HLS, URL tal cual + UA) | no | v1 |

Plan: sumar un canal **CLEARKEY** y un canal **FLOW** (token CDN) para cubrir los
tres métodos de transmisión de pascua.

## Cómo resuelve la señal (v1, canal_7_salta)

1. Entrega directo
   `https://vivo.solumedia.com:2020/canal7salta/canal7salta.m3u8`
   con el User-Agent por defecto de pascua y formato `hls` (mismo camino
   "DIRECTO" de `ChannelResolver.resolve`). Sin token, sin DRM, sin geo.

## Instalación en moai3

Desde **Fuentes** en la app, pegar cualquiera de estas URLs (HTTPS):

- `https://raw.githubusercontent.com/<cuenta>/moaiplug_ar/main/manifest.json`
- `https://raw.githubusercontent.com/<cuenta>/moaiplug_ar/main/plugin.dex`

El host deriva el archivo gemelo automáticamente y verifica el `sha256`
siempre-on del dex contra `manifest.json`.

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

## Contrato

Compila contra `com.infomak.moai.contract` (stubs Java en
`src/contract/java/`). En runtime las clases del contrato las provee la app
(parent-first classloader); **no viajan en el .dex**. La clase del plugin es
`com.infomak.moai.ar.MoaiArPlugin` (constructor público sin argumentos).

| Campo         | Valor                                             |
|---------------|---------------------------------------------------|
| id            | `moai_ar`                                         |
| version       | `1.5.0`                                           |
| minContrato   | 1                                                 |
| maxContrato   | 1                                                 |
| canales       | 398 canales (100% operativos)                      |
| canalInicial  | `telefe` → Telefe (Argentina)                     |