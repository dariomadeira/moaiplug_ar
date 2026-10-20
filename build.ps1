# Compila plugin.dex y regenera manifest.json en Windows
$ErrorActionPreference = 'Stop'

$sdk = if ($env:ANDROID_HOME) { $env:ANDROID_HOME } else { "$env:LOCALAPPDATA\Android\Sdk" }
$platformDir = Get-ChildItem "$sdk\platforms" | Sort-Object Name -Descending | Select-Object -First 1
$androidJar = "$($platformDir.FullName)\android.jar"
$buildToolsDir = Get-ChildItem "$sdk\build-tools" | Sort-Object Name -Descending | Select-Object -First 1
$d8 = "$($buildToolsDir.FullName)\d8.bat"

$jarCandidates = @(
    "$env:JAVA_HOME\bin\jar.exe",
    "C:\Program Files\Java\jdk-17\bin\jar.exe",
    "C:\Program Files\Android\Android Studio\jbr\bin\jar.exe"
)
$jar = $jarCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $jar) {
    $found = Get-ChildItem "C:\Program Files\Java" -Filter "jar.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($found) { $jar = $found.FullName }
}

Write-Host "Usando Platform: $androidJar"
Write-Host "Usando D8: $d8"
Write-Host "Usando Jar: $jar"

if (-not (Test-Path $androidJar) -or -not (Test-Path $d8)) {
    Write-Error "No se encontro android.jar o d8.bat en $sdk"
    exit 1
}

New-Item -ItemType Directory -Force -Path 'build\contract', 'build\plugin', 'build\out' | Out-Null

Write-Host ">> Compilando stubs del contrato..."
$contractFiles = Get-ChildItem "src\contract\java\com\infomak\moai\contract\*.java" | ForEach-Object { $_.FullName }
javac -encoding UTF-8 -source 8 -target 8 -d "build\contract" $contractFiles

Write-Host ">> Compilando plugin..."
$pluginFiles = Get-ChildItem "src\plugin\java\com\infomak\moai\ar\*.java" | ForEach-Object { $_.FullName }
javac -encoding UTF-8 -source 8 -target 8 -cp "build\contract;$androidJar" -d "build\plugin" $pluginFiles

Write-Host ">> Empaquetando jar..."
& $jar cf "build\plugin.jar" -C "build\plugin" .

Write-Host ">> Ejecutando d8 -> dex..."
& $d8 --min-api 21 --lib $androidJar --classpath "build\contract" --output "build\out" "build\plugin.jar"

Copy-Item "build\out\classes.dex" "plugin.dex" -Force
$sha = (Get-FileHash "plugin.dex" -Algorithm SHA256).Hash.ToLower()
Write-Host ">> plugin.dex generado. SHA-256: $sha"

Write-Host ">> Actualizando manifest.json..."
py -3 -c "
import json, io, unicodedata

def norm(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn').lower().strip()

flag_map = {
    'argentina': 'ar.png',
    'brasil': 'br.png',
    'brazil': 'br.png',
    'canada': 'ca.png',
    'paraguay': 'py.png',
    'uruguay': 'uy.png',
}
base = 'https://raw.githubusercontent.com/dariomadeira/moaiplug_ar/refs/heads/main/assets/flags/'

with io.open('manifest.json', 'r', encoding='utf-8') as f:
    m = json.load(f)

m['sha256'] = '$sha'
m['version'] = '1.7.2'
for c in m.get('canales', []):
    n = norm(c.get('pais', ''))
    c['flag'] = base + flag_map[n] if n in flag_map else ''

with io.open('manifest.json', 'w', encoding='utf-8') as f:
    json.dump(m, f, ensure_ascii=False, indent=2)

print('>> manifest.json actualizado con sha256 y banderas por canal.')
"

Write-Host "BUILD OK"
