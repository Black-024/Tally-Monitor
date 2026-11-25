<#
 Verificacion completa antes de publicar: pruebas automaticas, prueba de carga y auditoria de seguridad.
#>
$ErrorActionPreference = "Stop"
$Scripts = $PSScriptRoot
$Top     = Split-Path $Scripts -Parent
$Repo    = Join-Path $Top "tally-monitor"
$Release = Join-Path $Top "release"
if (-not (Test-Path (Join-Path $Repo "src\tally_monitor"))) { throw "No encuentro la carpeta tally-monitor junto a scripts. Mantene las 3 carpetas (tally-monitor, scripts, release) juntas." }
Set-Location $Repo
py -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Hay pruebas fallando." }
py (Join-Path $Scripts "prueba_de_carga.py")
py tools\auditoria_seguridad.py
if ($LASTEXITCODE -ne 0) { throw "La auditoria de seguridad encontro problemas." }
Write-Host "TODO OK."
