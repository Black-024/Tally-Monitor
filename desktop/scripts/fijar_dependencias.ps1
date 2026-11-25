<#
 Fija versiones EXACTAS y hashes SHA-256 de todas las dependencias (requirements.lock y requirements-build.lock),
 para que lo que se empaqueta sea siempre lo mismo. Necesita Internet. Despues crear_release usa los .lock solo.
 Conviene correrlo de nuevo, probar y recien ahi publicar, cada vez que se quiera actualizar una dependencia.
#>
$ErrorActionPreference = "Stop"
$Scripts = $PSScriptRoot
$Top     = Split-Path $Scripts -Parent
$Repo    = Join-Path $Top "tally-monitor"
$Release = Join-Path $Top "release"
if (-not (Test-Path (Join-Path $Repo "src\tally_monitor"))) { throw "No encuentro la carpeta tally-monitor junto a scripts. Mantene las 3 carpetas (tally-monitor, scripts, release) juntas." }
Set-Location $Repo
py -m pip install --upgrade pip-tools
if ($LASTEXITCODE -ne 0) { throw "No se pudo instalar pip-tools." }
py -m piptools compile --generate-hashes --allow-unsafe --quiet --output-file requirements.lock requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Fallo al fijar requirements.txt" }
py -m piptools compile --generate-hashes --allow-unsafe --quiet --output-file requirements-build.lock requirements.txt requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw "Fallo al fijar requirements-build.txt" }
Write-Host "Listo: requirements.lock y requirements-build.lock (en tally-monitor)."
