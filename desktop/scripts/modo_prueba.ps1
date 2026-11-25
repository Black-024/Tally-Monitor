<#
 Abre Tally Monitor en MODO PRUEBA: al cerrarlo guarda un informe .json de la sesion (sin API Key, sin textos de
 respuestas, sin nombres de cuentas ni encuestas). Usa el .exe de la carpeta release si existe; si no, usa Python.
#>
$ErrorActionPreference = "Stop"
$Scripts = $PSScriptRoot
$Top     = Split-Path $Scripts -Parent
$Repo    = Join-Path $Top "tally-monitor"
$Release = Join-Path $Top "release"
if (-not (Test-Path (Join-Path $Repo "src\tally_monitor"))) { throw "No encuentro la carpeta tally-monitor junto a scripts. Mantene las 3 carpetas (tally-monitor, scripts, release) juntas." }
$dir = Join-Path $env:LOCALAPPDATA "TallyMonitor\informes-prueba"
$exe = Join-Path $Release "TallyMonitor\TallyMonitor.exe"
if (Test-Path $exe) {
    Start-Process -FilePath $exe -ArgumentList "--test" -Wait
} else {
    Write-Host "No hay .exe en release: se usa Python (py)."
    $env:PYTHONPATH = Join-Path $Repo "src"
    py -m tally_monitor --test
}
if (Test-Path $dir) {
    $last = Get-ChildItem $dir -Filter "informe-*.json" | Sort-Object LastWriteTime | Select-Object -Last 1
    if ($last) { Write-Host "Informe: $($last.FullName)"; explorer.exe /select,$($last.FullName) }
} else { Write-Host "No se genero ningun informe (se cerro la app sin abrirse?)." }
