<#
 Genera TODO lo distribuible, en la carpeta release:
   release\TallyMonitor\TallyMonitor.exe          (carpeta con el programa: doble clic)
   release\TallyMonitor-<version>-portable.zip     (version portable)
   release\TallyMonitor-Setup-<version>.exe        (instalador; solo si esta instalado Inno Setup 6)
   release\SHA256SUMS.txt y NOTAS.md
 Antes de generar corre las pruebas y la auditoria de seguridad: si algo falla, no se genera nada.
 No toca tus datos ni tu API Key.
#>
$ErrorActionPreference = "Stop"
$Scripts = $PSScriptRoot
$Top     = Split-Path $Scripts -Parent
$Repo    = Join-Path $Top "tally-monitor"
$Release = Join-Path $Top "release"
if (-not (Test-Path (Join-Path $Repo "src\tally_monitor"))) { throw "No encuentro la carpeta tally-monitor junto a scripts. Mantene las 3 carpetas (tally-monitor, scripts, release) juntas." }
Set-Location $Repo
$version = (py -c "import sys; sys.path.insert(0,'src'); from tally_monitor._version import __version__ as v; print(v)").Trim()
Write-Host "Version: $version"

Write-Host "1/6 Pruebas..."
py -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Hay pruebas fallando: no se genera la version." }
Write-Host "2/6 Auditoria de seguridad del codigo..."
py tools\auditoria_seguridad.py
if ($LASTEXITCODE -ne 0) { throw "La auditoria de seguridad encontro problemas." }

Write-Host "3/6 Dependencias y ejecutable..."
if (Test-Path requirements-build.lock) {
    Write-Host "  Usando dependencias fijadas con hashes (requirements-build.lock)."
    py -m pip install --require-hashes -r requirements-build.lock
} else {
    Write-Warning "No hay requirements-build.lock: se usan versiones sin fijar (corre fijar_dependencias.bat antes de publicar)."
    py -m pip install -r requirements.txt -r requirements-build.txt
}
if ($LASTEXITCODE -ne 0) { throw "Fallo la instalacion de dependencias." }
New-Item -ItemType Directory -Force $Release | Out-Null
$app = Join-Path $Release "TallyMonitor"
if (Test-Path $app) { Remove-Item $app -Recurse -Force }
$work = Join-Path $env:TEMP "tally-monitor-build"
py -m PyInstaller --noconfirm --clean --distpath $Release --workpath $work packaging\TallyMonitor.spec
if ($LASTEXITCODE -ne 0) { throw "Fallo PyInstaller." }
$exe = Join-Path $app "TallyMonitor.exe"
if (-not (Test-Path $exe)) { throw "No se genero $exe" }
$p = Start-Process -FilePath $exe -ArgumentList "--self-check" -PassThru -Wait
if ($p.ExitCode -ne 0) { throw "El autodiagnostico del .exe fallo (codigo $($p.ExitCode))." }

Write-Host "4/6 Licencias y auditoria del paquete..."
foreach ($f in "LICENSE","THIRD_PARTY_LICENSES.md","PRIVACIDAD.md") { Copy-Item $f $app -Force }
$ql = (py -c "import PySide6,os; print(os.path.dirname(PySide6.__file__))").Trim()
$lic = Join-Path $app "licenses"
New-Item -ItemType Directory -Force $lic | Out-Null
Get-ChildItem $ql -Filter "*LICENSE*" -ErrorAction SilentlyContinue | Copy-Item -Destination $lic -Force
Get-ChildItem (Join-Path (Split-Path $ql -Parent) "PySide6*.dist-info") -Recurse -Include "*LICENSE*","*LGPL*","*GPL*" -ErrorAction SilentlyContinue | Copy-Item -Destination $lic -Force
if (-not (Get-ChildItem $lic -ErrorAction SilentlyContinue)) { Write-Warning "No se encontraron archivos de licencia de PySide6/Qt: agregalos a mano en $lic antes de publicar." }
py tools\auditoria_seguridad.py $app
if ($LASTEXITCODE -ne 0) { throw "La auditoria del paquete encontro problemas: no se publica." }

Write-Host "5/6 Version portable e instalador..."
$zip = Join-Path $Release "TallyMonitor-$version-portable.zip"
Remove-Item $zip -ErrorAction SilentlyContinue
Compress-Archive -Path $app -DestinationPath $zip
$iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe","${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe","$env:ProgramFiles\Inno Setup 6\ISCC.exe") |
        Where-Object { Test-Path $_ } | Select-Object -First 1
if ($iscc) {
    & $iscc "/DAppVersion=$version" "/DDistDir=$app" "/O$Release" packaging\TallyMonitor.iss
    if ($LASTEXITCODE -ne 0) { throw "Fallo Inno Setup." }
} else { Write-Host "  Inno Setup 6 no esta instalado: se omite el instalador (el zip portable si se genero)." }

Write-Host "6/6 SHA-256 y notas..."
$sums = Get-ChildItem $Release -File | Where-Object { $_.Extension -in ".zip",".exe" } |
        ForEach-Object { "$((Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower())  $($_.Name)" }
$sums | Set-Content (Join-Path $Release "SHA256SUMS.txt") -Encoding ascii
@"
# Tally Monitor $version
Descarga el instalador (TallyMonitor-Setup-$version.exe) o el zip portable (descomprime y abre TallyMonitor.exe).
No esta firmado digitalmente: Windows puede mostrar un aviso de SmartScreen. Verifica la integridad con SHA256SUMS.txt:
  Get-FileHash .\archivo -Algorithm SHA256
Solo lectura: nunca modifica nada en Tally. Datos solo en tu equipo (ver PRIVACIDAD.md).
## SHA-256
$($sums -join "`n")
"@ | Set-Content (Join-Path $Release "NOTAS.md") -Encoding utf8
Write-Host "Listo. Archivos en $Release :"; Get-ChildItem $Release | Select-Object Name, Length
