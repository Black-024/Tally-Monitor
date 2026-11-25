# Tally Monitor en Linux

## Requisitos
- Linux de 64 bits (x86_64) con escritorio gráfico (X11 o Wayland vía XWayland). Probado con Linux Mint y Kali.
- **Un llavero activo**, donde se guarda la API Key cifrada (nunca en un archivo):
  - Linux Mint, Ubuntu, Fedora (GNOME/Cinnamon/MATE): `gnome-keyring` ya viene instalado y se desbloquea al iniciar sesión.
  - KDE: KWallet.
  - Kali y otros entornos mínimos (XFCE): puede no haber llavero. Instalá `gnome-keyring` (`sudo apt install gnome-keyring libsecret-1-0`) y cerrá sesión y volvé a entrar.
  - Sin llavero, la app **se niega a guardar claves** (no existe modo sin cifrar) y lo explica en pantalla.
- Datos en `~/.local/share/TallyMonitor` (o `$XDG_DATA_HOME/TallyMonitor`).

## Usar el `.tar.gz`
```bash
tar -xzf TallyMonitor-1.0.0-linux-x86_64.tar.gz
./TallyMonitor/TallyMonitor
```
Para tenerlo en el menú de aplicaciones: `bash TallyMonitor/instalar_acceso_directo.sh` (con `--quitar` se desinstala).
Para verificar la descarga: `sha256sum -c SHA256SUMS`.

## Usar el AppImage
```bash
chmod +x TallyMonitor-1.0.0-linux-x86_64.AppImage
./TallyMonitor-1.0.0-linux-x86_64.AppImage
```
Si tu sistema no tiene FUSE 2: `sudo apt install libfuse2` (o ejecutá con `--appimage-extract-and-run`).

## Ejecutar desde el código
```bash
sudo apt install python3 python3-venv libxcb-cursor0    # Debian/Ubuntu/Mint/Kali
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=src python -m tally_monitor
```

## Scripts (carpeta `scripts/linux`)
| Script | Qué hace |
|---|---|
| `bash scripts/linux/verificar.sh` | Pruebas, prueba de carga y auditoría de seguridad |
| `bash scripts/linux/modo_prueba.sh` | Abre la app en modo prueba y deja un informe `.json` sin datos sensibles |
| `bash scripts/linux/crear_release.sh` | Genera `.tar.gz` (y AppImage si hay `appimagetool`) en `release/` |

## Problemas conocidos
- «Could not load the Qt platform plugin "xcb"»: instalá `libxcb-cursor0`.
- «No se encontró un llavero del sistema activo»: ver Requisitos.
- Si el llavero se reinicia o se borra, hay que reingresar las API Keys (los datos de encuestas no se pierden).
