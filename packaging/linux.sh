#!/usr/bin/env bash
set -euo pipefail

version="${1:-0.1.0}"
python_executable="${PYTHON_BIN:-python}"
mkdir -p artifacts
"$python_executable" -m PyInstaller --noconfirm --clean --windowed --onedir \
    --name DiskMapStudio --add-data 'diskmap/assets/icon.png:diskmap/assets' launch.py
QT_QPA_PLATFORM=offscreen timeout 30s dist/DiskMapStudio/DiskMapStudio --smoke

cp -r packaging/licenses dist/DiskMapStudio/
archive="diskmap-studio-${version}-linux-amd64"
tar -czf "artifacts/${archive}.tar.gz" -C dist DiskMapStudio

package="$(mktemp -d)"
trap 'rm -rf "$package"' EXIT
install -d "$package/DEBIAN" "$package/opt/diskmap-studio" \
    "$package/usr/share/applications" "$package/usr/share/icons/hicolor/256x256/apps"
cp -a dist/DiskMapStudio/. "$package/opt/diskmap-studio/"
install -m644 packaging/diskmap-studio.desktop "$package/usr/share/applications/"
install -m644 diskmap/assets/icon.png "$package/usr/share/icons/hicolor/256x256/apps/diskmap-studio.png"
cat > "$package/DEBIAN/control" <<CONTROL
Package: diskmap-studio
Version: $version
Section: utils
Priority: optional
Architecture: amd64
Maintainer: Franklin Leandro Martins <frank@franklem.com>
Depends: libc6 (>= 2.34), libegl1, libgl1, libfontconfig1, libdbus-1-3, libxkbcommon-x11-0, libxcb-cursor0, libxcb-icccm4, libxcb-keysyms1, libxcb-render-util0, libxcb-xinerama0, libxcb-xkb1
Description: Analisador gráfico e offline de armazenamento
 Tamanhos, treemap e histórico local de unidades e pastas.
CONTROL
dpkg-deb --root-owner-group --build "$package" "artifacts/diskmap-studio_${version}_amd64.deb"
