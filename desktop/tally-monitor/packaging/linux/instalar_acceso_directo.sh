#!/usr/bin/env bash
# Crea el acceso directo de Tally Monitor en el menú de aplicaciones (solo para tu usuario, sin sudo).
# Uso, desde la carpeta TallyMonitor ya descomprimida:  bash instalar_acceso_directo.sh
# Para quitarlo:  bash instalar_acceso_directo.sh --quitar
set -euo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICONOS="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/512x512/apps"
if [ "${1:-}" = "--quitar" ]; then
  rm -f "$APPS/tally-monitor.desktop" "$ICONOS/tally-monitor.png"; echo "Acceso directo quitado."; exit 0
fi
[ -x "$AQUI/TallyMonitor" ] || { echo "Ejecutá este script dentro de la carpeta TallyMonitor."; exit 1; }
mkdir -p "$APPS" "$ICONOS"
cp "$AQUI/_internal/tally_monitor/assets/logo.png" "$ICONOS/tally-monitor.png" 2>/dev/null || \
  cp "$AQUI/tally_monitor/assets/logo.png" "$ICONOS/tally-monitor.png"
cat > "$APPS/tally-monitor.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=Tally Monitor
Comment=Ver, analizar y exportar tus encuestas de Tally (solo lectura)
Exec="$AQUI/TallyMonitor"
Icon=tally-monitor
Categories=Office;Utility;
Terminal=false
StartupWMClass=TallyMonitor
DESK
update-desktop-database "$APPS" >/dev/null 2>&1 || true
echo "Listo: buscá «Tally Monitor» en el menú de aplicaciones."
