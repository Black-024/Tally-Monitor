# Tally Monitor en macOS

## Requisitos
- macOS 11 (Big Sur) o posterior. Hay un paquete para Apple Silicon (`arm64`, M1 y posteriores) y otro para Intel (`x86_64`).
- La API Key se guarda cifrada en el **Llavero de macOS**; en `credentials.dat` solo queda una referencia opaca.
- Datos en `~/Library/Application Support/TallyMonitor`.

## Instalar
1. Descargá el `.dmg` que corresponda a tu Mac (menú  > *Acerca de esta Mac*: «Chip Apple» = `arm64`; «Intel» = `x86_64`).
2. Abrilo y arrastrá **Tally Monitor** a *Aplicaciones*. (El `.zip` contiene la misma app.)
3. Verificá la descarga si querés: `shasum -a 256 -c SHA256SUMS`.

## Primer arranque: el aviso de macOS
La app **no está firmada con un certificado de Apple ni notarizada** (cuesta una suscripción anual). Va firmada «ad hoc», así que arranca, pero macOS muestra un aviso la primera vez:
- *«No se puede abrir porque no se puede verificar al desarrollador»*: hacé clic derecho (o Control+clic) sobre la app > **Abrir** > **Abrir**.
- En macOS 15 o posterior: *Ajustes del Sistema > Privacidad y seguridad* > bajá hasta «Tally Monitor fue bloqueada» > **Abrir igualmente**.
- Alternativa por Terminal: `xattr -dr com.apple.quarantine /Applications/TallyMonitor.app`

## El Llavero
La primera vez que guardes una cuenta, macOS puede preguntar si permitís que Tally Monitor use el Llavero: elegí **Permitir siempre**. Como la app no está firmada con un certificado, macOS puede volver a preguntar después de actualizar la app. Si se borra el Llavero, hay que reingresar las API Keys (los datos de encuestas no se pierden).

## Ejecutar desde el código
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=src python -m tally_monitor
```

## Scripts (carpeta `scripts/macos`)
| Script | Qué hace |
|---|---|
| `bash scripts/macos/verificar.sh` | Pruebas, prueba de carga y auditoría de seguridad |
| `bash scripts/macos/modo_prueba.sh` | Abre la app en modo prueba y deja un informe `.json` sin datos sensibles |
| `bash scripts/macos/crear_release.sh` | Genera `TallyMonitor.app`, `.dmg` y `.zip` en `release/` (hay que correrlo en la arquitectura de destino) |

Los paquetes de cada arquitectura se generan también en GitHub Actions (ver `.github/workflows/build.yml`).
